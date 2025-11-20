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
from app.services.agents.state_registry import StateManager
from app.utils.sql_validation import validate_sql_query

logger = structlog.get_logger()


class IntentType(str, Enum):
    """Types of user intentions (V4 - includes new agents)"""
    # Core intents
    QUERY_DATA = "query_data"  # SQL queries (copropriétaires, copropriétés, etc.)
    SEARCH_DOCUMENTS = "search_documents"  # RAG search (contracts, regulations)
    SEND_EMAIL = "send_email"  # Generate and send emails
    CONFIRM_EMAIL = "confirm_email"  # Confirm sending email after draft review
    REQUEST_QUOTES = "request_quotes"  # Request devis from vendors
    ANALYZE_DOCUMENT = "analyze_document"  # OCR + extraction
    GENERATE_DIGEST = "generate_digest"  # Generate email digest
    GENERAL_QUESTION = "general_question"  # General assistant question
    TRIGGER_WORKFLOW = "trigger_workflow"  # Explicit N8N workflow trigger

    # New Phase 2 intents (Web Search + Legal agents)
    WEB_SEARCH = "web_search"  # Search internet for current info
    LEGAL_ANALYSIS = "legal_analysis"  # Analyze legal documents
    LEGAL_COMPARISON = "legal_comparison"  # Compare legal docs
    LEGAL_ADVICE = "legal_advice"  # Legal counsel/advice
    SEARCH_JURISPRUDENCE = "search_jurisprudence"  # Find jurisprudence


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

        # Import production components
        from .hybrid_executor import HybridExecutor
        from .response_fusion_agent import ResponseFusionAgent
        from .intent_classifier_v3 import EnhancedIntentClassifierV3

        # REMOVED: v2 classifier (unused, wastes 50MB memory)
        # REMOVED: context_intelligence (file doesn't exist - causes ImportError)
        # TEMPORARILY USING V3: V4 has compatibility issues with ConversationState

        # Only instantiate what we actually use
        self.intent_classifier_v4 = EnhancedIntentClassifierV3()  # Using V3 temporarily
        self.hybrid_executor = HybridExecutor()
        self.fusion_agent = ResponseFusionAgent()

        logger.info("orchestrator_agent_initialized", version="v4.0_optimized")

    async def classify_intention(
        self,
        user_input: str,
        context: Dict[str, Any] = None,
        state_manager = None,
        conversation_history: List[Dict[str, str]] = None
    ) -> IntentType:
        """
        Classify user intention using Enhanced v3 Classifier

        Args:
            user_input: User's message
            context: Optional context (uploaded files, conversation history)
            state_manager: State manager for accessing recent uploads
            conversation_history: Recent conversation messages

        Returns:
            IntentType enum
        """
        try:
            # Use v4 production classifier with Web Search and Legal agents
            classification_result = await self.intent_classifier_v4.classify(
                user_input=user_input,
                conversation_history=conversation_history,
                state_manager=state_manager,
                context=context
            )

            # Log detailed classification info
            logger.info("intention_classified_v4",
                       user_input=user_input[:50],
                       intent=classification_result.intent.value,
                       confidence=classification_result.confidence,
                       reasoning=classification_result.reasoning[:100] if classification_result.reasoning else None)

            # Log alternatives for debugging
            if classification_result.alternatives:
                try:
                    # V3/V4 compatibility: handle both tuple and object formats
                    alt_summary = []
                    for alt in classification_result.alternatives:
                        if isinstance(alt, tuple):
                            # V4 format: (IntentType, confidence)
                            alt_summary.append(f"{alt[0].value}({alt[1]:.2f})")
                        elif hasattr(alt, 'intent') and hasattr(alt, 'confidence'):
                            # V3 format: AlternativeIntent object
                            alt_summary.append(f"{alt.intent.value}({alt.confidence:.2f})")
                    logger.info("alternative_intents", alternatives=alt_summary)
                except Exception as e:
                    logger.warning("failed_to_parse_alternatives", error=str(e))
            else:
                logger.info("no_alternative_intents")

            # If requires clarification, log it
            if classification_result.requires_clarification:
                logger.warning("low_confidence_classification",
                             confidence=classification_result.confidence,
                             clarification=classification_result.clarification_question)

            # Check for multi-step plan
            if classification_result.multi_step_plan and len(classification_result.multi_step_plan) > 0:
                logger.info("multi_step_plan_detected",
                           plan=[step.value for step in classification_result.multi_step_plan],
                           main_intent=classification_result.intent.value)

            # Convert IntentTypeV4 to IntentType (cast by value)
            intent_value = classification_result.intent.value
            return IntentType(intent_value), classification_result

        except Exception as e:
            logger.error("intention_classification_failed", error=str(e), exc_info=True)
            return IntentType.GENERAL_QUESTION, None

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
            # 0. Pre-populate EntityGraph if empty (first query of session)
            if state_manager:
                entity_graph = state_manager.get_entity_graph()
                if len(entity_graph.entities) == 0:
                    logger.info("entity_graph_empty_prepopulating")
                    await state_manager.pre_populate_entity_graph(db)

            # Thought 1: Analyzing request
            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.ANALYZING,
                    title="Analyse de la demande utilisateur",
                    content=f"Je reçois votre demande : « {user_input} ». Je vais d'abord vérifier si elle contient des références à des documents récemment uploadés, puis déterminer quelle action entreprendre.",
                    agent="orchestrator",
                    progress=0.05
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

                    if thought_stream:
                        await thought_stream.add_thought(
                            ThoughtType.PROCESSING,
                            title="Résolution de référence document",
                            content=f"J'ai détecté une référence générique à un document. Je la remplace par le fichier récemment uploadé : « {doc_filename} »",
                            agent="orchestrator",
                            progress=0.1
                        )

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

            # 1.5 NOUVEAU: Query Enrichment (résolution d'entités)
            enriched_query_obj = None
            if state_manager:
                try:
                    from app.services.agents.query_enrichment import QueryEnrichmentLayer

                    enrichment_layer = QueryEnrichmentLayer()
                    entity_graph = state_manager.get_entity_graph()

                    # Enrich query with entity resolution
                    enriched_query_obj = await enrichment_layer.enrich(
                        user_query=user_input,
                        entity_graph=entity_graph,
                        conversation_state=state_manager.get_state(),
                        db=db
                    )

                    # If entities were resolved, use enriched query
                    if enriched_query_obj.resolved_entities:
                        logger.info("query_enriched",
                                   original=user_input[:50],
                                   enriched=enriched_query_obj.enriched_query[:50],
                                   entities_count=len(enriched_query_obj.resolved_entities))

                        # Use enriched query for intent classification
                        user_input = enriched_query_obj.enriched_query

                        # Add enrichment context
                        if not context:
                            context = {}
                        context.update(enriched_query_obj.context)

                        if thought_stream:
                            resolved_names = ", ".join([
                                f"«{e.canonical_name}»"
                                for e in enriched_query_obj.resolved_entities.values()
                            ])
                            await thought_stream.add_thought(
                                ThoughtType.PROCESSING,
                                title="Résolution des références",
                                content=f"J'ai identifié et résolu {len(enriched_query_obj.resolved_entities)} entité(s) dans votre demande : {resolved_names}. Je vais utiliser ces informations pour générer une requête plus précise.",
                                agent="orchestrator",
                                progress=0.12
                            )

                except Exception as e:
                    logger.warning("query_enrichment_failed", error=str(e))
                    # Continue with original query if enrichment fails

            # 2. Classify intention
            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.CLASSIFYING,
                    title="Classification de l'intention utilisateur",
                    content="J'analyse la demande pour déterminer l'action appropriée. Je vérifie les mots-clés, le contexte de la conversation, et les documents actifs pour classifier l'intention parmi : requête SQL, recherche documentaire (RAG), génération d'email, recherche web, analyse légale, etc.",
                    agent="intent_classifier",
                    progress=0.15
                )

            intent, classification_result = await self.classify_intention(
                user_input,
                context,
                state_manager,
                conversation_history
            )

            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.CLASSIFYING,
                    title=f"Intention détectée : {intent.value}",
                    content=f"Classification terminée. Type d'intention identifiée : {intent.value}. Je vais maintenant déterminer quel(s) agent(s) spécialisé(s) activer pour traiter cette demande.",
                    agent="intent_classifier",
                    progress=0.25
                )

            logger.info("processing_request", intent=intent.value, input=user_input[:50])

            # Check for multi-step workflow
            if classification_result and classification_result.multi_step_plan:
                logger.info("executing_multi_step_workflow",
                           steps=[s.value for s in classification_result.multi_step_plan])

                # Execute multi-step plan
                return await self._execute_multi_step_plan(
                    classification_result.multi_step_plan,
                    user_input,
                    db,
                    context,
                    thought_stream,
                    state_manager,
                    conversation_history
                )

            # Thought 2: Planning
            if thought_stream:
                intent_descriptions = {
                    IntentType.QUERY_DATA: "SQL Agent (requête base de données PostgreSQL)",
                    IntentType.SEARCH_DOCUMENTS: "RAG Agent (recherche sémantique + Qdrant)",
                    IntentType.SEND_EMAIL: "Email Agent + Workflow Agent (génération + envoi via N8N)",
                    IntentType.REQUEST_QUOTES: "SQL Agent + Template Agent + Workflow Agent",
                    IntentType.ANALYZE_DOCUMENT: "OCR Agent (extraction Tesseract + analyse)",
                    IntentType.TRIGGER_WORKFLOW: "Workflow Agent (déclenchement N8N)",
                    IntentType.GENERAL_QUESTION: "LLM Direct (Mistral/GPT-4o)",
                    IntentType.WEB_SEARCH: "Web Search Agent (Tavily API)",
                    IntentType.LEGAL_ANALYSIS: "Legal Agent (analyse juridique)",
                }
                agent_desc = intent_descriptions.get(intent, 'agents appropriés')
                await thought_stream.add_thought(
                    ThoughtType.PLANNING,
                    title=f"Planification : {intent.value}",
                    content=f"Intention confirmée : {intent.value}.\n\nAgent(s) sélectionné(s) : {agent_desc}.\n\nJe vais maintenant activer cet agent et lui transmettre votre demande pour traitement.",
                    agent="orchestrator",
                    data={"intent": intent.value, "agents": agent_desc},
                    progress=0.35
                )

            # 2. Route to appropriate agent(s)
            if intent == IntentType.QUERY_DATA:
                if thought_stream:
                    await thought_stream.add_thought(
                        ThoughtType.EXECUTING,
                        title="Activation SQL Agent",
                        content="Je transfère la demande au SQL Agent. Il va analyser votre question, générer une requête SQL appropriée, l'exécuter sur la base PostgreSQL, et formater les résultats.",
                        agent="sql_agent",
                        progress=0.4
                    )
                return await self._handle_query_data(user_input, db, state_manager, thought_stream)

            elif intent == IntentType.SEARCH_DOCUMENTS:
                return await self._handle_search_documents(user_input, db, state_manager, conversation_history, thought_stream, context)

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

            # NEW Phase 2 agents
            elif intent == IntentType.WEB_SEARCH:
                return await self._handle_web_search(user_input, thought_stream)

            elif intent == IntentType.LEGAL_ANALYSIS:
                return await self._handle_legal_analysis(user_input, context, thought_stream)

            elif intent == IntentType.LEGAL_COMPARISON:
                return await self._handle_legal_comparison(user_input, context, thought_stream)

            elif intent == IntentType.LEGAL_ADVICE:
                return await self._handle_legal_advice(user_input, context, db, thought_stream)

            elif intent == IntentType.SEARCH_JURISPRUDENCE:
                return await self._handle_search_jurisprudence(user_input, db, thought_stream)

            else:  # GENERAL_QUESTION
                logger.info("handling_general_question",
                           query=user_input[:100],
                           has_history=len(conversation_history) if conversation_history else 0)
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

    async def _handle_query_data(self, user_input: str, db: AsyncSession, state_manager=None, thought_stream=None) -> AgentResponse:
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

                if thought_stream:
                    await thought_stream.add_thought(
                        ThoughtType.PROCESSING,
                        title="Enrichissement de la requête",
                        content=f"J'ai détecté que vous souhaitez filtrer par métier. J'enrichis la requête avec les professions pertinentes identifiées dans le contexte : {', '.join(relevant_professions)}",
                        agent="sql_agent",
                        progress=0.5
                    )

        if thought_stream:
            await thought_stream.add_thought(
                ThoughtType.EXECUTING,
                title="Génération de la requête SQL",
                content=f"Le SQL Agent analyse la demande et génère une requête SQL optimisée pour interroger la base de données PostgreSQL. Requête à traiter : « {enriched_input} »",
                agent="sql_agent",
                progress=0.6
            )

        sql_agent = SQLAgent()
        result = await sql_agent.process(enriched_input, db)

        if thought_stream:
            if result.get("success"):
                row_count = len(result.get("data", {}).get("results", []))
                await thought_stream.add_thought(
                    ThoughtType.PROCESSING,
                    title="Requête SQL exécutée avec succès",
                    content=f"✓ La requête a été exécutée. J'ai récupéré {row_count} résultat(s) de la base de données. Je vais maintenant formater et présenter ces données.",
                    agent="sql_agent",
                    progress=0.75
                )
            else:
                await thought_stream.add_thought(
                    ThoughtType.ERROR,
                    title="Erreur lors de l'exécution SQL",
                    content=f"✗ Une erreur s'est produite lors de l'exécution de la requête : {result.get('message', 'Erreur inconnue')}",
                    agent="sql_agent",
                    progress=0.75
                )

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
                        # Professionals query - extract profession type from user query
                        profession_keywords = {
                            "plombier": ["plombier", "plombiers"],
                            "électricien": ["électricien", "électriciens", "electricien"],
                            "chauffagiste": ["chauffagiste", "chauffagistes"],
                            "jardinier": ["jardinier", "jardiniers"],
                            "menuisier": ["menuisier", "menuisiers"],
                            "peintre": ["peintre", "peintres"],
                            "serrurier": ["serrurier", "serruriers"],
                            "maçon": ["maçon", "maçons", "macon"]
                        }

                        # Detect profession from user input
                        user_input_lower = user_input.lower()
                        detected_profession = "professionnel"
                        for profession, keywords in profession_keywords.items():
                            if any(keyword in user_input_lower for keyword in keywords):
                                detected_profession = profession
                                break

                        # Store profession in business context for later reference
                        if not state_manager.get_state().business_context:
                            state_manager.get_state().business_context = {}
                        state_manager.get_state().business_context["profession_requested"] = detected_profession

                        state_manager.get_state().set_last_query_entities(results, "professionals")
                        logger.info("stored_query_entities_in_state",
                                   type="professionals",
                                   profession=detected_profession,
                                   count=len(results))
                    elif "nom" in first_row and "nombre_coproprietaires" in first_row:
                        # Properties query
                        state_manager.get_state().set_last_query_entities(results, "properties")
                        logger.info("stored_query_entities_in_state", type="properties", count=len(results))

                # NOUVEAU: Populate EntityGraph with results
                try:
                    from app.services.agents.query_enrichment import EntityPopulator

                    entity_populator = EntityPopulator()
                    entity_graph = state_manager.get_entity_graph()

                    # Determine query type and populate
                    # Copropriétés: has copropriete_nom OR (nom + nombre_lots) OR (nom + adresse + ville)
                    is_copropriete = (
                        "copropriete_nom" in first_row or
                        ("nom" in first_row and "nombre_lots" in first_row) or
                        ("nom" in first_row and "adresse" in first_row and "ville" in first_row)
                    )

                    if is_copropriete:
                        # Copropriétés
                        await entity_populator.populate_from_sql_results(
                            results=results,
                            query_type="coproprietes",
                            entity_graph=entity_graph
                        )
                        logger.info("entity_graph_populated_coproprietes", count=len(results))
                    elif "prenom" in first_row and "nom" in first_row and "email" in first_row:
                        # People (coproprietaires with email)
                        await entity_populator.populate_from_sql_results(
                            results=results,
                            query_type="people",
                            entity_graph=entity_graph
                        )
                        logger.info("entity_graph_populated_people", count=len(results))
                    elif "name" in first_row and "category" in first_row:
                        # Professionals
                        await entity_populator.populate_from_sql_results(
                            results=results,
                            query_type="professionals",
                            entity_graph=entity_graph
                        )
                        logger.info("entity_graph_populated_professionals", count=len(results))

                except Exception as e:
                    logger.warning("entity_graph_population_failed", error=str(e), exc_info=True)

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

    async def _handle_search_documents(self, user_input: str, db: AsyncSession, state_manager = None, conversation_history: List[Dict] = None, thought_stream: ThoughtStream = None, context: Dict = None) -> AgentResponse:
        """
        Handle document search via RAG

        Simplified version: Direct RAG search without complex context analysis
        """
        try:
            logger.info("handling_search_documents", query=user_input[:50])

            # Extract active document IDs from context if available
            document_ids = None
            if context and "active_document_ids" in context:
                document_ids = context["active_document_ids"]
                logger.info("rag_filtering_by_documents", doc_ids=document_ids)

            # Thought 1: Recherche documentaire
            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.EXECUTING,
                    title="Recherche dans les documents",
                    content="Je cherche dans vos documents les informations pertinentes pour répondre à votre question.",
                    agent="rag_agent",
                    progress=0.3
                )

            # Simple RAG search with optional document filtering
            search_results = await self.rag_service.search(
                query=user_input,
                limit=5,
                document_ids=document_ids,
                use_reranker=True,
                use_hybrid=True
            )

            if not search_results or len(search_results) == 0:
                if thought_stream:
                    await thought_stream.add_thought(
                        ThoughtType.COMPLETED,
                        title="Aucun résultat",
                        content="Aucune information pertinente trouvée dans les documents.",
                        agent="rag_agent",
                        progress=1.0
                    )
                return AgentResponse(
                    success=True,
                    message="Je n'ai trouvé aucune information pertinente dans les documents disponibles.",
                    agents_used=["rag_agent"],
                    confidence=0.0
                )

            # Thought 2: Génération de la réponse
            if thought_stream:
                # Build a more informative message
                doc_names = [r['metadata'].get('source', 'Inconnu') for r in search_results[:3]]
                doc_list = ", ".join(doc_names)
                if len(search_results) > 3:
                    doc_list += f" et {len(search_results) - 3} autre(s)"

                filter_info = ""
                if document_ids:
                    filter_info = f" (filtré sur {len(document_ids)} document(s) sélectionné(s))"

                content_msg = f"J'ai trouvé {len(search_results)} résultat(s) pertinent(s){filter_info}.\n\n**Documents:** {doc_list}\n\nJe génère maintenant une réponse complète basée sur ces documents."

                await thought_stream.add_thought(
                    ThoughtType.PROCESSING,
                    title="Analyse des documents",
                    content=content_msg,
                    agent="rag_agent",
                    progress=0.6
                )

            # Generate response using LLM with retrieved context
            context_text = "\n\n".join([
                f"Document: {r['metadata'].get('source', 'Inconnu')}\nContenu: {r['content']}"
                for r in search_results
            ])

            # Construct prompt with context and question
            prompt = f"""Tu es un assistant intelligent qui aide les utilisateurs à trouver des informations dans leurs documents.

Contexte récupéré:
{context_text}

Question de l'utilisateur: {user_input}

Réponds à la question de manière précise et complète en utilisant uniquement les informations du contexte ci-dessus."""

            llm_response = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.3,
                max_tokens=2000
            )

            # Thought 3: Terminé
            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.COMPLETED,
                    title="Réponse générée",
                    content="J'ai terminé l'analyse et généré une réponse complète basée sur vos documents.",
                    agent="rag_agent",
                    progress=1.0
                )

            # Format sources for frontend
            sources = [
                {
                    "type": "document",
                    "filename": r["metadata"].get("source", "Inconnu"),
                    "score": round(r.get("score", 0), 3),
                    "excerpt": r["content"][:200] + "..." if len(r["content"]) > 200 else r["content"]
                }
                for r in search_results
            ]

            return AgentResponse(
                success=True,
                message=llm_response,
                data={"sources": sources},
                agents_used=["rag_agent"],
                confidence=0.85
            )

        except Exception as e:
            logger.error("rag_search_failed", error=str(e), exc_info=True)
            return AgentResponse(
                success=False,
                message=f"Erreur lors de la recherche documentaire : {str(e)}",
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

            # DEBUG: Log what's in the context
            if context:
                logger.info("email_context_check", context_keys=list(context.keys()))
                if "query_data" in context:
                    logger.info("query_data_in_context", structure=str(type(context["query_data"]))[:100])

            # Check if recipients were already retrieved in previous multi-step (e.g., QUERY_DATA step)
            if context and "query_data" in context:
                query_data_context = context["query_data"]

                # Try to extract from the result data structure
                if isinstance(query_data_context, dict):
                    result_data = query_data_context.get("result", {})
                    logger.info("result_data_structure", keys=list(result_data.keys()) if result_data else "empty")

                    # Check emails_available (direct field from SQL agent)
                    if "emails_available" in result_data and isinstance(result_data["emails_available"], list):
                        recipients_found = [str(email) for email in result_data["emails_available"] if email]
                        logger.info("emails_found_in_emails_available", count=len(recipients_found))

                    # Also try results field with email column
                    elif "results" in result_data and isinstance(result_data["results"], list):
                        for row in result_data["results"]:
                            if isinstance(row, dict) and "email" in row and row["email"]:
                                recipients_found.append(str(row["email"]))
                        logger.info("emails_found_in_results", count=len(recipients_found))

                    if recipients_found:
                        logger.info("recipients_from_previous_step", count=len(recipients_found))
                        if thought_stream:
                            await thought_stream.add_thought(
                                ThoughtType.ANALYZING,
                                title="Destinataires récupérés",
                                content=f"✓ {len(recipients_found)} destinataire(s) récupéré(s) de l'étape précédente",
                                agent="orchestrator",
                                progress=0.4
                            )

            # Execute SQL query if needed and no recipients found yet
            if not recipients_found:
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

                        # SECURITY: Validate SQL query before execution
                        is_valid, error_msg = validate_sql_query(step.query)
                        if not is_valid:
                            logger.error(
                                "sql_query_validation_failed",
                                query=step.query,
                                error=error_msg
                            )
                            # Skip this step and continue
                            continue

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

    # ========== NEW PHASE 2 AGENT HANDLERS ==========

    async def _handle_web_search(self, user_input: str, thought_stream: ThoughtStream = None) -> AgentResponse:
        """Handle web search requests"""
        try:
            from .websearch_agent import WebSearchAgent

            web_agent = WebSearchAgent()

            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.SEARCHING,
                    title="Recherche sur le web",
                    content=f"Je recherche sur internet : « {user_input} »",
                    agent="websearch_agent",
                    progress=0.5
                )

            # Perform search
            search_results = await web_agent.search(
                query=user_input,
                num_results=5,
                search_depth="basic",
                region="fr-fr"
            )

            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.PROCESSING,
                    title="Synthèse des résultats",
                    content=f"J'ai trouvé {len(search_results.results)} résultats. Je vais synthétiser les informations les plus pertinentes.",
                    agent="websearch_agent",
                    progress=0.8
                )

            # Format results with answer + sources
            formatted_message = ""

            if search_results.synthesized_answer:
                formatted_message += search_results.synthesized_answer + "\n\n"

            if search_results.results:
                formatted_message += "## 🔍 Sources\n\n"
                for idx, result in enumerate(search_results.results[:5], 1):
                    formatted_message += f"**[{idx}] {result.title}**\n"
                    formatted_message += f"{result.snippet[:200]}...\n"
                    formatted_message += f"🔗 {result.url}\n\n"

            return AgentResponse(
                success=True,
                message=formatted_message,
                data=search_results.to_dict(),
                agents_used=["websearch_agent"],
                confidence=search_results.confidence
            )

        except Exception as e:
            logger.error("web_search_failed", error=str(e), exc_info=True)
            return AgentResponse(
                success=False,
                message=f"Erreur lors de la recherche web: {str(e)}",
                agents_used=["websearch_agent"]
            )

    async def _handle_legal_analysis(self, user_input: str, context: Dict[str, Any], thought_stream: ThoughtStream = None) -> AgentResponse:
        """Handle legal document analysis"""
        try:
            from .legal_agent import LegalAgent

            legal_agent = LegalAgent()

            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.ANALYZING,
                    title="Analyse juridique",
                    content="Analyse juridique du document en cours...",
                    agent="legal_agent",
                    progress=0.5
                )

            # Extract document from context
            document_text = context.get("document_text", "") if context else ""
            if not document_text:
                return AgentResponse(
                    success=False,
                    message="❌ Aucun document à analyser. Veuillez uploader un document d'abord.",
                    agents_used=["legal_agent"]
                )

            # Perform full legal analysis
            result = await legal_agent.analyze_document(
                document_text=document_text,
                analysis_type="full"
            )

            # Format response
            if "error" in result:
                return AgentResponse(
                    success=False,
                    message=result["error"],
                    agents_used=["legal_agent"]
                )

            # Build formatted message
            formatted_message = f"## Analyse juridique\n\n"
            formatted_message += f"**Type de document:** {legal_agent.document_types.get(result.get('document_type', 'autre'), 'Document juridique')}\n\n"

            if result.get("summary"):
                formatted_message += f"### Résumé\n{result['summary']}\n\n"

            if result.get("risks"):
                formatted_message += f"### Risques identifiés ({len(result['risks'])})\n"
                for risk in result["risks"][:5]:  # Top 5
                    severity_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}.get(risk.get("severity", "medium"), "⚪")
                    formatted_message += f"{severity_emoji} **{risk.get('category', 'Risque')}**: {risk.get('description', '')}\n"
                formatted_message += "\n"

            if result.get("obligations"):
                formatted_message += f"### Obligations principales ({len(result['obligations'])})\n"
                for obligation in result["obligations"][:5]:
                    formatted_message += f"- **{obligation.get('partie', '')}**: {obligation.get('description', '')}\n"
                formatted_message += "\n"

            if result.get("recommendations"):
                formatted_message += f"### Recommandations\n"
                for idx, rec in enumerate(result["recommendations"], 1):
                    formatted_message += f"{idx}. {rec}\n"

            return AgentResponse(
                success=True,
                message=formatted_message,
                data=result,
                agents_used=["legal_agent"],
                confidence=0.9
            )

        except Exception as e:
            logger.error("legal_analysis_failed", error=str(e), exc_info=True)
            return AgentResponse(
                success=False,
                message=f"Erreur lors de l'analyse juridique: {str(e)}",
                agents_used=["legal_agent"]
            )

    async def _handle_legal_comparison(self, user_input: str, context: Dict[str, Any], thought_stream: ThoughtStream = None) -> AgentResponse:
        """Handle legal document comparison"""
        try:
            from .legal_agent import LegalAgent

            legal_agent = LegalAgent()

            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.ANALYZING,
                    title="Comparaison juridique",
                    content="Comparaison de documents juridiques...",
                    agent="legal_agent",
                    progress=0.5
                )

            # Extract documents from context
            doc1 = context.get("document1", "") if context else ""
            doc2 = context.get("document2", "") if context else ""

            if not doc1 or not doc2:
                return AgentResponse(
                    success=False,
                    message="❌ Deux documents sont nécessaires pour la comparaison.",
                    agents_used=["legal_agent"]
                )

            result = await legal_agent.compare_legal_documents(
                doc1=doc1,
                doc2=doc2,
                comparison_type="general"
            )

            return AgentResponse(
                success=result["success"],
                message=result["comparison"],
                data=result,
                agents_used=["legal_agent"],
                confidence=result.get("confidence", 0.9)
            )

        except Exception as e:
            logger.error("legal_comparison_failed", error=str(e), exc_info=True)
            return AgentResponse(
                success=False,
                message=f"Erreur lors de la comparaison juridique: {str(e)}",
                agents_used=["legal_agent"]
            )

    async def _handle_legal_advice(self, user_input: str, context: Dict[str, Any], db: AsyncSession, thought_stream: ThoughtStream = None) -> AgentResponse:
        """Handle legal advice requests"""
        try:
            from .legal_agent import LegalAgent

            legal_agent = LegalAgent()

            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.ANALYZING,
                    title="Conseil juridique",
                    content="Recherche d'informations juridiques...",
                    agent="legal_agent",
                    progress=0.5
                )

            result = await legal_agent.provide_legal_advice(
                situation=user_input,
                context=context or {}
            )

            # Flatten sources structure for FastAPI validation (sources must be a list, not a dict)
            flattened_data = result.copy()
            if "sources" in flattened_data and isinstance(flattened_data["sources"], dict):
                # Convert {'rag': [...], 'web': [...]} to a flat list with metadata
                all_sources = []
                for source_type, items in flattened_data["sources"].items():
                    if isinstance(items, list):
                        for item in items:
                            if isinstance(item, dict):
                                item["source_type"] = source_type  # Add type as metadata
                                all_sources.append(item)
                flattened_data["sources"] = all_sources

            return AgentResponse(
                success=result["success"],
                message=result["advice"],
                data=flattened_data,
                agents_used=["legal_agent"],
                confidence=result.get("confidence", 0.85),
                suggestions=["Consulter un avocat pour confirmation", "Demander une analyse approfondie"]
            )

        except Exception as e:
            logger.error("legal_advice_failed", error=str(e), exc_info=True)
            return AgentResponse(
                success=False,
                message=f"Erreur lors de la fourniture du conseil juridique: {str(e)}",
                agents_used=["legal_agent"]
            )

    async def _handle_search_jurisprudence(self, user_input: str, db: AsyncSession, thought_stream: ThoughtStream = None) -> AgentResponse:
        """Handle jurisprudence search"""
        try:
            from .legal_agent import LegalAgent

            legal_agent = LegalAgent()

            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.SEARCHING,
                    title="Recherche de jurisprudence",
                    content="Recherche de jurisprudence pertinente...",
                    agent="legal_agent",
                    progress=0.5
                )

            result = await legal_agent.search_jurisprudence(
                legal_question=user_input,
                case_type="copropriete"
            )

            return AgentResponse(
                success=result["success"],
                message=result["jurisprudence"],
                data=result,
                agents_used=["legal_agent"],
                confidence=result.get("confidence", 0.8)
            )

        except Exception as e:
            logger.error("jurisprudence_search_failed", error=str(e), exc_info=True)
            return AgentResponse(
                success=False,
                message=f"Erreur lors de la recherche de jurisprudence: {str(e)}",
                agents_used=["legal_agent"]
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

    async def _execute_multi_step_plan(
        self,
        plan: List[IntentType],
        user_input: str,
        db: AsyncSession,
        context: Optional[Dict[str, Any]] = None,
        thought_stream: Optional[ThoughtStream] = None,
        state_manager: Optional[StateManager] = None,
        conversation_history: List[Dict[str, str]] = None
    ) -> AgentResponse:
        """
        Execute a multi-step plan sequentially

        Each step is executed and its output becomes context for the next step.
        This enables complex workflows like:
        - Query data → Send email with results
        - Search documents → Analyze → Generate report
        - Web search → Legal analysis → Recommendation

        Args:
            plan: List of IntentTypes to execute in sequence
            user_input: Original user request
            db: Database session
            context: Additional context
            thought_stream: Stream for thoughts
            state_manager: State management
            conversation_history: Previous messages

        Returns:
            AgentResponse with combined results from all steps
        """
        try:
            logger.info("multi_step_execution_started",
                       steps=[step.value for step in plan],
                       user_input=user_input[:100])

            if thought_stream:
                thought_stream.add_thought(
                    f"🎯 Plan multi-étapes détecté: {len(plan)} étapes",
                    details=" → ".join([step.value for step in plan])
                )

            # Accumulated context from previous steps
            accumulated_context = context or {}
            accumulated_data = {}
            all_agents_used = []
            all_messages = []

            # Execute each step in sequence
            for step_idx, step in enumerate(plan, 1):
                logger.info("executing_step",
                           step=step.value,
                           step_number=f"{step_idx}/{len(plan)}")

                if thought_stream:
                    thought_stream.add_thought(
                        f"🔄 Étape {step_idx}/{len(plan)}: {step.value}",
                        details=f"Exécution de l'action: {step.value}"
                    )

                # Execute the step based on intent type
                step_result = await self._execute_single_step(
                    intent=step,
                    user_input=user_input,
                    db=db,
                    context=accumulated_context,
                    thought_stream=thought_stream,
                    state_manager=state_manager,
                    conversation_history=conversation_history
                )

                # Accumulate results
                if step_result.success:
                    all_agents_used.extend(step_result.agents_used)
                    all_messages.append(f"✅ {step.value}: {step_result.message}")

                    # Add step results to accumulated context
                    accumulated_data[step.value] = step_result.data
                    accumulated_context[step.value] = {
                        "result": step_result.data,
                        "message": step_result.message
                    }

                    logger.info("step_completed",
                               step=step.value,
                               success=True)
                else:
                    # Step failed - decide whether to continue or abort
                    logger.warning("step_failed",
                                 step=step.value,
                                 error=step_result.message)
                    all_messages.append(f"⚠️ {step.value}: {step_result.message}")

                    # For critical steps (like QUERY_DATA before SEND_EMAIL), abort
                    if step_idx < len(plan):
                        logger.info("aborting_multi_step_plan",
                                   reason="critical_step_failed",
                                   failed_step=step.value)

                        return AgentResponse(
                            success=False,
                            message=f"❌ Échec à l'étape {step_idx}/{len(plan)} ({step.value}): {step_result.message}",
                            data=accumulated_data,
                            agents_used=all_agents_used
                        )

            # All steps completed successfully
            logger.info("multi_step_execution_completed",
                       steps_executed=len(plan),
                       agents_used=all_agents_used)

            if thought_stream:
                thought_stream.add_thought(
                    f"✅ Plan multi-étapes terminé: {len(plan)}/{len(plan)} étapes réussies",
                    details="\n".join(all_messages)
                )

            # Build final response message
            final_message = f"✅ Workflow multi-étapes terminé ({len(plan)} étapes):\n\n"
            final_message += "\n".join(all_messages)

            return AgentResponse(
                success=True,
                message=final_message,
                data=accumulated_data,
                agents_used=list(set(all_agents_used)),  # Unique agents
                confidence=0.9
            )

        except Exception as e:
            logger.error("multi_step_execution_failed",
                        error=str(e),
                        exc_info=True)
            return AgentResponse(
                success=False,
                message=f"❌ Erreur lors de l'exécution du plan multi-étapes: {str(e)}",
                agents_used=["orchestrator"]
            )

    async def _execute_single_step(
        self,
        intent: IntentType,
        user_input: str,
        db: AsyncSession,
        context: Dict[str, Any],
        thought_stream: Optional[ThoughtStream] = None,
        state_manager: Optional[StateManager] = None,
        conversation_history: List[Dict[str, str]] = None
    ) -> AgentResponse:
        """
        Execute a single step in a multi-step plan

        Routes to appropriate handler based on intent type.

        Args:
            intent: Intent type to execute
            user_input: Original user input
            db: Database session
            context: Context from previous steps
            thought_stream: Stream for thoughts
            state_manager: State management
            conversation_history: Previous messages

        Returns:
            AgentResponse from the specific handler
        """
        # Map intent to handler method
        handler_map = {
            IntentType.QUERY_DATA: self._handle_query_data,
            IntentType.SEARCH_DOCUMENTS: self._handle_search_documents,
            IntentType.SEND_EMAIL: self._handle_send_email_intelligent,
            IntentType.REQUEST_QUOTES: self._handle_request_quotes,
            IntentType.ANALYZE_DOCUMENT: self._handle_analyze_document,
            IntentType.TRIGGER_WORKFLOW: self._handle_trigger_workflow,
            IntentType.WEB_SEARCH: self._handle_web_search,
            IntentType.LEGAL_ADVICE: self._handle_legal_advice,
            IntentType.LEGAL_ANALYSIS: self._handle_legal_analysis,
            IntentType.LEGAL_COMPARISON: self._handle_legal_comparison,
            IntentType.SEARCH_JURISPRUDENCE: self._handle_search_jurisprudence,
            IntentType.GENERAL_QUESTION: self._handle_general_question,
        }

        handler = handler_map.get(intent)

        if not handler:
            logger.error("no_handler_for_intent", intent=intent.value)
            return AgentResponse(
                success=False,
                message=f"Aucun gestionnaire trouvé pour l'intention: {intent.value}",
                agents_used=["orchestrator"]
            )

        # Call handler with appropriate arguments based on signature
        try:
            # Most handlers need these basic args
            handler_kwargs = {"user_input": user_input}

            # Add context if handler accepts it
            import inspect
            sig = inspect.signature(handler)
            if "context" in sig.parameters:
                handler_kwargs["context"] = context
            if "db" in sig.parameters:
                handler_kwargs["db"] = db
            if "thought_stream" in sig.parameters:
                handler_kwargs["thought_stream"] = thought_stream
            if "state_manager" in sig.parameters:
                handler_kwargs["state_manager"] = state_manager
            if "conversation_history" in sig.parameters:
                handler_kwargs["conversation_history"] = conversation_history

            return await handler(**handler_kwargs)

        except Exception as e:
            logger.error("step_execution_error",
                        intent=intent.value,
                        error=str(e),
                        exc_info=True)
            return AgentResponse(
                success=False,
                message=f"Erreur lors de l'exécution de {intent.value}: {str(e)}",
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
