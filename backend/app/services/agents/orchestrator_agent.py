"""
Orchestrator Agent - Brain of the Multi-Agent System
Routes user requests to appropriate specialized agents
"""

import structlog
from typing import Dict, Any, List, Optional

from app.services.llm_service import LLMService
from app.services.rag_service import RAGService
from app.core.database import AsyncSession
from app.services.agents.thought_stream import ThoughtStream, ThoughtType
from app.services.agents.state_registry import StateManager
from app.utils.sql_validation import validate_sql_query
from app.services.context_store import context_store

# Import centralized intent system
from app.models.intent import (
    IntentType,
    Domain,
    DataSource,
    IntentClassification,
    AgentResponse,
    INTENT_AGENT_MAP,
    INTENT_DEFAULT_SOURCES,
)

logger = structlog.get_logger()


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
        from .intent_classifier_v5 import IntentClassifierV5

        # V5 ACTIVATED (Phase 2): Clean classifier using centralized intent system
        # - Uses app.models.intent directly
        # - Simplified logic (70% Quick Rules + 30% LLM)
        # - Returns IntentClassification model
        # - No legacy enum complexity

        # SPRINT 1 OPTIMIZATIONS (Phase 2.5): Level 0 Bypass
        # - Template Filter: 10% bypass (greetings, thanks, etc.)
        # - UI Context Bypass: 30% bypass (UI mode, action buttons)
        # - Total: 40% queries never hit classification (0ms, $0)
        from app.services.template_filter import TemplateFilter, UIContextBypass

        # Only instantiate what we actually use
        self.intent_classifier = IntentClassifierV5()  # V5 replaces V4
        self.hybrid_executor = HybridExecutor()
        self.fusion_agent = ResponseFusionAgent()

        # Level 0 optimization
        self.template_filter = TemplateFilter()
        self.ui_context_bypass = UIContextBypass()

        logger.info("orchestrator_agent_initialized",
                   version="v5.1_sprint1",
                   classifier="v5",
                   optimizations=["template_filter", "ui_context_bypass"])

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
            # Use v5 simplified classifier with centralized intent system
            classification_result = await self.intent_classifier.classify(
                user_input=user_input,
                context=context,
                conversation_history=conversation_history,
            )

            # Log detailed classification info
            logger.info("intention_classified_v5",
                       user_input=user_input[:50],
                       intent=classification_result.intent.value,
                       domain=classification_result.domain.value,
                       confidence=classification_result.confidence,
                       suggested_sources=[s.value for s in classification_result.suggested_sources],
                       reasoning=classification_result.reasoning[:100] if classification_result.reasoning else None)

            # If requires clarification, log it
            if classification_result.needs_clarification:
                logger.warning("low_confidence_classification",
                             confidence=classification_result.confidence,
                             clarification=classification_result.clarification_question)

            # Return intent and full classification (no conversion needed - enums are preserved)
            return classification_result.intent, classification_result

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
        state_manager = None,
        selected_sources: Optional[List[str]] = None,  # ['sql', 'rag', 'web'] or None for auto
        session_id: Optional[str] = None  # For context_store
    ) -> AgentResponse:
        """
        Main orchestration method - routes to appropriate agents

        Args:
            user_input: User's message
            db: Database session
            context: Optional context (files, metadata)
            conversation_history: Previous messages
            selected_sources: User-selected sources (['sql', 'rag', 'web']) or None for auto-detection

        Returns:
            AgentResponse with results
        """
        try:
            # ================================================================
            # NIVEAU 0: PRE-FILTRAGE (40% bypass) - Sprint 1 Optimization
            # ================================================================
            # Check template patterns first (greetings, thanks, etc.)
            template_result = self.template_filter.check(user_input)

            if template_result and template_result.get('bypass_sma'):
                # Full bypass - return canned response immediately
                logger.info("level_0_bypass_sma",
                           method=template_result.get('method'),
                           category=template_result.get('category'))

                return AgentResponse(
                    success=True,
                    message=template_result['response'],
                    data={},
                    agents_used=['TemplateFilter'],
                    sources_used=[],
                    confidence=1.0,
                    suggestions=[],
                    warnings=[]
                )

            # Check UI context (UI mode, action buttons, selected docs)
            if context is None:
                context = {}

            ui_bypass_result = self.ui_context_bypass.check(context)

            # Store bypass results for later use in classification
            bypass_intent = None
            bypass_classification = None

            if template_result and template_result.get('bypass_classification'):
                # Skip classification but continue to SMA
                bypass_intent = template_result['intent']
                bypass_classification = IntentClassification(
                    intent=template_result['intent'],
                    domain=template_result['domain'],
                    confidence=template_result['confidence'],
                    reasoning=template_result['reasoning'],
                    multi_step_plan=None  # Bypass always single-step
                )
                logger.info("level_0_bypass_classification_template",
                           intent=bypass_intent.value,
                           method=template_result.get('method'))

            elif ui_bypass_result and ui_bypass_result.get('bypass_classification'):
                # Skip classification but continue to SMA
                bypass_intent = ui_bypass_result['intent']
                bypass_classification = IntentClassification(
                    intent=ui_bypass_result['intent'],
                    domain=ui_bypass_result['domain'],
                    confidence=ui_bypass_result['confidence'],
                    reasoning=ui_bypass_result['reasoning'],
                    multi_step_plan=None  # Bypass always single-step
                )
                logger.info("level_0_bypass_classification_ui",
                           intent=bypass_intent.value,
                           method=ui_bypass_result.get('method'))

            # ================================================================
            # CONTINUE NORMAL FLOW (with or without bypass)
            # ================================================================

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

            # 2. Check if we have a bypass classification from Level 0
            if bypass_classification is not None:
                # Use bypassed intent directly (skip classification)
                intent = bypass_intent
                classification_result = bypass_classification
                logger.info("using_bypass_classification", intent=intent.value, method=classification_result.reasoning)

                # Continue to agent execution (skip to line ~410)

            # 3. User-controlled source routing (bypass intent classifier if sources specified)
            elif selected_sources is not None and len(selected_sources) > 0:
                logger.info("user_controlled_routing", selected_sources=selected_sources)

                if thought_stream:
                    sources_str = ", ".join(selected_sources)
                    await thought_stream.add_thought(
                        ThoughtType.PLANNING,
                        title=f"Sources sélectionnées : {sources_str}",
                        content=f"Vous avez choisi de rechercher dans : {sources_str}. Je vais interroger ces sources en parallèle.",
                        agent="orchestrator",
                        progress=0.15
                    )

                # Route directly based on user selection
                if len(selected_sources) == 1:
                    # Single source execution
                    source = selected_sources[0]
                    if source == 'sql':
                        intent = IntentType.QUERY_DATA
                        classification_result = None
                    elif source == 'rag':
                        intent = IntentType.SEARCH_DOCUMENTS
                        classification_result = None
                    elif source == 'web':
                        intent = IntentType.WEB_SEARCH
                        classification_result = None
                    else:
                        # Fallback to classifier for unknown sources
                        logger.warning("unknown_source", source=source)
                        intent, classification_result = await self.classify_intention(
                            user_input, context, state_manager, conversation_history
                        )
                else:
                    # Multi-source execution (HYBRID)
                    logger.info("hybrid_execution_requested", sources=selected_sources)

                    # Update state_manager with active_document_ids from context (if provided)
                    if context and "active_document_ids" in context and state_manager:
                        doc_ids = context["active_document_ids"]
                        if doc_ids and len(doc_ids) > 0:
                            state_manager.state.set_active_document_ids(doc_ids)
                            logger.info("hybrid_active_docs_set_from_context", doc_ids=doc_ids)

                    return await self._execute_hybrid_sources(
                        user_input=user_input,
                        db=db,
                        selected_sources=selected_sources,
                        thought_stream=thought_stream,
                        state_manager=state_manager,
                        conversation_history=conversation_history
                    )
            else:
                # No bypass, no source selected → Call classifier to determine intent
                logger.info("calling_classifier", message="No bypass or source selection, classifying intent")

                if thought_stream:
                    await thought_stream.add_thought(
                        ThoughtType.CLASSIFYING,
                        title="Classification de l'intention",
                        content="Analyse de votre demande pour déterminer la meilleure façon d'y répondre...",
                        agent="intent_classifier",
                        progress=0.15
                    )

                # Call the intent classifier
                intent, classification_result = await self.classify_intention(
                    user_input=user_input,
                    context=context,
                    state_manager=state_manager,
                    conversation_history=conversation_history
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
            if classification_result and hasattr(classification_result, 'multi_step_plan') and classification_result.multi_step_plan:
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
                    IntentType.TRIGGER_WORKFLOW: "Workflow Agent (déclenchement N8N)",
                    IntentType.GENERAL_QUESTION: "LLM Direct (Mistral/GPT-4o)",
                    IntentType.WEB_SEARCH: "Web Search Agent (Tavily API)",
                    IntentType.LEGAL: "Legal Agent (analyse juridique)",
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
                    user_input, db, context, thought_stream, state_manager, conversation_history, session_id
                )

            elif intent == IntentType.REQUEST_QUOTES:
                return await self._handle_request_quotes(user_input, db)

            elif intent == IntentType.TRIGGER_WORKFLOW:
                return await self._handle_trigger_workflow(
                    user_input, db, context, thought_stream, conversation_history, session_id
                )

            # NEW Phase 2 agents
            elif intent == IntentType.WEB_SEARCH:
                return await self._handle_web_search(user_input, thought_stream, conversation_history)

            elif intent == IntentType.LEGAL:
                return await self._handle_legal(user_input, context, db, thought_stream)

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

        # Return SQL response without inline sources (sources in data only)
        # Frontend will display them in SourceCitationFooter
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
        Handle document search via RAG - Uses HybridExecutor for consistent enriched CoT
        """
        try:
            logger.info("handling_search_documents", query=user_input[:50])

            # Update state_manager with active_document_ids from context (if provided)
            if context and "active_document_ids" in context and state_manager:
                doc_ids = context["active_document_ids"]
                if doc_ids and len(doc_ids) > 0:
                    state_manager.state.set_active_document_ids(doc_ids)
                    logger.info("rag_active_docs_set_from_context", doc_ids=doc_ids)

            # Use HybridExecutor with RAG_ONLY intent for consistent enriched CoT
            hybrid_result = await self.hybrid_executor.execute_hybrid(
                query=user_input,
                db=db,
                state_manager=state_manager,
                intent="RAG_ONLY",
                thought_stream=thought_stream
            )

            # Use ResponseFusionAgent to format the response (same as hybrid mode)
            if hybrid_result.has_rag and hybrid_result.rag_result:
                fused = await self.fusion_agent.fuse_responses(user_input, hybrid_result)

                # Prepare response data with sources
                response_data = {}
                if hybrid_result.rag_result.data:
                    response_data = hybrid_result.rag_result.data

                return AgentResponse(
                    success=fused.text != "",
                    message=fused.text,
                    data=response_data,
                    agents_used=["rag_agent"],
                    confidence=hybrid_result.rag_result.confidence
                )
            else:
                # No RAG results found
                return AgentResponse(
                    success=True,
                    message="Je n'ai trouvé aucune information pertinente dans les documents disponibles.",
                    agents_used=["rag_agent"],
                    confidence=0.0,
                    data={"sources": []}
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
        state_manager = None,
        conversation_history: List[Dict[str, Any]] = None,
        session_id: Optional[str] = None
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
                        # Handle both dict format ({email: "...", name: "..."}) and string format
                        for email_item in result_data["emails_available"]:
                            if email_item:  # Skip None/empty
                                if isinstance(email_item, dict):
                                    email_value = email_item.get("email", str(email_item))
                                    recipients_found.append(str(email_value))
                                else:
                                    recipients_found.append(str(email_item))
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

            # Step 4: Generate email draft with conversation history
            return await self._handle_send_email(user_input, db, context, conversation_history, session_id)

        except Exception as e:
            logger.error("intelligent_email_handling_failed", error=str(e), exc_info=True)
            # Fallback to standard email handling
            return await self._handle_send_email(user_input, db, context, conversation_history, session_id)

    async def _handle_send_email(
        self,
        user_input: str,
        db: AsyncSession,
        context: Dict[str, Any] = None,
        conversation_history: List[Dict[str, Any]] = None,
        session_id: Optional[str] = None
    ) -> AgentResponse:
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
            # Handle both dict format ({email: "...", name: "..."}) and string format
            recipient_strs = []
            for recipient in recipients_from_context:
                if isinstance(recipient, dict):
                    recipient_strs.append(recipient.get("email", str(recipient)))
                else:
                    recipient_strs.append(str(recipient))
            enriched_input += f"\n\nDestinataires suggérés: {', '.join(recipient_strs)}"

        # Extract workflow_context if available
        workflow_context = context.get("workflow_data") if context else None

        # PRIORITY 1: Try context_store first (most reliable)
        if not workflow_context and session_id:
            workflow_context = context_store.get_workflow(session_id)
            if workflow_context:
                logger.info("workflow_context_retrieved_from_store", session_id=session_id)

        # PRIORITY 2: If no workflow_context, try to extract from conversation history
        # Look for recent workflow responses (WorkflowAgent V2)
        if not workflow_context and conversation_history:
            # Search backwards through last 5 messages
            for msg in reversed(conversation_history[-5:]):
                if msg.get("role") == "assistant":
                    # Check if message contains workflow data (from state/metadata)
                    msg_metadata = msg.get("metadata", {})
                    if "workflow_data" in msg_metadata:
                        workflow_context = msg_metadata["workflow_data"]
                        logger.info("workflow_context_extracted_from_history")
                        break
                    # Also check response data field
                    msg_data = msg.get("data", {})
                    if "workflow_data" in msg_data:
                        workflow_context = msg_data["workflow_data"]
                        logger.info("workflow_context_extracted_from_message_data")
                        break

        # Step 1: Generate email draft with full context
        email_draft = await email_agent.generate_email(
            user_request=enriched_input,
            db=db,
            recipients=None,
            conversation_history=conversation_history,
            workflow_context=workflow_context
        )
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
        # Handle both dict format and string format for recipients
        recipient_display = []
        if recipients:
            for recipient in recipients:
                if isinstance(recipient, dict):
                    recipient_display.append(recipient.get("email", str(recipient)))
                else:
                    recipient_display.append(str(recipient))

        message_parts = [
            "📧 **Brouillon d'email généré**\n",
            f"\n**Destinataires:** {', '.join(recipient_display) if recipient_display else 'Non spécifiés'}",
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

        # Step 3: Return prepared email drafts for user validation
        # TODO: Implement N8N workflow trigger for bulk sending after user confirms

        return AgentResponse(
            success=True,
            message=template_result["message"],
            data={
                "vendors": vendors_result.get("data", {}).get("vendors", []),
                "email_template": template_result.get("data", {}),
                "next_action": "validate_and_send"
            },
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

    async def _handle_trigger_workflow(
        self,
        user_input: str,
        db: AsyncSession,
        context: Optional[Dict[str, Any]] = None,
        thought_stream: Optional[ThoughtStream] = None,
        conversation_history: List[Dict[str, str]] = None,
        session_id: Optional[str] = None
    ) -> AgentResponse:
        """
        Handle workflow automation triggers with intelligent to-do list generation

        V2 Architecture (inspired by LegalAgent):
        - WorkflowAgent V2 analyzes the problem
        - Classifies workflow type (emergency, communication, maintenance, etc.)
        - Extracts context entities
        - Generates intelligent to-do list
        - Returns enriched workflow for user validation
        """
        try:
            from .workflow_agent_v2 import WorkflowAgentV2

            # Initialize WorkflowAgent V2
            workflow_agent = WorkflowAgentV2()

            logger.info("workflow_agent_v2_processing", query=user_input[:100])

            # Call WorkflowAgent V2 with full context
            result = await workflow_agent.process_request(
                user_input=user_input,
                context=context,
                db=db,
                thought_stream=thought_stream
            )

            # Store workflow context in context_store for other agents (e.g., EmailAgent)
            if session_id and result["success"]:
                workflow_data = {
                    "workflow_type": result.get("workflow_type"),
                    "subtype": result.get("subtype"),
                    "confidence": result.get("confidence"),
                    "context_data": result.get("context_data", {}),
                    "todo_list": result.get("todo_list", {})
                }
                context_store.set_workflow(session_id, workflow_data)
                logger.info("workflow_context_stored",
                           session_id=session_id,
                           workflow_type=result.get("workflow_type"))

            # Return formatted response
            return AgentResponse(
                success=result["success"],
                message=result["message"],
                data={
                    "workflow_type": result.get("workflow_type"),
                    "subtype": result.get("subtype"),
                    "confidence": result.get("confidence"),
                    "context_data": result.get("context_data", {}),
                    "todo_list": result.get("todo_list", {})
                },
                agents_used=["workflow_agent_v2"],
                confidence=result.get("confidence", 0.85)
            )

        except Exception as e:
            logger.error("workflow_agent_v2_failed", error=str(e), exc_info=True)
            return AgentResponse(
                success=False,
                message=f"Erreur lors de l'analyse du workflow: {str(e)}",
                agents_used=["workflow_agent_v2"]
            )

    # ========== NEW PHASE 2 AGENT HANDLERS ==========

    async def _handle_web_search(self, user_input: str, thought_stream: ThoughtStream = None, conversation_history: List[Dict] = None) -> AgentResponse:
        """Handle web search requests - Unified format with CoT and elegant sources"""
        try:
            from .websearch_agent import WebSearchAgent

            web_agent = WebSearchAgent()

            # Thought 1: Starting search - DeepSeek narrative style
            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.EXECUTING,
                    title="Ok, je lance une recherche sur internet. J'utilise DuckDuckGo pour trouver les informations les plus récentes et pertinentes.",
                    content="",  # Empty for DeepSeek style
                    agent="websearch",
                    progress=0.4
                )

            # Perform search with conversation history for contextual understanding
            search_results = await web_agent.search(
                query=user_input,
                num_results=5,
                search_depth="basic",
                region="fr-fr",
                conversation_history=conversation_history
            )

            # Thought 2: Results found - DeepSeek narrative style WITH METADATA (like RAG)
            if thought_stream:
                if search_results.results:
                    # Calculate metadata for rich CoT (similar to RAG)
                    top_scores = [r.relevance_score for r in search_results.results[:3]]
                    scores_display = [f'{int(s*100)}%' for s in top_scores if s > 0]
                    avg_score = sum(top_scores) / len(top_scores) if top_scores else 0

                    # Extract domains for context
                    domains = []
                    for r in search_results.results[:3]:
                        if r.url:
                            try:
                                domain = r.url.split("/")[2]
                                domains.append(domain)
                            except:
                                pass
                    domains_str = ", ".join(set(domains[:3])) if domains else "sources web variées"

                    # Quality assessment based on scores (like RAG)
                    if avg_score >= 0.8:
                        quality_assessment = f"Excellent ! Les sources semblent très fiables ({', '.join(scores_display[:3])}). Sources principales : {domains_str}."
                    elif avg_score >= 0.6:
                        quality_assessment = f"Scores corrects ({', '.join(scores_display[:3])}). Les informations sont utiles. Sources : {domains_str}."
                    else:
                        quality_assessment = f"Scores moyens ({', '.join(scores_display[:3])}). Les sources web ne sont peut-être pas totalement pertinentes. Sources : {domains_str}."

                    await thought_stream.add_thought(
                        ThoughtType.COMPLETED,
                        title=f"Trouvé {len(search_results.results)} sources web. Meilleurs scores : {', '.join(scores_display[:3])}. {quality_assessment}",
                        content="",  # Empty for DeepSeek style
                        agent="websearch",
                        progress=0.7
                    )
                else:
                    await thought_stream.add_thought(
                        ThoughtType.COMPLETED,
                        title="Hmm, aucun résultat pertinent trouvé sur le web. Soit l'information n'est pas publiquement disponible, soit il faudrait reformuler la question différemment.",
                        content="",  # Empty for DeepSeek style
                        agent="websearch",
                        progress=0.7
                    )

            # Build structured sources for frontend (same format as RAG/SQL)
            structured_sources = []
            for idx, result in enumerate(search_results.results[:5], 1):
                # Extract domain for cleaner display
                domain = ""
                if result.url:
                    try:
                        domain = result.url.split("/")[2]
                    except:
                        domain = result.url

                structured_sources.append({
                    "type": "web",
                    "id": idx,
                    "title": result.title,
                    "url": result.url,
                    "excerpt": result.snippet,
                    "text": result.snippet,  # For display consistency
                    "confidence": result.relevance_score,
                    "score": result.relevance_score,
                    "metadata": {
                        "domain": domain,
                        "source": "duckduckgo"
                    }
                })

            # Use synthesized answer from WebSearchAgent (already uses Mistral LLM with citations)
            if search_results.synthesized_answer:
                response_message = search_results.synthesized_answer
            else:
                # Fallback: Create basic synthesis if LLM failed
                if search_results.results:
                    response_message = f"Voici les informations trouvées sur internet concernant « {user_input} » :\n\n"
                    for idx, result in enumerate(search_results.results[:3], 1):
                        response_message += f"{idx}. {result.snippet[:200]}...\n\n"
                else:
                    response_message = f"❌ Aucune information trouvée sur internet pour : « {user_input} ».\n\n**Suggestions** :\n- Reformulez avec d'autres mots\n- Vérifiez l'orthographe\n- Essayez une question plus générale"

            # Thought 3: Synthesis complete - DeepSeek narrative style WITH METADATA
            if thought_stream:
                if structured_sources:
                    # Calculate synthesis confidence (similar to RAG)
                    synthesis_confidence = int(search_results.confidence * 100) if search_results.confidence else 0
                    source_count = len(structured_sources)

                    # Build natural narrative based on confidence
                    if synthesis_confidence >= 80:
                        confidence_narrative = f"Parfait ! J'ai synthétisé {source_count} sources avec {synthesis_confidence}% de confiance. Les informations sont claires et cohérentes."
                    elif synthesis_confidence >= 60:
                        confidence_narrative = f"Synthèse terminée avec {synthesis_confidence}% de confiance sur {source_count} sources. Les informations sont utiles mais parfois incomplètes."
                    else:
                        confidence_narrative = f"Synthèse terminée mais ma confiance est moyenne ({synthesis_confidence}%). Les {source_count} sources ne couvrent peut-être pas complètement le sujet."

                    await thought_stream.add_thought(
                        ThoughtType.COMPLETED,
                        title=confidence_narrative,
                        content="",  # Empty for DeepSeek style
                        agent="synthesis",
                        progress=1.0
                    )
                else:
                    await thought_stream.add_thought(
                        ThoughtType.COMPLETED,
                        title="Synthèse terminée mais aucune source fiable trouvée. La réponse risque d'être limitée.",
                        content="",
                        agent="synthesis",
                        progress=1.0
                    )

            return AgentResponse(
                success=True,
                message=response_message,
                data={
                    "sources": structured_sources,  # Structured format for frontend
                    "source_count": len(structured_sources),
                    "search_provider": "duckduckgo"
                },
                agents_used=["websearch_agent"],
                confidence=search_results.confidence
            )

        except Exception as e:
            error_str = str(e).lower()
            logger.error("web_search_failed", error=str(e), exc_info=True)

            # User-friendly error messages
            if "ratelimit" in error_str or "202" in error_str:
                user_message = "⚠️ Le service de recherche web est temporairement surchargé. Veuillez réessayer dans quelques secondes."
            else:
                user_message = f"❌ Erreur lors de la recherche web : {str(e)}\n\n**Suggestions** :\n- Réessayez dans quelques secondes\n- Vérifiez votre connexion internet\n- Utilisez d'autres sources (documents, base de données)"

            return AgentResponse(
                success=False,
                message=user_message,
                agents_used=["websearch_agent"],
                data={"sources": []}
            )

    async def _handle_legal(
        self,
        user_input: str,
        context: Dict[str, Any],
        db: AsyncSession,
        thought_stream: ThoughtStream = None
    ) -> AgentResponse:
        """
        Unified handler for all legal requests.

        Architecture principle:
        - Orchestrator routes to LegalAgent (decides WHICH agent)
        - LegalAgent decides the specific action (decides HOW to process)

        This handler simply passes the raw request to LegalAgent.process_request(),
        which will internally classify the intent and call the appropriate method
        (analyze, compare, advise, search jurisprudence).
        """
        try:
            from .legal_agent import LegalAgent

            legal_agent = LegalAgent()

            # Add initial thought
            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.ANALYZING,
                    title="Traitement de la demande juridique",
                    content="Analyse de votre demande juridique...",
                    agent="legal_agent",
                    progress=0.3
                )

            # Pass raw request to LegalAgent - it will decide what to do
            # IMPORTANT: Pass thought_stream so Legal Agent can display its Chain of Thought
            result = await legal_agent.process_request(
                user_input=user_input,
                context=context,
                db=db,
                thought_stream=thought_stream
            )

            # Update thought based on action performed
            if thought_stream:
                action_labels = {
                    "analyze": "Analyse juridique",
                    "compare": "Comparaison juridique",
                    "advice": "Conseil juridique",
                    "jurisprudence": "Recherche de jurisprudence"
                }
                action_label = action_labels.get(result.get("action", "unknown"), "Traitement juridique")

                await thought_stream.add_thought(
                    ThoughtType.COMPLETED,
                    title=f"{action_label} terminée",
                    content="",
                    agent="legal_agent",
                    progress=0.9
                )

            # Flatten sources if needed (for FastAPI validation)
            flattened_data = result.get("result", {}).copy()
            if "sources" in flattened_data and isinstance(flattened_data["sources"], dict):
                all_sources = []
                for source_type, items in flattened_data["sources"].items():
                    if isinstance(items, list):
                        for item in items:
                            if isinstance(item, dict):
                                item["source_type"] = source_type
                                all_sources.append(item)
                flattened_data["sources"] = all_sources

            # Return AgentResponse
            return AgentResponse(
                success=result.get("success", False),
                message=result.get("message", ""),
                data=flattened_data,
                agents_used=["legal_agent"],
                confidence=result.get("result", {}).get("confidence", 0.8)
            )

        except Exception as e:
            logger.error("legal_request_failed", error=str(e), exc_info=True)
            return AgentResponse(
                success=False,
                message=f"Erreur lors du traitement de la demande juridique: {str(e)}",
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
            IntentType.TRIGGER_WORKFLOW: self._handle_trigger_workflow,
            IntentType.WEB_SEARCH: self._handle_web_search,
            IntentType.LEGAL: self._handle_legal,  # Single LEGAL intent (agent decides action internally)
            IntentType.GENERAL_QUESTION: self._handle_general_question,
            # Legacy (backward compatibility)
            IntentType.HYBRID_QUERY: self._handle_query_data,  # DEPRECATED: Route to QUERY_DATA
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

    async def _execute_hybrid_sources(
        self,
        user_input: str,
        db,
        selected_sources: List[str],
        thought_stream=None,
        state_manager=None,
        conversation_history: List[Dict] = None
    ) -> AgentResponse:
        """
        Execute multiple sources in parallel (user-controlled HYBRID mode)

        This is the core of the Search-First architecture:
        - User selects ['sql', 'rag'] → Execute both in parallel
        - User selects ['sql', 'rag', 'web'] → Execute all three
        - Results are fused intelligently by ResponseFusionAgent

        Args:
            user_input: User's query
            db: Database session
            selected_sources: List of sources to query
            thought_stream: Optional thought stream
            state_manager: State manager

        Returns:
            AgentResponse with fused results from all sources
        """
        try:
            logger.info("hybrid_sources_execution_started",
                       query=user_input[:50],
                       sources=selected_sources)

            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.EXECUTING,
                    title=f"D'accord, je lance des recherches parallèles dans {', '.join(selected_sources)} pour avoir une vue complète.",
                    content="",  # Empty for DeepSeek style
                    agent="orchestrator",
                    progress=0.4
                )

            # Execute HybridExecutor based on selected sources
            has_web = 'web' in selected_sources
            has_sql = 'sql' in selected_sources
            has_rag = 'rag' in selected_sources

            # Web only
            if has_web and not has_sql and not has_rag:
                return await self._handle_web_search(user_input, thought_stream, conversation_history)

            # Execute SQL/RAG sources first
            sql_rag_response = None
            web_response = None

            # Execute all selected sources in parallel
            import asyncio as aio
            tasks = []
            task_names = []

            # SQL/RAG task
            if has_sql or has_rag:
                intent = "HYBRID" if has_sql and has_rag else ("SQL_ONLY" if has_sql else "RAG_ONLY")
                logger.info("hybrid_executor_intent", intent=intent, has_sql=has_sql, has_rag=has_rag, selected_sources=selected_sources)

                async def run_sql_rag():
                    return await self.hybrid_executor.execute_hybrid(
                        query=user_input,
                        db=db,
                        state_manager=state_manager,
                        intent=intent,
                        thought_stream=thought_stream
                    )
                tasks.append(run_sql_rag())
                task_names.append("sql_rag")

            # Web task - Use enriched CoT version
            if has_web:
                async def run_web():
                    from .websearch_agent import WebSearchAgent
                    web_agent = WebSearchAgent()

                    # Thought 1: Starting web search - DeepSeek narrative style
                    if thought_stream:
                        await thought_stream.add_thought(
                            ThoughtType.EXECUTING,
                            title="Ok, je lance aussi une recherche sur internet. J'utilise DuckDuckGo pour trouver les informations les plus récentes et pertinentes.",
                            content="",
                            agent="websearch",
                            progress=0.4
                        )

                    # Perform search with conversation history
                    search_results = await web_agent.search(
                        query=user_input,
                        num_results=5,
                        region="fr-fr",
                        conversation_history=conversation_history
                    )

                    # Thought 2: Results found - DeepSeek narrative style WITH METADATA
                    if thought_stream:
                        if search_results.results:
                            # Calculate metadata for rich CoT
                            top_scores = [r.relevance_score for r in search_results.results[:3]]
                            scores_display = [f'{int(s*100)}%' for s in top_scores if s > 0]
                            avg_score = sum(top_scores) / len(top_scores) if top_scores else 0

                            # Extract domains
                            domains = []
                            for r in search_results.results[:3]:
                                if r.url:
                                    try:
                                        domain = r.url.split("/")[2]
                                        domains.append(domain)
                                    except:
                                        pass
                            domains_str = ", ".join(set(domains[:3])) if domains else "sources web variées"

                            # Quality assessment
                            if avg_score >= 0.8:
                                quality_assessment = f"Excellent ! Les sources web semblent très fiables ({', '.join(scores_display[:3])}). Sources principales : {domains_str}."
                            elif avg_score >= 0.6:
                                quality_assessment = f"Scores corrects ({', '.join(scores_display[:3])}). Les informations web sont utiles. Sources : {domains_str}."
                            else:
                                quality_assessment = f"Scores moyens ({', '.join(scores_display[:3])}). Les sources web ne sont peut-être pas totalement pertinentes. Sources : {domains_str}."

                            await thought_stream.add_thought(
                                ThoughtType.COMPLETED,
                                title=f"Trouvé {len(search_results.results)} sources web. Meilleurs scores : {', '.join(scores_display[:3])}. {quality_assessment}",
                                content="",
                                agent="websearch",
                                progress=0.7
                            )
                        else:
                            await thought_stream.add_thought(
                                ThoughtType.COMPLETED,
                                title="Hmm, aucun résultat pertinent trouvé sur le web pour enrichir la réponse.",
                                content="",
                                agent="websearch",
                                progress=0.7
                            )

                    return search_results

                tasks.append(run_web())
                task_names.append("web")

            # Execute all tasks in parallel
            results = await aio.gather(*tasks, return_exceptions=True)

            # Process results
            sql_rag_result = None
            web_result = None
            agents_used = []

            for i, name in enumerate(task_names):
                if isinstance(results[i], Exception):
                    logger.error(f"hybrid_task_failed", task=name, error=str(results[i]))
                    continue
                if name == "sql_rag":
                    sql_rag_result = results[i]
                    if sql_rag_result.has_sql:
                        agents_used.append("sql_agent")
                    if sql_rag_result.has_rag:
                        agents_used.append("rag_agent")
                elif name == "web":
                    web_result = results[i]
                    if web_result and web_result.results:
                        agents_used.append("websearch_agent")

            # Build response using unified fusion approach
            response_data = {"sources": selected_sources}
            all_sources = []

            # Case 1: No web - use ResponseFusionAgent (already works well for SQL+RAG)
            if not has_web and sql_rag_result:
                fused = await self.fusion_agent.fuse_responses(user_input, sql_rag_result)

                if thought_stream:
                    await thought_stream.add_thought(
                        ThoughtType.COMPLETED,
                        title="Terminé",
                        content="",
                        agent="orchestrator"
                    )

                # Update response_data with SQL results if any
                if sql_rag_result.has_sql and sql_rag_result.sql_result.data:
                    response_data.update(sql_rag_result.sql_result.data)

                return AgentResponse(
                    success=fused.text != "",
                    message=fused.text,
                    data=response_data,
                    agents_used=agents_used
                )

            # Case 2: With web - create unified fusion with all sources
            # Collect data for fusion
            sql_data_formatted = ""
            rag_chunks_text = ""
            web_text = ""

            # Format SQL data - ONLY if SQL was selected
            if has_sql and sql_rag_result and sql_rag_result.has_sql:
                sql_data = sql_rag_result.sql_result.data
                rows = sql_data.get("results", []) if sql_data else []
                if rows:
                    response_data.update(sql_rag_result.sql_result.data)
                    sql_data_formatted = await self.fusion_agent._format_sql_results(user_input, rows)
                    all_sources.append({"type": "sql", "title": "Base de données DisruptIQ"})
            else:
                logger.info("sql_not_selected_or_no_results", has_sql=has_sql, selected=selected_sources)

            # Get RAG raw chunks - ONLY if RAG was selected
            rag_duplicates_count = 0
            if has_rag and sql_rag_result and sql_rag_result.has_rag:
                rag_data = sql_rag_result.rag_result.data or {}
                chunks = rag_data.get("chunks", [])
                rag_sources = rag_data.get("sources", [])

                if chunks:
                    # Track seen sources to deduplicate
                    seen_sources = {}
                    total_chunks = len(chunks[:10])

                    # Use more chunks and longer content to preserve all RAG information
                    for i, chunk in enumerate(chunks[:10], 1):
                        source_name = chunk.get("source", chunk.get("metadata", {}).get("filename", "Document"))
                        content = chunk.get("text", chunk.get("content", ""))[:1500]  # Increased from 600

                        # Deduplicate by source name
                        if source_name in seen_sources:
                            rag_duplicates_count += 1
                            # Merge content from duplicate source
                            existing_idx = seen_sources[source_name]
                            continue

                        seen_sources[source_name] = len(all_sources)
                        rag_chunks_text += f"**[Document {i}: {source_name}]**\n{content}\n\n"

                        all_sources.append({
                            "type": "rag",
                            "id": i,
                            "title": source_name,
                            "document": source_name,
                            "confidence": chunk.get("score", chunk.get("cross_encoder_score", 0.5))
                        })

            # Format Web results - Include URLs in context for proper citations
            if web_result and web_result.results:
                web_parts = []
                if web_result.synthesized_answer:
                    web_parts.append(web_result.synthesized_answer)
                # Add source attribution for each result
                for idx, r in enumerate(web_result.results[:3], 1):
                    domain = r.url.split("/")[2] if r.url and "/" in r.url else "web"
                    web_parts.append(f"**[Source {idx}: {r.title}]** ({domain})")
                    all_sources.append({
                        "type": "web",
                        "id": idx,
                        "title": r.title,
                        "url": r.url
                    })
                web_text = "\n".join(web_parts)

            # Check if we have any content
            if not sql_data_formatted and not rag_chunks_text and not web_text:
                return AgentResponse(
                    success=False,
                    message="❌ Aucune information trouvée dans les sources sélectionnées.",
                    data={},
                    agents_used=agents_used
                )

            # Create unified fusion with LLM
            fused_message = await self._create_unified_fusion_v2(
                query=user_input,
                sql_data=sql_data_formatted,
                rag_chunks=rag_chunks_text,
                web_text=web_text,
                all_sources=all_sources
            )

            # Add deduplication info to thought stream
            if thought_stream and rag_duplicates_count > 0:
                await thought_stream.add_thought(
                    ThoughtType.PROCESSING,
                    title=f"Nettoyage : {rag_duplicates_count} doublon(s) supprimé(s) des sources pour éviter la répétition.",
                    content="",
                    agent="orchestrator"
                )

            # Thought 3: Synthesis complete with metadata (enriched)
            if thought_stream:
                # Count sources by type for narrative
                sources_by_type = {"sql": 0, "rag": 0, "web": 0}
                for src in all_sources:
                    src_type = src.get("type", "")
                    if src_type in sources_by_type:
                        sources_by_type[src_type] += 1

                # Build source summary
                source_parts = []
                if sources_by_type["sql"] > 0:
                    source_parts.append(f"{sources_by_type['sql']} source(s) SQL")
                if sources_by_type["rag"] > 0:
                    source_parts.append(f"{sources_by_type['rag']} document(s)")
                if sources_by_type["web"] > 0:
                    source_parts.append(f"{sources_by_type['web']} source(s) web")

                source_summary = " + ".join(source_parts) if source_parts else "sources multiples"
                total_sources = sum(sources_by_type.values())

                # Calculate average confidence if available
                confidences = [src.get("confidence", src.get("score", 0)) for src in all_sources if src.get("confidence") or src.get("score")]
                avg_confidence = int(sum(confidences) / len(confidences) * 100) if confidences else 0

                # Build narrative based on confidence and source diversity
                if avg_confidence >= 80:
                    synthesis_narrative = f"Parfait ! J'ai fusionné {total_sources} sources ({source_summary}) avec {avg_confidence}% de confiance. Les informations se complètent bien et sont cohérentes."
                elif avg_confidence >= 60:
                    synthesis_narrative = f"Synthèse terminée avec {avg_confidence}% de confiance sur {total_sources} sources ({source_summary}). Les informations sont utiles mais certaines sont incomplètes."
                else:
                    synthesis_narrative = f"Synthèse terminée mais ma confiance est moyenne ({avg_confidence}%). Les {total_sources} sources ({source_summary}) ne couvrent peut-être pas complètement le sujet."

                await thought_stream.add_thought(
                    ThoughtType.COMPLETED,
                    title=synthesis_narrative,
                    content="",
                    agent="synthesis"
                )

            # Replace string array with structured source objects for frontend display
            response_data["sources"] = all_sources
            response_data["duplicates_removed"] = rag_duplicates_count

            return AgentResponse(
                success=True,
                message=fused_message,
                data=response_data,
                agents_used=agents_used
            )

        except Exception as e:
            logger.error("hybrid_sources_execution_failed", error=str(e), exc_info=True)
            return AgentResponse(
                success=False,
                message=f"❌ Erreur lors de l'exécution multi-sources : {str(e)}",
                data={},
                agents_used=[]
            )

    async def _create_unified_fusion_v2(
        self,
        query: str,
        sql_data: str,
        rag_chunks: str,
        web_text: str,
        all_sources: List[Dict[str, Any]]
    ) -> str:
        """
        Create a unified, well-formatted response with proper sources
        V2: Better formatting, no redundancy, proper source attribution
        """
        try:
            # Build context sections
            context_sections = []
            if sql_data:
                context_sections.append(f"### BASE DE DONNÉES\n{sql_data}")
            if rag_chunks:
                context_sections.append(f"### DOCUMENTS\n{rag_chunks}")
            if web_text:
                context_sections.append(f"### INTERNET\n{web_text}")

            context = "\n\n".join(context_sections)

            # Build source citation guide based on actual sources used
            source_cite_examples = []
            if sql_data:
                source_cite_examples.append("(base de données)")
            if rag_chunks:
                # Extract actual document names from rag_chunks
                source_cite_examples.append("(document: [nom du fichier].pdf)")
            if web_text:
                # Extract actual domains from web sources
                web_domains = [s.get("url", "").split("/")[2] if s.get("url") and "/" in s.get("url", "") else ""
                              for s in all_sources if s.get("type") == "web"]
                web_domains = [d for d in web_domains if d][:2]
                if web_domains:
                    source_cite_examples.append(f"(web: {web_domains[0]})")
                else:
                    source_cite_examples.append("(web: [domaine])")
            source_cite_guide = ", ".join(source_cite_examples) if source_cite_examples else "(source)"

            fusion_prompt = f"""Tu es un assistant expert. Synthétise les informations ci-dessous en UNE réponse claire et complète.

