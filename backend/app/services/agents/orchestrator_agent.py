"""
Orchestrator Agent - Brain of the Multi-Agent System
Routes user requests to appropriate specialized agents
"""

import structlog
from typing import Dict, Any, List, Optional
from enum import Enum
from pydantic import BaseModel

from app.services.llm_service import LLMService
from app.services.rag_service import RAGService
from app.core.database import AsyncSession
from app.services.agents.thought_stream import ThoughtStream, ThoughtType

logger = structlog.get_logger()


class IntentType(str, Enum):
    """Types of user intentions"""
    QUERY_DATA = "query_data"  # SQL queries (copropriétaires, copropriétés, etc.)
    SEARCH_DOCUMENTS = "search_documents"  # RAG search (contracts, regulations)
    SEND_EMAIL = "send_email"  # Generate and send emails
    CONFIRM_EMAIL = "confirm_email"  # Confirm sending email after draft review
    REQUEST_QUOTES = "request_quotes"  # Request devis from vendors
    ANALYZE_DOCUMENT = "analyze_document"  # OCR + extraction
    GENERATE_DIGEST = "generate_digest"  # Generate email digest
    GENERAL_QUESTION = "general_question"  # General assistant question
    TRIGGER_WORKFLOW = "trigger_workflow"  # Explicit N8N workflow trigger


class AgentResponse(BaseModel):
    """Standardized agent response format"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    agents_used: List[str] = []
    confidence: float = 1.0
    suggestions: List[str] = []


class OrchestratorAgent:
    """
    Orchestrator Agent - Routes requests to specialized agents

    This is the brain that:
    1. Classifies user intentions
    2. Determines which agents to call
    3. Coordinates multi-agent workflows
    4. Aggregates and formats results
    """

    def __init__(self):
        self.llm_service = LLMService()
        self.rag_service = RAGService()
        # Import new v2 components
        from .intent_classifier_v2 import IntentClassifierV2
        from .hybrid_executor import HybridExecutor
        from .response_fusion_agent import ResponseFusionAgent
        # Import Phase 1 components (Planner + Evaluator)
        from .planner_dag import PlannerDAG
        from .evaluator import Evaluator

        self.intent_classifier_v2 = IntentClassifierV2()
        self.hybrid_executor = HybridExecutor()
        self.fusion_agent = ResponseFusionAgent()
        self.planner = PlannerDAG()
        self.evaluator = Evaluator()

        logger.info("orchestrator_agent_initialized", version="v2.1_with_planner_evaluator")

    async def classify_intention(self, user_input: str, context: Dict[str, Any] = None) -> IntentType:
        """
        Classify user intention using LLM

        Args:
            user_input: User's message
            context: Optional context (uploaded files, conversation history)

        Returns:
            IntentType enum
        """
        classification_prompt = f"""
Analyse l'intention de l'utilisateur et classifie-la dans UNE de ces catégories:

CATÉGORIES:
- query_data: Questions sur données structurées UNIQUEMENT (coordonnées contacts, informations personnelles)
  Exemples: "Combien de copropriétaires?", "Email du plombier?", "Téléphone de Marie Dupont?", "Adresse de la copropriété?"

  ⚠️ NE PAS UTILISER pour: prix, tarifs, coûts, conditions contractuelles → utiliser search_documents

- search_documents: Recherche dans documents DÉJÀ UPLOADÉS et indexés (RAG)
  Exemples généraux:
    * "Que contient le fichier X?"
    * "Recherche dans les documents: [mot-clé]"
    * "Que disent les documents sur [sujet]?"
    * "Trouve-moi des infos dans les docs"
    * "Contenu du document X"
    * "Résume le document X"
    * "Procédure dégât des eaux"
    * "Règlement copropriété article 5"

  Exemples PRIX/TARIFS (TRÈS IMPORTANT):
    * "Quel est le prix du plombier?"
    * "Tarif du jardinier?"
    * "Coût de l'entretien?"
    * "Combien coûte la maintenance?"
    * "Conditions de paiement du fournisseur?"
    * "Devis pour les travaux?"
    * "Honoraires du syndic?"

  NOTE IMPORTANTE: Si l'utilisateur mentionne un nom de fichier ou demande le contenu d'un document,
  c'est TOUJOURS search_documents (sauf si un fichier est actuellement attaché à la requête)

  NOTE CRITIQUE: Les informations financières (prix, tarifs, devis) ne sont PAS dans la BDD structurée,
  elles sont dans les documents/contrats → TOUJOURS utiliser search_documents pour ces questions

- send_email: Générer et envoyer emails (première génération de brouillon)
  Exemples: "Envoyer email aux copropriétaires", "Alerter pour urgence", "Convocation AG", "Préviens les voisins", "Répondons à", "Contact les copropriétaires", "Contacte les pour", "Informe-les", "Avertir de"

- confirm_email: Confirmer l'envoi d'un email après révision du brouillon
  Exemples: "Envoyer cet email", "Oui envoie", "OK envoie", "Valider l'envoi", "Confirmer"

- request_quotes: Demander devis aux fournisseurs (workflow automatique sans email)
  Exemples: "Lancer workflow devis", "Déclencher demande devis automatique"

  NOTE: Si l'utilisateur dit "contacte les X pour demander un devis" → utiliser send_email (pas request_quotes)

- analyze_document: Analyser NOUVEAU document uploadé MAINTENANT (OCR, extraction données)
  Exemples: Détecté UNIQUEMENT si fichier ATTACHÉ dans le context actuel

  NOTE IMPORTANTE: Si pas de fichier attaché mais mention de nom de fichier → search_documents (pas analyze_document)

- generate_digest: Générer digest quotidien/hebdomadaire des emails
  Exemples: "Générer le digest", "Digest des emails", "Résumé emails", "Mail digest"

- trigger_workflow: Déclencher workflow N8N spécifique
  Exemples: "Créer brouillon Gmail", "Lancer workflow facturation", "Déclencher alerte SMS"

- general_question: Question générale assistant
  Exemples: "Comment ça marche?", "Aide-moi", "Qu'est-ce que tu peux faire?"

MESSAGE UTILISATEUR:
"{user_input}"

CONTEXTE:
{context if context else "Aucun"}