**Question:** {query}

**Données collectées:**
{context}

---

**RÈGLES STRICTES:**
1. **UNE SEULE réponse fluide** - PAS de sections séparées par source
2. **Fusionne intelligemment** - Si une personne apparaît dans plusieurs sources, combine ses informations
3. **PRÉCISION FACTUELLE** - NE JAMAIS attribuer une information à la mauvaise personne. Si NEC+ est un prestataire de nettoyage, ne pas dire que "Laurent Moussu travaille chez NEC+"
4. **Zéro redondance** - Ne répète JAMAIS la même information
5. **Format markdown élégant:**
   - Utilise des titres ## si pertinent
   - **Gras** pour noms et infos clés
   - Listes à puces si plusieurs éléments
6. **AUCUNE citation inline** - NE JAMAIS écrire (document: x.pdf) ou (web: site.com) dans le texte car les sources sont affichées automatiquement en bas
7. **Commence directement** par la réponse, sans "Voici" ni préambule
8. **Inclus les détails importants** des documents (montants, dates, adresses, numéros)
9. **NE JAMAIS lister les sources à la fin** - Elles sont ajoutées automatiquement
10. **Termine proprement** - pas de phrase incomplète

**Réponse:**"""

            fused_content = await self.llm_service.generate_response(fusion_prompt)

            # Clean up any source lists the LLM might have added despite instructions
            import re
            # Remove patterns like "(Sources : ...)" or "Sources:" at the end
            fused_content = re.sub(r'\n*\*?\(Sources?\s*:.*?\)\*?\s*$', '', fused_content, flags=re.IGNORECASE | re.DOTALL)
            fused_content = re.sub(r'\n*Sources?\s*:\s*\[.*?\]\s*$', '', fused_content, flags=re.IGNORECASE | re.DOTALL)
            fused_content = fused_content.strip()

            # Return content without inline sources - frontend will display them
            return fused_content

        except Exception as e:
            logger.error("unified_fusion_v2_failed", error=str(e))
            return f"Erreur lors de la fusion: {str(e)}"

    def _format_sources_section(self, sources: List[Dict[str, Any]], min_score: float = 0.73) -> str:
        """Format sources as a clean markdown section with deduplication and relevance filtering"""
        if not sources:
            return ""

        lines = ["---", "### 📚 Sources"]
        seen = set()  # Track unique sources

        for src in sources:
            source_type = src.get("type", "unknown")

            # Filter out low-relevance RAG sources
            if source_type == "rag":
                score = src.get("confidence", src.get("score", 1.0))
                if score < min_score:
                    continue

            title = src.get("title", src.get("name", "Source"))
            url = src.get("url", src.get("link"))
            doc_name = src.get("document", title) if source_type == "rag" else title

            # Create unique key for deduplication
            unique_key = f"{source_type}:{doc_name}:{url or ''}"
            if unique_key in seen:
                continue
            seen.add(unique_key)

            if source_type == "sql":
                lines.append(f"- 🗄️ **Base de données**: {title}")
            elif source_type == "rag":
                lines.append(f"- 📄 **Document**: {doc_name}")
            elif source_type == "web":
                if url:
                    lines.append(f"- 🌐 **Web**: [{title}]({url})")
                else:
                    lines.append(f"- 🌐 **Web**: {title}")
            else:
                lines.append(f"- {title}")

        # Only return if we have actual sources (not just headers)
        if len(lines) <= 2:
            return ""

        return "\n".join(lines)

    async def _create_unified_fusion(
        self,
        query: str,
        context_parts: List[str],
        has_sql: bool,
        has_rag: bool,
        has_web: bool
    ) -> str:
        """
        Create a unified, coherent response from multiple sources using LLM
        """
        try:
            # Build source indicators
            sources_used = []
            if has_sql:
                sources_used.append("base de données")
            if has_rag:
                sources_used.append("documents")
            if has_web:
                sources_used.append("internet")

            context = "\n\n".join(context_parts)

            fusion_prompt = f"""Tu es un assistant expert qui synthétise des informations provenant de plusieurs sources pour répondre à une question.

**Question:** {query}

**Sources consultées:** {', '.join(sources_used)}

**Informations collectées:**
{context}

---

**Instructions STRICTES:**
1. Produis UNE SEULE réponse fluide et cohérente (pas de sections [BASE DE DONNÉES], [DOCUMENTS], etc.)
2. Fusionne intelligemment les informations - ne répète JAMAIS la même info
3. Si une personne apparaît dans plusieurs sources, combine toutes les infos sur elle
4. Cite les sources de façon légère: (base de données), (documents), (internet)
5. Si les sources se contredisent, mentionne-le brièvement
6. Inclus les informations IMPORTANTES des documents (contrats, rôles, etc.)
7. Format: texte fluide avec paragraphes, utilise **gras** pour les noms et infos clés
8. Commence directement par la réponse, sans préambule

**Réponse:**"""

            # Use the LLM for fusion
            return await self.llm_service.generate_response(fusion_prompt)

        except Exception as e:
            logger.error("unified_fusion_failed", error=str(e))
            # Fallback: return concatenated parts
            return "\n\n".join(context_parts)