Réponds UNIQUEMENT avec le nom de la catégorie (ex: query_data), sans explication.
"""

        try:
            response = await self.llm_service.generate_response(
                prompt=classification_prompt,
                max_tokens=20,
                temperature=0.1
            )

            # Clean response
            intent_str = response.strip().lower().replace('"', '').replace("'", "")

            # Map to IntentType
            intent_mapping = {
                "query_data": IntentType.QUERY_DATA,
                "search_documents": IntentType.SEARCH_DOCUMENTS,
                "send_email": IntentType.SEND_EMAIL,
                "confirm_email": IntentType.CONFIRM_EMAIL,
                "request_quotes": IntentType.REQUEST_QUOTES,
                "analyze_document": IntentType.ANALYZE_DOCUMENT,
                "generate_digest": IntentType.GENERATE_DIGEST,
                "trigger_workflow": IntentType.TRIGGER_WORKFLOW,
                "general_question": IntentType.GENERAL_QUESTION,
            }

            intent = intent_mapping.get(intent_str, IntentType.GENERAL_QUESTION)

            logger.info("intention_classified", user_input=user_input[:50], intent=intent.value)
            return intent

        except Exception as e:
            logger.error("intention_classification_failed", error=str(e))
            return IntentType.GENERAL_QUESTION

    async def process(
        self,
        user_input: str,
        db: AsyncSession,
        context: Dict[str, Any] = None,
        conversation_history: List[Dict[str, str]] = None,
        thought_stream: ThoughtStream = None,
        state_manager = None
    ) -> AgentResponse:
        """
        Main orchestration method - routes to appropriate agents

        Args:
            user_input: User's message
            db: Database session
            context: Optional context (files, metadata)
            conversation_history: Previous messages

        Returns:
            AgentResponse with results
        """
        try:
            # Thought 1: Analyzing request
            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.ANALYZING,
                    title="Analyse de la demande",
                    content=f"Je commence par analyser votre demande : « {user_input[:100]}... »",
                    agent="orchestrator",
                    progress=0.1
                )

            # 1. Resolve document references ("le doc", "ce fichier", etc.)
            original_user_input = user_input
            if state_manager and state_manager.state.last_uploaded_documents:
                # Detect references to documents without specific names
                doc_keywords = [
                    ("le doc", "le document"),
                    ("ce doc", "ce document"),
                    ("le fichier", "ce fichier"),
                    ("le dernier doc", "dernier document", "last document"),
                    ("ce pdf", "le pdf")
                ]

                user_input_lower = user_input.lower()
                has_doc_reference = any(
                    any(kw in user_input_lower for kw in keyword_group)
                    for keyword_group in doc_keywords
                )

                if has_doc_reference:
                    # Get most recent document
                    last_doc = state_manager.state.last_uploaded_documents[0]
                    doc_filename = last_doc["filename"]

                    # Replace generic references with actual filename
                    replacements = {
                        "le doc": doc_filename,
                        "ce doc": doc_filename,
                        "le document": doc_filename,
                        "ce document": doc_filename,
                        "le fichier": doc_filename,
                        "ce fichier": doc_filename,
                        "le dernier doc": doc_filename,
                        "dernier document": doc_filename,
                        "ce pdf": doc_filename,
                        "le pdf": doc_filename
                    }

                    for old_ref, new_ref in replacements.items():
                        user_input = user_input.replace(old_ref, new_ref)
                        user_input = user_input.replace(old_ref.capitalize(), new_ref)

                    logger.info("document_reference_resolved",
                               original=original_user_input,
                               resolved=user_input,
                               filename=doc_filename)

            # 2. Classify intention
            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.CLASSIFYING,
                    title="Classification de l'intention",
                    content="Je détermine quel type d'action est nécessaire (requête de données, recherche documentaire, génération d'email, etc.)",
                    agent="orchestrator",
                    progress=0.2
                )

            intent = await self.classify_intention(user_input, context)

            logger.info("processing_request", intent=intent.value, input=user_input[:50])

            # Thought 2: Planning
            if thought_stream:
                intent_descriptions = {
                    IntentType.QUERY_DATA: "requête de données structurées → SQL Agent",
                    IntentType.SEARCH_DOCUMENTS: "recherche documentaire → RAG Agent",
                    IntentType.SEND_EMAIL: "génération et envoi d'email → Email + Workflow Agents",
                    IntentType.REQUEST_QUOTES: "demande de devis → SQL + Template + Workflow Agents",
                    IntentType.ANALYZE_DOCUMENT: "analyse de document → OCR Agent",
                    IntentType.TRIGGER_WORKFLOW: "déclenchement de workflow → Workflow Agent",
                    IntentType.GENERAL_QUESTION: "question générale → LLM"
                }
                await thought_stream.add_thought(
                    ThoughtType.PLANNING,
                    title="Plan d'action",
                    content=f"J'ai identifié votre intention : **{intent.value}**\n\nJe vais utiliser : {intent_descriptions.get(intent, 'agents appropriés')}",
                    agent="orchestrator",
                    data={"intent": intent.value},
                    progress=0.3
                )

            # 2. Route to appropriate agent(s)
            if intent == IntentType.QUERY_DATA:
                return await self._handle_query_data(user_input, db, state_manager)

            elif intent == IntentType.SEARCH_DOCUMENTS:
                return await self._handle_search_documents(user_input, db, state_manager)

            elif intent == IntentType.SEND_EMAIL:
                return await self._handle_send_email_intelligent(
                    user_input, db, context, thought_stream, state_manager
                )

            elif intent == IntentType.CONFIRM_EMAIL:
                return await self._handle_confirm_email(user_input, context, db)

            elif intent == IntentType.REQUEST_QUOTES:
                return await self._handle_request_quotes(user_input, db)

            elif intent == IntentType.ANALYZE_DOCUMENT:
                return await self._handle_analyze_document(user_input, context, db)

            elif intent == IntentType.GENERATE_DIGEST:
                return await self._handle_generate_digest(user_input, db)

            elif intent == IntentType.TRIGGER_WORKFLOW:
                return await self._handle_trigger_workflow(user_input, db)

            else:  # GENERAL_QUESTION
                return await self._handle_general_question(user_input, conversation_history)

        except Exception as e:
            logger.error("orchestrator_processing_failed", error=str(e), exc_info=True)
            return AgentResponse(
                success=False,
                message=f"Désolé, une erreur s'est produite : {str(e)}",
                agents_used=["orchestrator"]
            )

    async def _requires_recipient_lookup(self, user_input: str, context: Dict[str, Any] = None) -> bool:
        """
        Determine if we need to lookup recipients from database before sending email

        Examples requiring lookup:
        - "envoyer mail aux copropriétaires des mimosas"
        - "contacter les chauffagistes"
        - "prévenir tous les copropriétaires"
        - "envoie un mail aux chauffagistes"
        - "envoie un mail a nathalie girard et olivier bonnet"

        Examples NOT requiring lookup (recipients already in context):
        - "envoie lui un mail" (when emails_available in context)
        - "les destinataires sont..." (explicit modification)
        """
        user_lower = user_input.lower()

        # If we already have recipients in context, no lookup needed
        if context and context.get("emails_available"):
            # Unless user explicitly mentions a NEW group or NEW specific names
            new_group_keywords = ["copropriétaire", "chauffagiste", "plombier", "professionnel", "voisin", "électricien", "menuisier", "peintre"]
            # Check for potential names (capital letters pattern suggesting proper nouns)
            has_new_names = any(word[0].isupper() and len(word) > 2 for word in user_input.split() if word not in ["Madame", "Monsieur", "Mme", "M"])

            if not any(keyword in user_lower for keyword in new_group_keywords) and not has_new_names:
                return False

        # Profession keywords that indicate database lookup
        profession_keywords = ["chauffagiste", "plombier", "électricien", "menuisier", "peintre", "jardinier", "serrurier", "maçon"]
        has_profession = any(prof in user_lower for prof in profession_keywords)

        # Email action keywords
        email_actions = ["mail", "email", "contacter", "contact", "envoyer", "envoie", "prévenir", "prevenir", "informer", "envoie"]
        has_email_action = any(action in user_lower for action in email_actions)

        # Check for specific names pattern (looking for "à/a [Name] [Name]" or "aux [Name] [Name]")
        import re
        name_pattern = r'\b(à|a|aux)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        has_specific_names = bool(re.search(name_pattern, user_input))

        # Check for patterns that require database lookup
        requires_lookup_patterns = [
            # Specific names mentioned
            has_specific_names and has_email_action,
            # Copropriétaires patterns
            "copropriétaire" in user_lower and (
                "mimosas" in user_lower or
                "tous" in user_lower or
                "de la" in user_lower or
                "du " in user_lower or
                "des " in user_lower
            ),
            # Professional patterns
            has_profession and has_email_action,
            # "Tous les" pattern
            "tous les" in user_lower and ("copropriétaire" in user_lower or has_profession),
            # "aux [group]" pattern
            "aux " in user_lower and ("copropriétaire" in user_lower or has_profession),
        ]

        result = any(requires_lookup_patterns)
        if result:
            logger.info("recipient_lookup_required", user_input=user_input[:50], has_names=has_specific_names)
        return result

    async def _handle_query_data(self, user_input: str, db: AsyncSession, state_manager=None) -> AgentResponse:
        """Handle SQL data queries and store results in context"""
        # Import here to avoid circular imports
        from .sql_agent import SQLAgent

        # Check if user is asking to filter by relevant professions based on context
        user_lower = user_input.lower()
        filter_keywords = ["filtre", "filter", "concerné", "concerne", "métier", "profession"]
        is_filter_request = any(keyword in user_lower for keyword in filter_keywords)

        enriched_input = user_input

        # If filtering and we have business context, enrich the query
        if is_filter_request and state_manager:
            state = state_manager.get_state()
            relevant_professions = state.get_relevant_professions()

            if relevant_professions:
                # Enrich query with relevant professions
                enriched_input = f"{user_input} (professions pertinentes: {', '.join(relevant_professions)})"
                logger.info("query_enriched_with_professions",
                           original=user_input[:50],
                           professions=relevant_professions)

        sql_agent = SQLAgent()
        result = await sql_agent.process(enriched_input, db)

        # Store SQL results in response data for context persistence
        response_data = result.get("data", {})
        if result.get("success") and response_data.get("results"):
            # Extract emails from results for potential email sending
            emails_found = []
            for row in response_data.get("results", []):
                if "email" in row and row["email"]:
                    emails_found.append(row["email"])

            if emails_found:
                response_data["emails_available"] = emails_found
                logger.info("emails_extracted_from_query", count=len(emails_found))

            # Store entities in state_manager for contextual reference resolution
            if state_manager and response_data.get("results"):
                results = response_data.get("results", [])

                # Determine query type based on columns
                if results and len(results) > 0:
                    first_row = results[0]
                    if "prenom" in first_row and "nom" in first_row:
                        # People query
                        state_manager.get_state().set_last_query_entities(results, "people")
                        logger.info("stored_query_entities_in_state", type="people", count=len(results))
                    elif "name" in first_row and "category" in first_row:
                        # Professionals query
                        state_manager.get_state().set_last_query_entities(results, "professionals")
                        logger.info("stored_query_entities_in_state", type="professionals", count=len(results))
                    elif "nom" in first_row and "nombre_coproprietaires" in first_row:
                        # Properties query
                        state_manager.get_state().set_last_query_entities(results, "properties")
                        logger.info("stored_query_entities_in_state", type="properties", count=len(results))

        return AgentResponse(
            success=result["success"],
            message=result["message"],
            data=response_data,
            agents_used=["sql_agent"],
            confidence=result.get("confidence", 1.0),
            suggestions=[
                "Envoyer un email à ces personnes",
                "Obtenir plus de détails",
                "Exporter les résultats"
            ] if result.get("success") and response_data.get("results") else []
        )

    async def _handle_search_documents(self, user_input: str, db: AsyncSession, state_manager = None) -> AgentResponse:
        """
        Handle document search via RAG with HYBRID SQL+RAG intelligence

        NEW v2.0: Uses Intent Classifier to determine if query needs:
        - RAG only
        - SQL only
        - HYBRID (both SQL + RAG with fusion)

        This provides the most comprehensive answers by combining
        structured data (SQL) with unstructured knowledge (RAG).
        """
        try:
            logger.info("handling_search_with_hybrid_intelligence", query=user_input[:50])

            # Step 1: Classify with v2.0 Intent Classifier (SQL vs RAG vs HYBRID)
            classification = await self.intent_classifier_v2.classify_with_confidence(
                query=user_input,
                context={
                    "has_uploaded_documents": True,  # Assume docs exist if called
                    "last_query_was_rag": True  # Coming from SEARCH_DOCUMENTS intent
                }
            )

            logger.info("intent_classification_v2",
                       query=user_input[:50],
                       intent=classification.intent.value,
                       confidence=classification.confidence,
                       sql_score=classification.sql_score,
                       rag_score=classification.rag_score)

            # Step 2: Handle AMBIGUOUS case (request clarification)
            if classification.intent.value == "AMBIGUOUS":
                return self._handle_ambiguous_query(user_input, classification)

            # Step 3: Execute based on classified intent
            hybrid_result = await self.hybrid_executor.execute_hybrid(
                query=user_input,
                db=db,
                state_manager=state_manager,
                intent=classification.intent.value
            )

            logger.info("hybrid_execution_completed",
                       has_sql=hybrid_result.has_sql,
                       has_rag=hybrid_result.has_rag,
                       needs_fusion=hybrid_result.needs_fusion)

            # Step 4: Fuse results if HYBRID
            if hybrid_result.needs_fusion:
                logger.info("fusing_sql_and_rag_results")
                fused = await self.fusion_agent.fuse_responses(user_input, hybrid_result)

                return AgentResponse(
                    success=True,
                    message=fused.text,
                    data={
                        "fusion_strategy": fused.fusion_strategy,
                        "has_contradictions": fused.has_contradictions,
                        "contradiction_note": fused.contradiction_note,
                        "sources": fused.sources,
                        "sql_result": hybrid_result.sql_result.dict() if hybrid_result.sql_result else None,
                        "rag_result": hybrid_result.rag_result.dict() if hybrid_result.rag_result else None
                    },
                    agents_used=["intent_classifier_v2", "hybrid_executor", "sql_agent", "rag_agent", "synthesis_agent", "fusion_agent"],
                    confidence=fused.confidence
                )

            # Step 5: Return SQL-only or RAG-only result
            elif hybrid_result.has_sql and not hybrid_result.has_rag:
                # SQL only
                fused = await self.fusion_agent.fuse_responses(user_input, hybrid_result)
                return AgentResponse(
                    success=True,
                    message=fused.text,
                    data={"sources": fused.sources},
                    agents_used=["intent_classifier_v2", "sql_agent"],
                    confidence=fused.confidence
                )

            elif hybrid_result.has_rag and not hybrid_result.has_sql:
                # RAG only
                fused = await self.fusion_agent.fuse_responses(user_input, hybrid_result)
                return AgentResponse(
                    success=True,
                    message=fused.text,
                    data={
                        "sources": fused.sources,
                        "has_contradictions": fused.has_contradictions
                    },
                    agents_used=["intent_classifier_v2", "rag_agent", "synthesis_agent"],
                    confidence=fused.confidence
                )

            else:
                # Neither (empty result) - IMPROVED MESSAGE
                logger.warning("no_results_found",
                             query=user_input[:50],
                             has_sql=hybrid_result.has_sql,
                             has_rag=hybrid_result.has_rag)

                return AgentResponse(
                    success=True,
                    message=(
                        "Je n'ai trouvé aucune information pertinente pour répondre à votre question.\n\n"
                        "**Suggestions** :\n"
                        "1. Vérifiez que des documents sont bien uploadés dans le panneau de droite\n"
                        "2. Reformulez votre question avec d'autres mots\n"
                        "3. Précisez le contexte (noms, dates, catégories)\n\n"
                        "Si vous cherchez dans les documents, assurez-vous qu'ils contiennent l'information recherchée."
                    ),
                    agents_used=["intent_classifier_v2", "hybrid_executor"],
                    confidence=0.0,
                    suggestions=[
                        "Afficher les documents disponibles",
                        "Reformuler la question",
                        "Chercher dans la base de données"
                    ]
                )

        except Exception as e:
            logger.error("hybrid_search_failed", error=str(e), exc_info=True)
            return AgentResponse(
                success=False,
                message=f"Erreur lors de la recherche : {str(e)}",
                agents_used=["orchestrator"]
            )

    def _handle_ambiguous_query(self, query: str, classification) -> AgentResponse:
        """
        Handle ambiguous queries by requesting clarification

        Returns options to the user to clarify their intent
        """
        options = classification.clarification_options or [
            "Consulter la base de données",
            "Chercher dans les documents",
            "Les deux"
        ]

        message_parts = [
            f"Je peux vous aider de plusieurs façons avec : « {query} »\n",
            "\n**Choisissez une option** :\n"
        ]

        for i, option in enumerate(options, 1):
            message_parts.append(f"{i}. {option}\n")

        message_parts.append("\nQue souhaitez-vous ?")

        return AgentResponse(
            success=True,
            message="".join(message_parts),
            data={
                "clarification_needed": True,
                "options": options,
                "sql_score": classification.sql_score,
                "rag_score": classification.rag_score
            },
            agents_used=["intent_classifier_v2"],
            confidence=classification.confidence,
            suggestions=options
        )

    async def _handle_send_email_intelligent(
        self,
        user_input: str,
        db: AsyncSession,
        context: Dict[str, Any] = None,
        thought_stream = None,
        state_manager = None
    ) -> AgentResponse:
        """
        Intelligent email handling with entity extraction and query planning

        Flow:
        1. Extract entities (persons, groups, actions)
        2. Create execution plan
        3. Execute plan steps
        4. Return result with human-in-the-loop confirmation
        """
        from .entity_extractor import EntityExtractor
        from .query_planner import QueryPlanner
        from sqlalchemy import text

        try:
            # Step 1: Extract entities (with state_manager for contextual reference resolution)
            extractor = EntityExtractor(state_manager=state_manager)
            entities = extractor.extract(user_input)

            logger.info("entities_extracted_for_email",
                       persons=len(entities.persons),
                       groups=len(entities.groups),
                       actions=len(entities.actions))

            # Debug: log entity details
            for i, person in enumerate(entities.persons):
                logger.info(f"person_{i}", prenom=person.prenom, nom=person.nom, full_name=person.full_name)

            # Emit thought about entity extraction
            if thought_stream:
                entity_summary = []
                if entities.persons:
                    entity_summary.append(f"{len(entities.persons)} personne(s)")
                if entities.groups:
                    entity_summary.append(f"{len(entities.groups)} groupe(s)")

                await thought_stream.add_thought(
                    ThoughtType.ANALYZING,
                    title="Analyse de la demande",
                    content=f"J'ai identifié: {', '.join(entity_summary) if entity_summary else 'aucune entité spécifique'}",
                    agent="orchestrator",
                    progress=0.2
                )

            # Step 2: Create execution plan
            planner = QueryPlanner()
            plan = planner.create_plan(entities, user_input, context)

            logger.info("execution_plan_created",
                       steps=plan.total_steps,
                       confidence=plan.confidence)

            # Step 3: Execute plan
            recipients_found = []

            # Execute SQL query if needed
            for i, step in enumerate(plan.steps):
                if step.step_type.value == "sql_query":
                    # Emit thought
                    if thought_stream:
                        await thought_stream.add_thought(
                            ThoughtType.EXECUTING,
                            title="Recherche des destinataires",
                            content=step.description,
                            agent="orchestrator",
                            progress=0.3 + (i * 0.2)
                        )

                    # Execute SQL query
                    try:
                        result = await db.execute(text(step.query))
                        rows = result.fetchall()

                        if rows:
                            columns = result.keys()
                            results_dicts = [dict(zip(columns, row)) for row in rows]

                            # Extract emails
                            for row_dict in results_dicts:
                                if "email" in row_dict and row_dict["email"]:
                                    email_value = str(row_dict["email"])  # Ensure it's a string
                                    recipients_found.append(email_value)

                            logger.info("recipients_found_from_sql", count=len(recipients_found), recipients=recipients_found[:3])

                            # Emit success thought
                            if thought_stream:
                                await thought_stream.add_thought(
                                    ThoughtType.ANALYZING,
                                    title="Destinataires trouvés",
                                    content=f"✓ {len(recipients_found)} destinataire(s) trouvé(s): {', '.join(recipients_found[:3])}{'...' if len(recipients_found) > 3 else ''}",
                                    agent="orchestrator",
                                    progress=0.5
                                )

                    except Exception as e:
                        logger.error("sql_execution_failed", error=str(e), query=step.query)
                        # Continue without recipients

            # Update context with found recipients
            if recipients_found:
                if not context:
                    context = {}
                context["emails_available"] = recipients_found

            # Step 4: Generate email draft
            return await self._handle_send_email(user_input, db, context)

        except Exception as e:
            logger.error("intelligent_email_handling_failed", error=str(e), exc_info=True)
            # Fallback to standard email handling
            return await self._handle_send_email(user_input, db, context)

    async def _handle_send_email(self, user_input: str, db: AsyncSession, context: Dict[str, Any] = None) -> AgentResponse:
        """
        Handle email generation with human-in-the-loop validation

        Shows draft first, then asks for validation before sending
        Uses emails from previous SQL query if available
        """
        from .email_agent import EmailAgent

        email_agent = EmailAgent()
        agents_used = []

        # Extract emails from context if available (from previous SQL query)
        recipients_from_context = []
        if context and "emails_available" in context:
            recipients_from_context = context["emails_available"]
            logger.info("recipients_found_in_context", count=len(recipients_from_context))

        # Enrich user input with context information
        enriched_input = user_input

        # Add topic/subject if available from context (for modifications)
        if context and "topic" in context:
            enriched_input = f"{user_input}\n\nSujet principal: {context['topic']}"
            logger.info("email_enriched_with_topic", topic=context["topic"])

        # Add business context if available
        if context and "business_context" in context:
            business_ctx = context["business_context"]
            ctx_parts = []
            if "incident_type" in business_ctx:
                ctx_parts.append(f"Type d'incident: {business_ctx['incident_type']}")
            if "urgency" in business_ctx:
                ctx_parts.append(f"Urgence: {business_ctx['urgency']}")
            if ctx_parts:
                enriched_input += f"\n\nContexte: {', '.join(ctx_parts)}"
                logger.info("email_enriched_with_business_context", context=business_ctx)

        # Add recipient info if found
        if recipients_from_context:
            enriched_input += f"\n\nDestinataires suggérés: {', '.join(recipients_from_context)}"

        # Step 1: Generate email draft
        email_draft = await email_agent.generate_email(enriched_input, db)
        agents_used.append("email_agent")

        # If draft doesn't have recipients but we have some from context, add them
        if email_draft.get("success") and recipients_from_context:
            draft_data = email_draft.get("data", {})
            if not draft_data.get("recipients") or draft_data.get("recipients") == ["Non spécifiés"]:
                draft_data["recipients"] = recipients_from_context
                email_draft["data"] = draft_data
                logger.info("recipients_auto_populated", count=len(recipients_from_context))

        if not email_draft["success"]:
            return AgentResponse(
                success=False,
                message=email_draft["message"],
                agents_used=agents_used
            )

        # Extract draft details
        draft_data = email_draft.get("data", {})
        recipients = draft_data.get("recipients", [])
        subject = draft_data.get("subject", "Sans objet")
        body = draft_data.get("body", "")

        # Format preview message
        message_parts = [
            "📧 **Brouillon d'email généré**\n",
            f"\n**Destinataires:** {', '.join(recipients) if recipients else 'Non spécifiés'}",
            f"\n**Objet:** {subject}",
            f"\n\n**Message:**\n```\n{body}\n```\n",
            "\n---",
            "\n**⚠️ Cet email n'a PAS été envoyé.**",
            "\n\nPour l'envoyer, veuillez confirmer en répondant:",
            "\n- ✅ \"Envoyer cet email\"",
            "\n- ✏️ \"Modifier le sujet\" ou \"Modifier le message\"",
            "\n- ❌ \"Annuler\""
        ]

        return AgentResponse(
            success=True,
            message="".join(message_parts),
            data={
                "email_draft": draft_data,
                "awaiting_confirmation": True,
                "draft_id": draft_data.get("draft_id")
            },
            agents_used=agents_used,
            suggestions=[
                "✅ Envoyer cet email",
                "✏️ Modifier l'objet",
                "✏️ Modifier le message",
                "❌ Annuler"
            ]
        )

    async def _handle_confirm_email(
        self,
        user_input: str,
        context: Dict[str, Any],
        db: AsyncSession
    ) -> AgentResponse:
        """
        Handle email sending confirmation after draft review

        Requires draft data in context from previous interaction
        """
        from .workflow_agent import WorkflowAgent

        # Check if we have draft data in context
        if not context or "email_draft" not in context:
            return AgentResponse(
                success=False,
                message="❌ Je n'ai pas de brouillon d'email en attente. Veuillez d'abord générer un brouillon avec une commande comme 'Envoyer email à [destinataire]'.",
                agents_used=["orchestrator"],
                suggestions=[
                    "Envoyer email aux copropriétaires",
                    "Prévenir les voisins",
                    "Répondre à un email"
                ]
            )

        draft_data = context["email_draft"]
        workflow_agent = WorkflowAgent()

        try:
            # Trigger N8N workflow to send email
            workflow_result = await workflow_agent.trigger_email_draft(draft_data)

            if workflow_result["success"]:
                return AgentResponse(
                    success=True,
                    message=f"✅ **Email envoyé avec succès!**\n\n{workflow_result['message']}",
                    data=workflow_result.get("data"),
                    agents_used=["workflow_agent"],
                    suggestions=[
                        "Voir mes emails envoyés",
                        "Envoyer un autre email"
                    ]
                )
            else:
                return AgentResponse(
                    success=False,
                    message=f"❌ **Échec de l'envoi de l'email**\n\n{workflow_result['message']}\n\nVoulez-vous réessayer ?",
                    data=workflow_result.get("data"),
                    agents_used=["workflow_agent"],
                    suggestions=[
                        "Réessayer",
                        "Modifier le brouillon",
                        "Annuler"
                    ]
                )

        except Exception as e:
            logger.error("email_confirmation_failed", error=str(e), exc_info=True)
            return AgentResponse(
                success=False,
                message=f"❌ Une erreur s'est produite lors de l'envoi : {str(e)}",
                agents_used=["workflow_agent"]
            )

    async def _handle_request_quotes(self, user_input: str, db: AsyncSession) -> AgentResponse:
        """Handle vendor quote requests"""
        from .sql_agent import SQLAgent
        from .template_agent import TemplateAgent
        from .workflow_agent import WorkflowAgent

        sql_agent = SQLAgent()
        template_agent = TemplateAgent()
        workflow_agent = WorkflowAgent()

        agents_used = []

        # Step 1: Get relevant vendors from DB
        vendor_query = f"Extract vendor information for: {user_input}"
        vendors_result = await sql_agent.process(vendor_query, db)
        agents_used.append("sql_agent")

        if not vendors_result["success"]:
            return AgentResponse(
                success=False,
                message="Je n'ai pas pu trouver de fournisseurs correspondants.",
                agents_used=agents_used
            )

        # Step 2: Generate quote request template
        template_result = await template_agent.fill_template(
            template_name="demande_devis",
            user_request=user_input,
            context=vendors_result.get("data")
        )
        agents_used.append("template_agent")

        # Step 3: Trigger N8N workflow for bulk quote requests
        workflow_result = await workflow_agent.trigger_bulk_quotes(
            vendors=vendors_result.get("data", {}).get("vendors", []),
            message=template_result["message"]
        )
        agents_used.append("workflow_agent")

        return AgentResponse(
            success=workflow_result["success"],
            message=workflow_result["message"],
            data=workflow_result.get("data"),
            agents_used=agents_used
        )

    async def _handle_analyze_document(
        self,
        user_input: str,
        context: Dict[str, Any],
        db: AsyncSession
    ) -> AgentResponse:
        """Handle document analysis with OCR"""
        from .ocr_agent import OCRAgent

        # Check if file is in context
        if not context or "file" not in context:
            return AgentResponse(
                success=False,
                message="Veuillez uploader un document (PDF ou image) pour que je puisse l'analyser.",
                agents_used=["orchestrator"],
                suggestions=["Uploadez une facture, un contrat, ou tout autre document"]
            )

        file_data = context["file"]

        ocr_agent = OCRAgent()
        result = await ocr_agent.process(
            file_content=file_data["content"],
            filename=file_data["filename"],
            content_type=file_data["content_type"],
            db=db,
            user_context={"message": user_input}
        )

        return AgentResponse(
            success=result["success"],
            message=result["message"],
            data=result.get("data"),
            agents_used=["ocr_agent"],
            suggestions=[
                "Rechercher des documents similaires",
                "Extraire les montants de toutes les factures",
                "Trouver le contrat avec ce fournisseur"
            ]
        )

    async def _handle_generate_digest(self, user_input: str, db: AsyncSession) -> AgentResponse:
        """Handle email digest generation and queries - reads from database"""
        try:
            # Import digest service
            from app.api.endpoints.digest import generate_digest, DigestGenerateRequest

            # Check if user wants specific details
            user_input_lower = user_input.lower()

            # Keywords for digest interactions
            show_urgent = any(keyword in user_input_lower for keyword in [
                "urgent", "urgents", "prioritaire", "prioritaires", "critique"
            ])
            show_important = any(keyword in user_input_lower for keyword in [
                "important", "importants"
            ])
            show_routine = any(keyword in user_input_lower for keyword in [
                "routin", "routine", "routinier", "routiniers", "normal", "normaux"
            ])
            show_content = any(keyword in user_input_lower for keyword in [
                "contenu", "content", "détail", "detail", "lire", "voir", "affiche",
                "montre", "donne", "corps", "body", "texte", "message"
            ])

            logger.info("generating_digest_from_db",
                        show_urgent=show_urgent,
                        show_important=show_important,
                        show_routine=show_routine,
                        show_content=show_content)

            request = DigestGenerateRequest(since_hours=24, max_emails=100)
            digest_result = await generate_digest(request=request, db=db)

            # digest_result is a dict
            if digest_result and isinstance(digest_result, dict):
                urgent_emails = digest_result.get('urgent', {}).get('emails', [])
                important_emails = digest_result.get('important', {}).get('emails', [])
                routine_emails = digest_result.get('routine', {}).get('emails', [])

                urgent_count = len(urgent_emails)
                important_count = len(important_emails)
                routine_count = len(routine_emails)
                total = digest_result.get('total_emails', 0)

                # Handle specific queries
                if show_urgent and (show_content or "contenu" in user_input_lower or "détail" in user_input_lower):
                    # Show detailed urgent emails
                    return self._format_detailed_emails(urgent_emails, "🔴 Emails Urgents", "digest_agent")

                elif show_important and (show_content or "quels" in user_input_lower or "liste" in user_input_lower):
                    # Show detailed important emails
                    return self._format_detailed_emails(important_emails, "🟡 Emails Importants", "digest_agent")

                elif show_routine and (show_content or "quels" in user_input_lower or "liste" in user_input_lower):
                    # Show detailed routine emails
                    return self._format_detailed_emails(routine_emails, "🟢 Emails Routiniers", "digest_agent")

                else:
                    # Default: show summary with previews
                    message_parts = [
                        f"📧 **Digest des emails généré** ({total} emails analysés)\n",
                        f"\n🔴 **Urgents**: {urgent_count}",
                        f"\n🟡 **Importants**: {important_count}",
                        f"\n🟢 **Routiniers**: {routine_count}\n"
                    ]

                    # Add ALL urgent emails (not just first 3)
                    if urgent_emails:
                        message_parts.append("\n**Emails urgents:**")
                        for i, email in enumerate(urgent_emails, 1):
                            subject = email.get('subject', 'Sans objet')
                            sender = email.get('sender', 'Inconnu')
                            message_parts.append(f"\n{i}. {subject} (de {sender})")

                    # Add preview of important emails
                    if important_emails:
                        message_parts.append("\n\n**Emails importants (aperçu):**")
                        for i, email in enumerate(important_emails[:3], 1):
                            subject = email.get('subject', 'Sans objet')
                            sender = email.get('sender', 'Inconnu')
                            message_parts.append(f"\n{i}. {subject} (de {sender})")
                        if len(important_emails) > 3:
                            message_parts.append(f"\n... et {len(important_emails) - 3} autre(s)")

                    return AgentResponse(
                        success=True,
                        message="".join(message_parts),
                        data={
                            "urgent_count": urgent_count,
                            "important_count": important_count,
                            "routine_count": routine_count,
                            "digest": digest_result
                        },
                        agents_used=["digest_agent"],
                        suggestions=[
                            "Voir le contenu des emails urgents",
                            "Quels sont les emails importants ?",
                            "Afficher les emails routiniers"
                        ]
                    )
            else:
                return AgentResponse(
                    success=True,
                    message="Aucun nouveau email trouvé dans les dernières 24 heures.",
                    agents_used=["digest_agent"]
                )

        except Exception as e:
            logger.error("digest_generation_failed", error=str(e), exc_info=True)
            return AgentResponse(
                success=False,
                message=f"Erreur lors de la génération du digest: {str(e)}",
                agents_used=["digest_agent"]
            )

    def _format_detailed_emails(self, emails: List[Dict[str, Any]], title: str, agent_name: str) -> AgentResponse:
        """
        Format emails with full details

        Args:
            emails: List of email dictionaries
            title: Section title (e.g., "🔴 Emails Urgents")
            agent_name: Name of the agent for tracking

        Returns:
            AgentResponse with formatted email details
        """
        if not emails:
            return AgentResponse(
                success=True,
                message=f"{title}\n\nAucun email dans cette catégorie.",
                agents_used=[agent_name]
            )

        message_parts = [f"## {title}\n\n**Total: {len(emails)} emails**\n"]

        for i, email in enumerate(emails, 1):
            subject = email.get('subject', 'Sans objet')
            sender = email.get('sender', 'Inconnu')
            body = email.get('body', 'Pas de contenu disponible')
            received_at = email.get('received_at', 'Date inconnue')

            # Truncate body if too long
            body_preview = body[:500] + "..." if len(body) > 500 else body

            message_parts.append(f"\n---\n")
            message_parts.append(f"\n### {i}. {subject}")
            message_parts.append(f"\n**De:** {sender}")
            message_parts.append(f"\n**Reçu:** {received_at}")
            message_parts.append(f"\n\n**Message:**\n{body_preview}\n")

        return AgentResponse(
            success=True,
            message="".join(message_parts),
            data={"emails": emails, "count": len(emails)},
            agents_used=[agent_name],
            suggestions=[
                "Répondre à ces emails",
                "Marquer comme traités",
                "Voir le digest complet"
            ]
        )

    async def _handle_trigger_workflow(self, user_input: str, db: AsyncSession) -> AgentResponse:
        """Handle explicit workflow triggers"""
        from .workflow_agent import WorkflowAgent

        workflow_agent = WorkflowAgent()
        result = await workflow_agent.trigger_generic(user_input, {})

        return AgentResponse(
            success=result["success"],
            message=result["message"],
            agents_used=["workflow_agent"]
        )

    async def _handle_general_question(
        self,
        user_input: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> AgentResponse:
        """Handle general assistant questions"""
        try:
            # Build context from conversation history
            context = ""
            if conversation_history:
                context = "\n".join([
                    f"{msg['role']}: {msg['content']}"
                    for msg in conversation_history[-5:]  # Last 5 messages
                ])

            prompt = f"""
Tu es l'assistant DisruptIQ, un assistant intelligent pour syndics de copropriété.

TES CAPACITÉS:
- Requêter les données (copropriétaires, copropriétés, fournisseurs)
- Chercher dans les documents (contrats, règlements, procédures)
- Générer et envoyer des emails
- Demander des devis aux fournisseurs
- Analyser des documents (factures, contrats)
- Déclencher des workflows automatisés

HISTORIQUE:
{context if context else "Aucun"}

QUESTION:
{user_input}

Réponds de manière claire, professionnelle et utile. Si tu peux aider avec une action spécifique, propose-la.
"""

            response = await self.llm_service.generate_response(
                prompt=prompt,
                max_tokens=500,
                temperature=0.7
            )

            return AgentResponse(
                success=True,
                message=response,
                agents_used=["orchestrator", "llm"],
                suggestions=[
                    "Rechercher dans mes documents",
                    "Voir la liste des copropriétaires",
                    "Générer un email",
                    "Demander un devis"
                ]
            )

        except Exception as e:
            logger.error("general_question_failed", error=str(e))
            return AgentResponse(
                success=False,
                message="Désolé, je n'ai pas pu traiter votre question.",
                agents_used=["orchestrator"]
            )

    def _is_procedural_query(self, query: str) -> bool:
        """
        Detect if query is asking for a procedure/steps/actions

        Args:
            query: User's question

        Returns:
            True if the query is procedural (asking "how to" or "what to do")
        """
        procedural_keywords = [
            "how to", "comment", "procédure", "étapes", "steps",
            "what to do", "que faire", "marche à suivre", "actions",
            "comment faire", "quoi faire", "procedure", "démarche"
        ]
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in procedural_keywords)

    async def _format_as_action_list(
        self,
        query: str,
        results: List[Dict[str, Any]]
    ) -> str:
        """
        Format RAG results as actionable step-by-step instructions using LLM

        Args:
            query: Original user query
            results: RAG search results with context

        Returns:
            Formatted action list with markdown
        """
        try:
            # Combine context from all results
            context = "\n\n".join([r.get("text", "")[:1000] for r in results])

            # Use LLM to extract and structure steps
            prompt = f"""À partir des documents suivants, extrais et structure les étapes à suivre pour : {query}

DOCUMENTS:
{context}

INSTRUCTIONS:
1. Identifie les actions concrètes à entreprendre
2. Structure-les en liste numérotée claire
3. Utilise des tirets (-) pour les sous-actions si nécessaire
4. Utilise le markdown pour le formatage (** pour gras)
5. Termine par une note si des informations importantes sont manquantes

FORMAT ATTENDU:
## 📋 Actions à suivre

1. **[Action principale]**
   - Sous-action A
   - Sous-action B

2. **[Action suivante]**
   - Details...

**Note:** [Informations complémentaires ou contacts]
"""

            action_list = await self.llm_service.generate_response(
                prompt=prompt,
                max_tokens=800,
                temperature=0.3  # Low temperature for consistent formatting
            )

            # Add sources footer
            sources_text = "\n\n---\n**📚 Sources:**\n" + "\n".join([
                f"- {r.get('metadata', {}).get('title', 'Document')} (pertinence: {r.get('score', 0):.0%})"
                for r in results[:3]
            ])

            return action_list + sources_text

        except Exception as e:
            logger.error("action_list_formatting_failed", error=str(e))
            # Fallback to simple formatting
            return await self._format_as_informational(query, results)

    async def _format_as_informational(self, query: str, results: List[Dict[str, Any]]) -> str:
        """
        Format RAG results as informational (non-procedural queries)

        Uses LLM to synthesize a clear, coherent answer from multiple document chunks.
        Shows discrete source citations at bottom with relevance scores.

        Args:
            query: Original user question
            results: RAG search results

        Returns:
            Formatted informational response with markdown and discrete sources
        """
        try:
            # Combine context from all results
            context = "\n\n".join([
                f"[Source: {r.get('metadata', {}).get('title', 'Document')}]\n{r.get('text', '')[:1000]}"
                for r in results
            ])

            # Use LLM to synthesize a coherent answer
            prompt = f"""À partir des documents suivants, réponds à cette question de manière claire et synthétique : {query}

DOCUMENTS:
{context}

INSTRUCTIONS:
1. Réponds directement à la question de manière naturelle et claire
2. Utilise le markdown pour structurer ta réponse (**, ##, listes si pertinent)
3. Synthétise les informations plutôt que de copier-coller
4. Si plusieurs documents disent la même chose, fusionne l'information
5. Sois concis mais complet
6. N'ajoute PAS de section "Sources" - elle sera ajoutée automatiquement

Réponds uniquement avec le contenu, sans préambule."""

            synthesized_response = await self.llm_service.generate_response(
                prompt=prompt,
                max_tokens=600,
                temperature=0.3  # Low temperature for factual accuracy
            )

            # Format relevance scores with colors/indicators
            def format_score(score: float) -> str:
                """Format score with descriptive text"""
                percentage = int(score * 100)
                if score >= 0.9:
                    return f"{percentage}%"  # Very relevant
                elif score >= 0.7:
                    return f"{percentage}%"  # Relevant
                else:
                    return f"{percentage}%"  # Less relevant

            # Add discrete sources footer
            sources_list = []
            for r in results[:3]:  # Limit to top 3 sources
                title = r.get('metadata', {}).get('title', 'Document')
                score = r.get('score', 0)
                sources_list.append(f"{title} ({format_score(score)})")

            sources_text = "\n\n---\n📄 **Sources :** " + ", ".join(sources_list)

            return synthesized_response.strip() + sources_text

        except Exception as e:
            logger.error("informational_formatting_failed", error=str(e))
            # Fallback to simple list format if LLM fails
            response_parts = ["**Voici ce que j'ai trouvé dans les documents:**\n"]

            for i, doc in enumerate(results, 1):
                title = doc.get('metadata', {}).get('title', 'Document')
                text_preview = doc.get('text', '')[:300]
                score = doc.get('score', 0)

                response_parts.append(f"\n**{i}. {title}** (pertinence: {score:.0%})")
                response_parts.append(f"\n{text_preview}...\n")

            response_parts.append("\n---\n_Sources citées ci-dessus._")
            return "".join(response_parts)

    # =========================================================================
    # PHASE 1 INTEGRATION: Planner + Evaluator + Observability
    # =========================================================================

    async def _create_agent_run(
        self,
        db: AsyncSession,
        conversation_id: str,
        intent: str,
        plan: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Create AgentRun record for observability tracking

        Args:
            db: Database session
            conversation_id: Unique conversation identifier
            intent: Detected intent (SQL_ONLY, RAG_ONLY, HYBRID, etc.)
            plan: Execution plan JSON from Planner DAG

        Returns:
            run_id: ID of created AgentRun
        """
        from sqlalchemy import text
        import json

        try:
            plan_json = json.dumps(plan) if plan else None

            query = text("""
                INSERT INTO agent_runs (conversation_id, intent, plan_json, status, started_at)
                VALUES (:conversation_id, :intent, :plan_json, 'running', NOW())
                RETURNING id
            """)

            result = await db.execute(
                query,
                {
                    "conversation_id": conversation_id,
                    "intent": intent,
                    "plan_json": plan_json
                }
            )
            await db.commit()

            run_id = result.scalar_one()
            logger.info("agent_run_created", run_id=run_id, intent=intent, conversation_id=conversation_id)
            return run_id

        except Exception as e:
            logger.error("agent_run_creation_failed", error=str(e), exc_info=True)
            await db.rollback()
            return None

    async def _log_agent_step(
        self,
        db: AsyncSession,
        run_id: int,
        step_number: int,
        tool: str,
        input_data: Optional[Dict[str, Any]] = None,
        output_data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        latency_ms: Optional[int] = None
    ):
        """
        Log individual agent step for observability

        Args:
            db: Database session
            run_id: AgentRun ID
            step_number: Step number in execution plan
            tool: Tool/skill name (e.g., "sql.execute", "rag.search")
            input_data: Input parameters (hashed for caching)
            output_data: Output results
            error: Error message if step failed
            latency_ms: Execution time in milliseconds
        """
        from sqlalchemy import text
        import json
        import hashlib

        try:
            # Generate input hash for cache lookup
            input_hash = None
            if input_data:
                input_str = json.dumps(input_data, sort_keys=True)
                input_hash = hashlib.sha256(input_str.encode()).hexdigest()

            output_json = json.dumps(output_data) if output_data else None

            query = text("""
                INSERT INTO agent_steps (
                    run_id, step_number, tool, input_hash,
                    output_json, error, latency_ms, executed_at
                )
                VALUES (
                    :run_id, :step_number, :tool, :input_hash,
                    :output_json, :error, :latency_ms, NOW()
                )
            """)

            await db.execute(
                query,
                {
                    "run_id": run_id,
                    "step_number": step_number,
                    "tool": tool,
                    "input_hash": input_hash,
                    "output_json": output_json,
                    "error": error,
                    "latency_ms": latency_ms
                }
            )
            await db.commit()

            logger.info(
                "agent_step_logged",
                run_id=run_id,
                step_number=step_number,
                tool=tool,
                latency_ms=latency_ms,
                has_error=error is not None
            )

        except Exception as e:
            logger.error("agent_step_logging_failed", error=str(e), exc_info=True)
            await db.rollback()

    async def _finalize_agent_run(
        self,
        db: AsyncSession,
        run_id: int,
        status: str,
        cost_tokens: Optional[int] = None,
        citations_json: Optional[Dict] = None,
        has_conflicts: bool = False,
        evaluator_passed: Optional[bool] = None
    ):
        """
        Finalize AgentRun with results and evaluation

        Args:
            db: Database session
            run_id: AgentRun ID
            status: Final status ('success', 'failed', 'partial')
            cost_tokens: Total tokens consumed
            citations_json: Citations/sources used
            has_conflicts: Whether SQL/RAG conflicts detected
            evaluator_passed: Whether evaluation rules passed
        """
        from sqlalchemy import text
        import json

        try:
            citations_str = json.dumps(citations_json) if citations_json else None

            query = text("""
                UPDATE agent_runs
                SET status = :status,
                    cost_tokens = :cost_tokens,
                    citations_json = :citations_json,
                    has_conflicts = :has_conflicts,
                    evaluator_passed = :evaluator_passed,
                    finished_at = NOW()
                WHERE id = :run_id
            """)

            await db.execute(
                query,
                {
                    "run_id": run_id,
                    "status": status,
                    "cost_tokens": cost_tokens,
                    "citations_json": citations_str,
                    "has_conflicts": has_conflicts,
                    "evaluator_passed": evaluator_passed
                }
            )
            await db.commit()

            logger.info(
                "agent_run_finalized",
                run_id=run_id,
                status=status,
                evaluator_passed=evaluator_passed,
                has_conflicts=has_conflicts
            )

        except Exception as e:
            logger.error("agent_run_finalization_failed", error=str(e), exc_info=True)
            await db.rollback()

    async def process_with_plan(
        self,
        user_input: str,
        db: AsyncSession,
        conversation_id: str,
        context: Dict[str, Any] = None,
        conversation_history: List[Dict[str, str]] = None,
        thought_stream: ThoughtStream = None,
        state_manager = None
    ) -> AgentResponse:
        """
        Enhanced processing with Planner DAG + Evaluator + Observability

        This is the Phase 1 integration that adds:
        - Execution plan generation (Planner DAG)
        - Rule-based validation (Evaluator)
        - Complete observability tracking (AgentRun, AgentSteps)

        Flow:
        1. Classify intent
        2. Generate execution plan (Planner DAG)
        3. Create AgentRun for tracking
        4. Execute plan steps (with logging)
        5. Evaluate results (Evaluator)
        6. Finalize AgentRun with evaluation

        Args:
            user_input: User's message
            db: Database session
            conversation_id: Unique conversation identifier
            context: Optional context
            conversation_history: Previous messages
            thought_stream: Real-time thought stream
            state_manager: State manager for context

        Returns:
            AgentResponse with enhanced tracking
        """
        import time

        run_id = None
        start_time = time.time()

        try:
            # Step 1: Classify intent (reuse existing method)
            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.CLASSIFYING,
                    title="Classification de l'intention",
                    content="Je détermine le type d'action nécessaire...",
                    agent="orchestrator",
                    progress=0.1
                )

            intent = await self.classify_intention(user_input, context)

            # Map old IntentType to Phase 1 intents
            intent_map = {
                IntentType.QUERY_DATA: "SQL_ONLY",
                IntentType.SEARCH_DOCUMENTS: "RAG_ONLY",  # Will be refined by classifier_v2
                IntentType.SEND_EMAIL: "EMAIL",
                IntentType.TRIGGER_WORKFLOW: "N8N",
                IntentType.ANALYZE_DOCUMENT: "OCR",
                IntentType.GENERAL_QUESTION: "GENERAL"
            }

            phase1_intent = intent_map.get(intent, "GENERAL")

            # Step 2: Generate execution plan
            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.PLANNING,
                    title="Génération du plan d'exécution",
                    content=f"Je crée un plan structuré pour l'intent **{phase1_intent}**...",
                    agent="planner_dag",
                    progress=0.2
                )

            plan = await self.planner.generate_plan(
                intent=phase1_intent,
                query=user_input,
                context=context
            )

            logger.info(
                "execution_plan_generated",
                intent=phase1_intent,
                steps_count=len(plan.steps),
                estimated_tokens=plan.estimated_tokens
            )

            # Step 3: Create AgentRun for observability
            run_id = await self._create_agent_run(
                db=db,
                conversation_id=conversation_id,
                intent=phase1_intent,
                plan=plan.dict()
            )

            # Step 4: Execute using existing process method
            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.EXECUTING,
                    title="Exécution du plan",
                    content=f"J'exécute {len(plan.steps)} étapes...",
                    agent="orchestrator",
                    progress=0.3
                )

            # Log initial step
            if run_id:
                await self._log_agent_step(
                    db=db,
                    run_id=run_id,
                    step_number=0,
                    tool="orchestrator.classify",
                    input_data={"query": user_input},
                    output_data={"intent": phase1_intent},
                    latency_ms=int((time.time() - start_time) * 1000)
                )

            # Execute via existing process method
            execution_start = time.time()
            response = await self.process(
                user_input=user_input,
                db=db,
                context=context,
                conversation_history=conversation_history,
                thought_stream=thought_stream,
                state_manager=state_manager
            )
            execution_latency = int((time.time() - execution_start) * 1000)

            # Log execution step
            if run_id:
                await self._log_agent_step(
                    db=db,
                    run_id=run_id,
                    step_number=1,
                    tool="orchestrator.execute",
                    input_data={"intent": phase1_intent},
                    output_data={"success": response.success},
                    error=None if response.success else response.message,
                    latency_ms=execution_latency
                )

            # Step 5: Evaluate results
            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.VALIDATING,
                    title="Validation des résultats",
                    content="Je vérifie que les règles de conformité sont respectées...",
                    agent="evaluator",
                    progress=0.9
                )

            # Determine rules based on intent
            rules_to_check = self._get_evaluation_rules(phase1_intent, response)

            eval_start = time.time()
            evaluation = await self.evaluator.evaluate(
                rules=rules_to_check,
                context={
                    "response": response.message,
                    "data": response.data or {},
                    "intent": phase1_intent,
                    "citations": response.data.get("sources", []) if response.data else []
                }
            )
            eval_latency = int((time.time() - eval_start) * 1000)

            logger.info(
                "evaluation_complete",
                passed=evaluation.passed,
                rules_checked=evaluation.rules_checked,
                critical_failures=evaluation.critical_failures,
                warnings=evaluation.warnings
            )

            # Log evaluation step
            if run_id:
                await self._log_agent_step(
                    db=db,
                    run_id=run_id,
                    step_number=2,
                    tool="evaluator.check",
                    input_data={"rules": rules_to_check},
                    output_data=evaluation.dict(),
                    latency_ms=eval_latency
                )

            # Step 6: Finalize AgentRun
            total_latency = int((time.time() - start_time) * 1000)

            if run_id:
                await self._finalize_agent_run(
                    db=db,
                    run_id=run_id,
                    status="success" if response.success and evaluation.passed else "failed",
                    cost_tokens=plan.estimated_tokens,
                    citations_json=response.data.get("sources") if response.data else None,
                    has_conflicts=response.data.get("has_contradictions", False) if response.data else False,
                    evaluator_passed=evaluation.passed
                )

            # Add evaluation results to response
            if response.data is None:
                response.data = {}

            response.data["evaluation"] = {
                "passed": evaluation.passed,
                "rules_checked": evaluation.rules_checked,
                "rules_passed": evaluation.rules_passed,
                "critical_failures": evaluation.critical_failures,
                "warnings": evaluation.warnings,
                "failed_rules": evaluation.rules_failed
            }
            response.data["observability"] = {
                "run_id": run_id,
                "plan_steps": len(plan.steps),
                "total_latency_ms": total_latency,
                "estimated_tokens": plan.estimated_tokens
            }

            # Add warning message if evaluation failed
            if not evaluation.passed:
                warning_msg = f"\n\n⚠️ **Attention**: {evaluation.critical_failures} règle(s) critique(s) non respectée(s)."
                response.message += warning_msg

            return response

        except Exception as e:
            logger.error("process_with_plan_failed", error=str(e), exc_info=True)

            # Log failure if run_id exists
            if run_id:
                await self._finalize_agent_run(
                    db=db,
                    run_id=run_id,
                    status="failed",
                    evaluator_passed=False
                )

            return AgentResponse(
                success=False,
                message=f"Erreur lors du traitement avec plan : {str(e)}",
                agents_used=["orchestrator", "planner", "evaluator"]
            )

    def _get_evaluation_rules(self, intent: str, response: AgentResponse) -> List[str]:
        """
        Determine which evaluation rules to apply based on intent

        Args:
            intent: Phase 1 intent (SQL_ONLY, RAG_ONLY, HYBRID, etc.)
            response: Agent response to evaluate

        Returns:
            List of rule IDs to check
        """
        rules = []

        if intent == "SQL_ONLY":
            rules = ["sql_no_error", "sql_results_not_empty"]

        elif intent == "RAG_ONLY":
            rules = ["rag_has_citations", "rag_min_sources_2"]

        elif intent == "HYBRID":
            rules = [
                "rag_has_citations",
                "sql_no_error",
                "hybrid_no_contradiction",
                "hybrid_sources_attributed"
            ]

        elif intent == "EMAIL":
            rules = ["email_has_evidence", "email_preview_shown"]

        elif intent == "N8N":
            rules = ["n8n_preview_if_danger_high", "n8n_correlation_id"]

        elif intent == "WEB":
            rules = ["web_urls_cited"]

        # Add SQL whitelist check if SQL was used
        if "sql_agent" in response.agents_used:
            if "sql_whitelist_tables" not in rules:
                rules.append("sql_whitelist_tables")

        return rules
