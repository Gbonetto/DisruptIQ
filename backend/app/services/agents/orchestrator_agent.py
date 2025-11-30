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

# Import Unified Context Manager (Phase 3 - World-Class SMA)
from app.services.unified_context import (
    UnifiedContextManager,
    get_unified_context_manager,
    UnifiedContext,
    ContextPriority
)

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
        from .llm_intent_classifier import classify_intent_with_llm

        # LLM CLASSIFIER ACTIVATED (Phase 3): Intelligent semantic routing
        # - Uses Mistral LLM for semantic understanding
        # - Conversation context aware
        # - Few-shot examples for each intent
        # - Fallback cascade (fast → accurate)
        # - Replaces keyword-based V5 for main classification

        # SPRINT 1 OPTIMIZATIONS (Phase 2.5): Level 0 Bypass
        # - Template Filter: 10% bypass (greetings, thanks, etc.)
        # - UI Context Bypass: 30% bypass (UI mode, action buttons)
        # - Total: 40% queries never hit classification (0ms, $0)
        from app.services.template_filter import TemplateFilter, UIContextBypass

        # WORLD-CLASS ROUTER (Phase 4): Perplexity-style multi-source routing
        # - Fast Pre-filter: ~1ms keyword detection
        # - Parallel Retrieval: Query multiple sources simultaneously
        # - Cross-Encoder Rerank: Score and filter results
        from app.services.agents.world_class_router import get_world_class_router, SourceType

        # Only instantiate what we actually use
        self.intent_classifier = IntentClassifierV5()  # Fallback/quick rules
        self.llm_classifier = classify_intent_with_llm  # Primary LLM-based classifier
        self.hybrid_executor = HybridExecutor()
        self.fusion_agent = ResponseFusionAgent()

        # Level 0 optimization
        self.template_filter = TemplateFilter()
        self.ui_context_bypass = UIContextBypass()

        # World-Class Router (lazy loaded)
        self._world_class_router = None

        logger.info("orchestrator_agent_initialized",
                   version="v7.0_world_class",
                   classifier="llm_groq",
                   fallback="v5_keywords",
                   optimizations=["template_filter", "ui_context_bypass", "world_class_router"])

    @property
    def world_class_router(self):
        """Lazy load the World-Class Router."""
        if self._world_class_router is None:
            from app.services.agents.world_class_router import get_world_class_router
            self._world_class_router = get_world_class_router()
        return self._world_class_router

    async def classify_intention(
        self,
        user_input: str,
        context: Dict[str, Any] = None,
        state_manager = None,
        conversation_history: List[Dict[str, str]] = None
    ) -> IntentType:
        """
        Classify user intention using LLM-based classifier (Phase 3)

        Uses Mistral LLM for semantic understanding with:
        - Conversation context awareness
        - Few-shot examples for each intent
        - Fallback cascade (fast model → accurate model)

        Args:
            user_input: User's message
            context: Optional context (uploaded files, conversation history)
            state_manager: State manager for accessing recent uploads
            conversation_history: Recent conversation messages

        Returns:
            IntentType enum
        """
        try:
            # Enrich context with last_intent for cascading queries
            enriched_context = dict(context) if context else {}

            # Extract last_intent from conversation history if available
            if conversation_history and len(conversation_history) >= 2:
                # Look for assistant response with intent info in metadata
                for msg in reversed(conversation_history):
                    if msg.get('role') == 'assistant':
                        # Check if message has metadata with intent
                        metadata = msg.get('metadata', {})
                        if metadata.get('intent'):
                            enriched_context['last_intent'] = metadata['intent']
                            logger.debug("last_intent_extracted", intent=metadata['intent'])
                            break

                # FALLBACK: Infer last_intent from previous user message keywords
                if 'last_intent' not in enriched_context:
                    for msg in reversed(conversation_history):
                        if msg.get('role') == 'user':
                            prev_msg = msg.get('content', '').lower()
                            # Simple heuristic inference
                            if any(kw in prev_msg for kw in ['règlement', 'contrat', 'document', 'facture', 'pv']):
                                enriched_context['last_intent'] = 'search_documents'
                            elif any(kw in prev_msg for kw in ['combien', 'liste', 'qui', 'email de', 'contact']):
                                enriched_context['last_intent'] = 'query_data'
                            elif any(kw in prev_msg for kw in ['loi', 'légal', 'article', 'juridique']):
                                enriched_context['last_intent'] = 'legal'
                            elif any(kw in prev_msg for kw in ['envoie', 'mail', 'contacte', 'préviens']):
                                enriched_context['last_intent'] = 'send_email'
                            if 'last_intent' in enriched_context:
                                logger.debug("last_intent_inferred", intent=enriched_context['last_intent'])
                                break

            # PRIMARY: Use LLM-based classifier for semantic understanding
            classification_result = await self.llm_classifier(
                user_query=user_input,
                conversation_history=conversation_history,
                context=enriched_context,
            )

            # Log detailed classification info
            logger.info("intention_classified_llm",
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
            logger.error("llm_classification_failed", error=str(e), exc_info=True)
            # FALLBACK: Use V5 keyword-based classifier if LLM fails
            logger.info("falling_back_to_v5_classifier")
            try:
                classification_result = await self.intent_classifier.classify(
                    user_input=user_input,
                    context=context,
                    conversation_history=conversation_history,
                )
                return classification_result.intent, classification_result
            except Exception as e2:
                logger.error("v5_fallback_also_failed", error=str(e2))
                return IntentType.GENERAL_QUESTION, None

    def _is_ambiguous(
        self,
        query: str,
        conversation_history: List[Dict[str, str]] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Detect if a query is too ambiguous to process directly.

        Ambiguity types detected:
        1. Short queries (<3 words without context)
        2. Isolated pronouns (il, elle, ça, lui, son) without referent
        3. Incomplete actions (envoie, trouve, cherche without object)

        Args:
            query: User's query
            conversation_history: Previous messages for context

        Returns:
            (is_ambiguous, clarification_question) tuple
        """
        query_lower = query.lower().strip()
        words = query_lower.split()
        has_context = conversation_history and len(conversation_history) > 0

        # ================================================================
        # Type 1: Very short queries without context
        # ================================================================
        if len(words) <= 2 and not has_context:
            # Exception: Common complete questions
            complete_short_queries = [
                "bonjour", "salut", "hello", "merci", "oui", "non",
                "ok", "aide", "help", "quoi de neuf"
            ]
            if query_lower not in complete_short_queries:
                logger.info("ambiguity_detected_short_query", query=query[:50])
                return True, f"Votre question « {query} » est un peu courte. Pouvez-vous préciser ce que vous recherchez ?"

        # ================================================================
        # Type 2: Isolated pronouns without referent (no context)
        # ================================================================
        isolated_pronouns = ["son", "sa", "ses", "lui", "elle", "il", "eux", "leur", "leurs"]
        pronoun_patterns = [
            # "son email", "sa facture", "son numéro"
            r"^(quel|quelle|quels|quelles|où|donne|trouve|cherche)\s+(est\s+)?(son|sa|ses|leur|leurs)\s+",
            # "combien lui", "envoie lui"
            r"(à|pour|chez|avec)\s+(lui|elle|eux)$",
            # Queries starting with just pronoun reference
            r"^(il|elle|ça|cela)\s+(a|est|fait|veut)",
        ]

        if not has_context:
            import re
            for pattern in pronoun_patterns:
                if re.search(pattern, query_lower):
                    logger.info("ambiguity_detected_pronoun", query=query[:50], pattern=pattern)
                    return True, "Je ne suis pas sûr de comprendre à qui ou à quoi vous faites référence. Pouvez-vous préciser le nom de la personne ou du document ?"

        # ================================================================
        # Type 3: Incomplete actions (verbe sans complément)
        # ================================================================
        incomplete_action_patterns = [
            # "envoie" without destination
            (r"^envoie(\s+un)?$", "Envoyer quoi et à qui ?"),
            (r"^envoie\s+(un\s+)?(email|mail|message)$", "À qui souhaitez-vous envoyer cet email ?"),
            # "trouve" without object
            (r"^trouve$", "Que souhaitez-vous que je trouve ?"),
            (r"^cherche$", "Que souhaitez-vous que je cherche ?"),
            # "liste" without object
            (r"^liste$", "Que souhaitez-vous lister ?"),
            # "combien" alone
            (r"^combien\s*\?*$", "Combien de quoi ? Précisez ce que vous souhaitez compter."),
            # "montre" without object
            (r"^montre$", "Que souhaitez-vous voir ?"),
        ]

        import re
        for pattern, clarification in incomplete_action_patterns:
            if re.match(pattern, query_lower):
                logger.info("ambiguity_detected_incomplete_action", query=query[:50], pattern=pattern)
                return True, clarification

        # ================================================================
        # Type 4: Questions with only interrogative words
        # ================================================================
        only_interrogative = [
            "quoi", "qui", "où", "quand", "comment", "pourquoi", "lequel", "laquelle"
        ]
        if query_lower.rstrip("?") in only_interrogative:
            logger.info("ambiguity_detected_interrogative_only", query=query[:50])
            return True, f"Pouvez-vous compléter votre question ? « {query} » seul ne me permet pas de comprendre ce que vous cherchez."

        # Not ambiguous
        return False, None

    async def process(
        self,
        user_input: str,
        db: AsyncSession,
        context: Dict[str, Any] = None,
        conversation_history: List[Dict[str, str]] = None,
        thought_stream: ThoughtStream = None,
        state_manager = None,
        selected_sources: Optional[List[str]] = None,  # ['sql', 'rag', 'web'] or None for auto
        session_id: Optional[str] = None,  # For context_store
        use_world_class_router: bool = False  # Enable Perplexity-style routing
    ) -> AgentResponse:
        """
        Main orchestration method - routes to appropriate agents

        Args:
            user_input: User's message
            db: Database session
            context: Optional context (files, metadata)
            conversation_history: Previous messages
            selected_sources: User-selected sources (['sql', 'rag', 'web']) or None for auto-detection
            use_world_class_router: If True, use Perplexity-style multi-source routing

        Returns:
            AgentResponse with results
        """
        try:
            # ================================================================
            # PRIORITY CHECK: EMAIL CONFIRMATION DETECTION
            # Must check BEFORE template filter to prevent "ok" bypass
            # ================================================================
            if state_manager and state_manager.state.email_draft:
                from .conversation_state import ActionType

                # User has a pending email draft awaiting confirmation
                if state_manager.state.pending_action == ActionType.AWAITING_EMAIL_CONFIRMATION:
                    user_input_lower = user_input.lower().strip()

                    # Confirmation patterns (permissive - context is clear)
                    confirmation_patterns = [
                        "envoyer", "envoie", "envoi",
                        "ok", "oui", "d'accord", "valider", "confirmer",
                        "vas-y", "vas y", "go", "yes", "✅",
                        "parfait", "correct", "c'est bon"
                    ]

                    # Cancellation patterns
                    cancellation_patterns = [
                        "annuler", "annule", "non", "stop", "cancel", "❌"
                    ]

                    # Modification patterns
                    modification_patterns = [
                        "modifier", "modifie", "changer", "change", "corriger", "✏️"
                    ]

                    # Check confirmation
                    if any(pattern in user_input_lower for pattern in confirmation_patterns):
                        logger.info("email_confirmation_detected", user_input=user_input[:50])

                        if thought_stream:
                            await thought_stream.add_thought(
                                ThoughtType.EXECUTING,
                                title="Envoi de l'email",
                                content="Confirmation reçue. Je vais maintenant envoyer l'email via N8N...",
                                agent="orchestrator",
                                progress=0.5
                            )

                        return await self._handle_email_confirmation(
                            state_manager=state_manager,
                            db=db,
                            session_id=session_id,
                            thought_stream=thought_stream
                        )

                    # Check cancellation
                    elif any(pattern in user_input_lower for pattern in cancellation_patterns):
                        logger.info("email_cancellation_detected", user_input=user_input[:50])

                        # Clear draft and pending action
                        state_manager.state.email_draft = None
                        state_manager.state.clear_pending_action()

                        return AgentResponse(
                            success=True,
                            message="✅ Brouillon d'email annulé. Que puis-je faire pour vous ?",
                            data={},
                            agents_used=["orchestrator"],
                            sources_used=[],
                            confidence=1.0,
                            suggestions=[],
                            warnings=[]
                        )

                    # Check modification request
                    elif any(pattern in user_input_lower for pattern in modification_patterns):
                        logger.info("email_modification_detected", user_input=user_input[:50])

                        return AgentResponse(
                            success=True,
                            message="✏️ Pour modifier l'email, veuillez préciser :\n- \"Modifier l'objet\" pour changer le sujet\n- \"Modifier le message\" pour changer le contenu\n- Ou reformulez votre demande complète",
                            data={"email_draft": state_manager.state.email_draft},
                            agents_used=["orchestrator"],
                            sources_used=[],
                            confidence=1.0,
                            suggestions=[
                                "Modifier l'objet",
                                "Modifier le message",
                                "Annuler"
                            ],
                            warnings=[]
                        )

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

                # Emit thought even for bypass so CoT shows something
                if thought_stream:
                    await thought_stream.add_thought(
                        ThoughtType.COMPLETED,
                        title="Réponse rapide",
                        content=f"Catégorie détectée : {template_result.get('category', 'greeting')}",
                        agent="template_filter",
                        progress=1.0
                    )

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

            ui_bypass_result = self.ui_context_bypass.check(context, user_query=user_input)

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
            # AMBIGUITY DETECTION (P1 Improvement)
            # Check if query is too vague before processing
            # ================================================================
            is_ambiguous, clarification_question = self._is_ambiguous(
                user_input,
                conversation_history
            )

            if is_ambiguous and clarification_question:
                logger.info("ambiguity_detected_returning_clarification",
                           query=user_input[:50],
                           clarification=clarification_question[:50])

                if thought_stream:
                    await thought_stream.add_thought(
                        ThoughtType.ANALYZING,
                        title="Demande de précision",
                        content="La requête est ambiguë, je demande une clarification.",
                        agent="orchestrator",
                        progress=0.1
                    )

                return AgentResponse(
                    success=True,
                    message=clarification_question,
                    data={
                        "needs_clarification": True,
                        "ambiguity_type": "detected",
                        "original_query": user_input
                    },
                    agents_used=["orchestrator"],
                    sources_used=[],
                    confidence=0.3,
                    suggestions=[
                        "Précisez le nom de la copropriété",
                        "Ajoutez plus de détails",
                        "Reformulez votre question"
                    ],
                    warnings=[]
                )

            # ================================================================
            # WORLD-CLASS ROUTER MODE (Phase 4 - Perplexity-style)
            # When enabled, bypasses traditional intent classification
            # ================================================================
            if use_world_class_router and selected_sources is None:
                # No user-selected sources AND world_class_router enabled
                # → Use intelligent multi-source routing
                logger.info("world_class_router_mode_enabled", query=user_input[:50])

                return await self._execute_with_world_class_router(
                    user_input=user_input,
                    db=db,
                    thought_stream=thought_stream,
                    state_manager=state_manager,
                    context=context,
                    conversation_history=conversation_history
                )

            # ================================================================
            # CONTINUE NORMAL FLOW (with or without bypass)
            # ================================================================

            # ================================================================
            # UNIFIED CONTEXT SYNCHRONIZATION (Phase 3 - World-Class SMA)
            # Single Source of Truth for all context sources
            # ================================================================
            unified_ctx = None
            if session_id:
                unified_ctx = get_unified_context_manager(session_id)

                # Sync from StateManager (if available)
                if state_manager:
                    unified_ctx.sync_from_state_manager(state_manager)

                # Sync from ContextStore
                unified_ctx.sync_from_context_store(context_store, session_id)

                # Sync from EntityGraph (if available)
                if state_manager:
                    entity_graph = state_manager.get_entity_graph()
                    if entity_graph:
                        unified_ctx.sync_from_entity_graph(entity_graph)

                # Update conversation summary
                if conversation_history:
                    unified_ctx.update_conversation_summary(
                        summary=f"Conversation de {len(conversation_history)} messages",
                        message_count=len(conversation_history)
                    )

                # Add unified context to the context dict for agents
                if context is None:
                    context = {}
                context["unified_context"] = unified_ctx.get_llm_context_string()
                context["unified_context_data"] = unified_ctx.to_dict()

                logger.info("unified_context_synced",
                           session_id=session_id,
                           context_summary=unified_ctx.get_llm_context_string()[:100])

            # ================================================================
            # FACT EXTRACTION - Extract structured facts from user input
            # ================================================================
            # Extract and store budgets, dates, contacts for better recall
            if session_id:
                await self._extract_and_store_facts(user_input, session_id)

            # ================================================================
            # MEMORY RECALL LAYER - Check conversation history first
            # ================================================================
            # If user is asking for recall ("c'était combien déjà?"), answer from
            # conversation history instead of calling SQL/RAG agents
            if conversation_history and len(conversation_history) > 0:
                # Try context_store facts first (most reliable)
                if session_id:
                    fact_result = await self._recall_from_context_store(user_input, session_id)
                    if fact_result:
                        logger.info("context_store_recall_success", query=user_input[:50])

                        # Emit thought for context recall
                        if thought_stream:
                            await thought_stream.add_thought(
                                ThoughtType.COMPLETED,
                                title="Rappel depuis le contexte",
                                content="Information retrouvée dans le contexte de la conversation.",
                                agent="context_store",
                                progress=1.0
                            )

                        return AgentResponse(
                            success=True,
                            message=fact_result,
                            data={},
                            agents_used=["context_store"],
                            sources_used=[DataSource.CONVERSATION],
                            confidence=0.98,
                            suggestions=[],
                            warnings=[]
                        )

                # Fallback to conversation history analysis
                memory_result = await self._check_conversation_memory(
                    user_input,
                    conversation_history
                )

                if memory_result:
                    logger.info("memory_recall_success",
                               query=user_input[:50],
                               latency="<2s")

                    if thought_stream:
                        await thought_stream.add_thought(
                            ThoughtType.COMPLETED,
                            title="Rappel depuis la mémoire",
                            content=f"J'ai retrouvé cette information dans notre conversation précédente.",
                            agent="memory_recall",
                            progress=1.0
                        )

                    return AgentResponse(
                        success=True,
                        message=memory_result,
                        data={},
                        agents_used=["memory_recall"],
                        sources_used=[DataSource.CONVERSATION],
                        confidence=0.95,
                        suggestions=[],
                        warnings=[]
                    )

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

            # 1.5 NOUVEAU: Reference Resolution (pronoms et références)
            # Résout "elle", "lui", "ce prestataire", etc.
            try:
                from app.services.agents.reference_resolver import get_reference_resolver

                reference_resolver = get_reference_resolver()

                # Construire les données du context_store pour la résolution
                context_store_data = {}
                if session_id:
                    # Récupérer les dernières entités mentionnées
                    stored_context = context_store.get_context(session_id)
                    if stored_context:
                        context_store_data = stored_context

                # Résoudre les références
                resolution_result = await reference_resolver.resolve(
                    query=user_input,
                    conversation_history=conversation_history,
                    context_store_data=context_store_data,
                    session_id=session_id
                )

                # Si des références ont été résolues, utiliser la requête résolue
                if resolution_result.changes_made:
                    logger.info("references_resolved",
                               original=user_input[:50],
                               resolved=resolution_result.resolved_query[:50],
                               changes=resolution_result.changes_made)

                    user_input = resolution_result.resolved_query

                    # Stocker les entités résolues dans le contexte
                    if not context:
                        context = {}
                    context["resolved_references"] = {
                        ref: {"name": entity.name, "type": entity.entity_type.value}
                        for ref, entity in resolution_result.resolved_entities.items()
                    }

                    if thought_stream:
                        changes_str = ", ".join(resolution_result.changes_made)
                        await thought_stream.add_thought(
                            ThoughtType.PROCESSING,
                            title="Résolution des références",
                            content=f"J'ai identifié et résolu les références dans votre demande : {changes_str}",
                            agent="reference_resolver",
                            progress=0.12
                        )

            except Exception as e:
                logger.warning("reference_resolution_failed", error=str(e))
                # Continue with original query if resolution fails

            # 1.6 Query Enrichment (résolution d'entités supplémentaire)
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
                    elif source == 'legal':
                        intent = IntentType.LEGAL
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

            # ================================================================
            # CLARIFICATION HANDLING - Ask user when confidence is low
            # ================================================================
            if classification_result and classification_result.needs_clarification:
                logger.info("clarification_needed",
                           intent=intent.value,
                           confidence=classification_result.confidence,
                           question=classification_result.clarification_question)

                if thought_stream:
                    await thought_stream.add_thought(
                        ThoughtType.ANALYZING,
                        title="Clarification nécessaire",
                        content=f"Je ne suis pas sûr de bien comprendre votre demande (confiance: {classification_result.confidence:.0%}). Je vais vous demander de préciser.",
                        agent="intent_classifier",
                        progress=0.20
                    )

                # Build clarification response with options for UI
                options_text = "\n".join([
                    f"• **{opt['label']}** : {opt['description']}"
                    for opt in classification_result.clarification_options
                ])

                return AgentResponse(
                    success=True,
                    message=f"{classification_result.clarification_question}\n\n{options_text}",
                    data={
                        "needs_clarification": True,
                        "clarification_options": classification_result.clarification_options,
                        "original_intent": intent.value,
                        "confidence": classification_result.confidence
                    },
                    agents_used=["intent_classifier"],
                    sources_used=[],
                    confidence=classification_result.confidence,
                    suggestions=[opt['label'] for opt in classification_result.clarification_options],
                    warnings=[]
                )

            if thought_stream:
                # Map intent to French label
                intent_labels_fr = {
                    "QUERY_DATA": "Requête base de données",
                    "SEARCH_DOCUMENTS": "Recherche documentaire",
                    "WEB_SEARCH": "Recherche web",
                    "SEND_EMAIL": "Envoi d'email",
                    "LEGAL": "Analyse juridique",
                    "GENERAL_QUESTION": "Question générale",
                    "GENERATE_DIGEST": "Génération de digest",
                    "TRIGGER_WORKFLOW": "Déclenchement workflow"
                }
                intent_label = intent_labels_fr.get(intent.value, intent.value)

                # Build detailed confidence info for CoT
                confidence = classification_result.confidence if classification_result else 0.9
                confidence_level = "haute" if confidence >= 0.85 else "moyenne" if confidence >= 0.70 else "faible"
                confidence_emoji = "🟢" if confidence >= 0.85 else "🟡" if confidence >= 0.70 else "🔴"

                # Extract reasoning from classification (LLM provides this)
                reasoning = ""
                if classification_result and classification_result.reasoning:
                    # Clean up reasoning for display
                    reasoning = classification_result.reasoning.replace("[LLM] ", "").replace("[FALLBACK] ", "")

                # Build sources info
                sources_info = ""
                if classification_result and classification_result.suggested_sources:
                    sources_list = [s.value for s in classification_result.suggested_sources]
                    sources_info = f" | Sources: {', '.join(sources_list)}"

                # Determine if using LLM or fallback
                classifier_type = "LLM Mistral" if classification_result and "[LLM]" in (classification_result.reasoning or "") else "Fallback keywords"

                await thought_stream.add_thought(
                    ThoughtType.INTENT_DETECTED,
                    title=f"{confidence_emoji} {intent_label} ({confidence:.0%})",
                    content=f"**Confiance {confidence_level}** ({classifier_type})\n\n{reasoning}{sources_info}" if reasoning else f"Classification par {classifier_type} avec confiance {confidence_level}",
                    agent="llm_classifier",
                    data={
                        "intent": intent.value,
                        "confidence": confidence,
                        "confidence_level": confidence_level,
                        "reasoning": reasoning,
                        "classifier_type": classifier_type,
                        "suggested_sources": [s.value for s in classification_result.suggested_sources] if classification_result and classification_result.suggested_sources else [],
                        "domain": classification_result.domain.value if classification_result else "general"
                    },
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
                    IntentType.GENERATE_DIGEST: "Digest Agent (classification et résumé des emails)",
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
                return await self._handle_query_data(user_input, db, state_manager, thought_stream, session_id)

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

            elif intent == IntentType.GENERATE_DIGEST:
                if thought_stream:
                    await thought_stream.add_thought(
                        ThoughtType.DIGEST_FETCHING,
                        title="Récupération des emails",
                        content="Interrogation de la base de données...",
                        agent="digest_agent",
                        progress=0.3
                    )
                return await self._handle_generate_digest(user_input, db, thought_stream)

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

    # ================================================================
    # MEMORY RECALL LAYER - Solution 1 from MEMORY_ENHANCEMENT_PLAN.md
    # ================================================================

    async def _check_conversation_memory(
        self,
        user_input: str,
        conversation_history: List[Dict[str, str]]
    ) -> Optional[str]:
        """
        Check if question can be answered from conversation history

        This pre-checks memory BEFORE routing to agents, avoiding unnecessary
        SQL/RAG calls for simple recall questions like "C'était combien déjà?"

        Returns:
            str: Answer from memory, or None if not found
        """
        import re

        # 1. Detect recall patterns (French-optimized)
        recall_patterns = [
            r"c'est quoi (déjà|encore) (le|la|l'|les)",
            r"c'était (combien|quoi|quand|où|qui|comment)",
            r"rappel[le]?[-\s]moi",
            r"quel était le",
            r"quelle était la",
            r"quels étaient les",
            r"tu (m')?as dit",
            r"on avait dit",
            r"tu disais",
            r"je t'ai donné",
            r"je t'avais dit",
            r"dans la conversation",
            r"plus tôt",
            r"tantôt",
            r"tout à l'heure",
        ]

        is_recall_question = any(
            re.search(pattern, user_input.lower(), re.IGNORECASE)
            for pattern in recall_patterns
        )

        if not is_recall_question:
            return None

        # 2. Extract what user is asking about
        keywords = self._extract_recall_keywords(user_input)

        if not keywords:
            logger.info("memory_recall_no_keywords", query=user_input[:50])
            return None

        # 3. Search in conversation history (reverse order, most recent first)
        relevant_messages = []
        for msg in reversed(conversation_history[-20:]):  # Last 20 messages
            if msg.get("role") in ["assistant", "user"]:
                content = msg.get("content", "").lower()
                # Check if message contains keywords
                if any(kw in content for kw in keywords):
                    relevant_messages.append({
                        "role": msg.get("role"),
                        "content": msg.get("content", "")
                    })

        if not relevant_messages:
            logger.info("memory_recall_no_matches",
                       keywords=keywords[:3],
                       history_size=len(conversation_history))
            return None

        # 4. Use LLM to extract specific answer
        # Concatenate relevant messages (top 5 most relevant)
        context_parts = []
        for msg in relevant_messages[:5]:
            role_label = "Utilisateur" if msg["role"] == "user" else "Assistant"
            context_parts.append(f"{role_label}: {msg['content']}")

        context_str = "\n\n".join(context_parts)

        recall_prompt = f"""Tu es un assistant mémoire pour DisruptIQ.

Question de l'utilisateur: "{user_input}"

Contexte de conversation précédente:
{context_str}

Réponds UNIQUEMENT à la question en utilisant les informations ci-dessus.
Si l'information n'est pas dans le contexte, réponds "Je n'ai pas cette information en mémoire."

Réponse courte et directe (2-3 phrases maximum):"""

        try:
            answer = await self.llm_service.generate_response(
                prompt=recall_prompt,
                temperature=0.2,
                max_tokens=200,
                conversation_history=conversation_history
            )

            # Validate answer is not "je ne sais pas"
            no_answer_phrases = [
                "je n'ai pas",
                "je ne sais pas",
                "information manquante",
                "pas en mémoire",
                "pas trouvé",
                "je ne trouve pas"
            ]

            answer_lower = answer.lower()
            if any(phrase in answer_lower for phrase in no_answer_phrases):
                logger.info("memory_recall_llm_uncertain", answer=answer[:50])
                return None

            logger.info("memory_recall_extracted",
                       keywords=keywords[:3],
                       answer_length=len(answer))

            return answer.strip()

        except Exception as e:
            logger.error("memory_recall_failed", error=str(e))
            return None

    def _extract_recall_keywords(self, user_input: str) -> List[str]:
        """
        Extract keywords from recall question

        Removes stopwords and extracts meaningful terms + numbers
        """
        # Remove question words and common French stopwords
        stopwords = {
            "c'est", "c'était", "quoi", "déjà", "encore", "le", "la", "l'", "les",
            "combien", "rappelle", "moi", "qui", "quand", "où", "comment", "quel",
            "quelle", "quels", "était", "étaient", "tu", "m'as", "dit", "on", "avait",
            "dans", "plus", "tôt", "tout", "heure", "je", "t'ai", "donné", "t'avais",
            "conversation", "tantôt", "pour", "avec", "sans", "sur", "sous", "par"
        }

        # Split and clean
        words = user_input.lower().split()
        keywords = [
            w.strip("?!.,;:") for w in words
            if len(w) > 3 and w.lower() not in stopwords
        ]

        # Also extract potential numbers (amounts, dates)
        import re
        numbers = re.findall(r'\d+', user_input)
        keywords.extend(numbers)

        return keywords

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

    async def _handle_query_data(self, user_input: str, db: AsyncSession, state_manager=None, thought_stream=None, session_id: Optional[str] = None) -> AgentResponse:
        """Handle SQL data queries and store results in context"""
        # Import here to avoid circular imports
        from .sql_agent import SQLAgent
        import re

        # NOUVEAU: Extract and store copropriete names from user query for reference resolution
        if session_id:
            # Pattern to match copropriete names - capture full name including prefix
            copro_patterns = [
                # Capture full name with prefix: "Résidence Arc-en-Ciel", "Immeuble Haussmann"
                r"((?:résidence|copropriété|copropriete|immeuble|le clos|les)\s+(?:de\s+)?[A-ZÀ-Üa-zà-ü][a-zà-ü\-]+(?:[\s\-]+[A-ZÀ-Üa-zà-ü][a-zà-ü\-]+)*)",
                # Known copropriété names
                r"(Résidence Arc-en-Ciel|Arc-en-Ciel|Jardins de Provence|Parc des Étoiles|Les Mimosas|Le Clos des Oliviers|Clos des Oliviers|Immeuble Haussmann Saint-Germain|Haussmann Saint-Germain)",
            ]
            for pattern in copro_patterns:
                matches = re.findall(pattern, user_input, re.IGNORECASE)
                for match in matches:
                    copro_name = match.strip() if isinstance(match, str) else match[0].strip()
                    if copro_name and len(copro_name) > 2:
                        context_store.set_entity(
                            session_id=session_id,
                            entity_type="copropriete",
                            entity_data={"name": copro_name}
                        )
                        logger.info("copropriete_extracted_from_query",
                                   session_id=session_id,
                                   copro_name=copro_name)

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
                ThoughtType.SQL_GENERATING,
                title="Génération de la requête SQL",
                content=f"Analyse de la demande et génération d'une requête SQL optimisée...",
                agent="sql_agent",
                progress=0.5
            )

        sql_agent = SQLAgent()
        result = await sql_agent.process(enriched_input, db, thought_stream=thought_stream)

        if thought_stream:
            if result.get("success"):
                row_count = len(result.get("data", {}).get("results", []))
                tables_used = result.get("data", {}).get("tables", [])
                await thought_stream.add_thought(
                    ThoughtType.SQL_RESULTS,
                    title=f"{row_count} résultat(s) trouvé(s)",
                    content=f"Requête exécutée avec succès sur la base de données.",
                    agent="sql_agent",
                    data={
                        "rowCount": row_count,
                        "tables": tables_used
                    },
                    progress=0.8
                )
            else:
                await thought_stream.add_thought(
                    ThoughtType.ERROR,
                    title="Erreur SQL",
                    content=f"Erreur lors de l'exécution : {result.get('message', 'Erreur inconnue')}",
                    agent="sql_agent",
                    progress=0.8
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

            # NOUVEAU: Store SQL results in context_store for email agent
            if session_id:
                context_store.set_sql_results(session_id, {
                    "results": response_data.get("results", []),
                    "query": response_data.get("sql_query", ""),
                    "tables": response_data.get("tables", [])
                })
                logger.info("sql_results_stored_in_context_store",
                           session_id=session_id,
                           result_count=len(response_data.get("results", [])))

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

                        # NOUVEAU: Store in context_store for reference resolution
                        if session_id:
                            for res in results:
                                copro_name = res.get("nom") or res.get("copropriete_nom", "")
                                if copro_name:
                                    context_store.set_entity(
                                        session_id=session_id,
                                        entity_type="copropriete",
                                        entity_data={
                                            "name": copro_name,
                                            "id": res.get("id"),
                                            "adresse": res.get("adresse"),
                                            "ville": res.get("ville"),
                                            "nombre_lots": res.get("nombre_lots")
                                        }
                                    )
                            logger.info("context_store_coproprietes_stored", session_id=session_id, count=len(results))
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
        Also handles conversation synthesis requests
        """
        try:
            logger.info("handling_search_documents", query=user_input[:50])

            # Check if this is a conversation synthesis request
            synthesis_keywords = ["synthèse", "synthese", "résumé complet", "résume notre conversation",
                                  "récapitule", "récapitulatif", "ce qui a été fait", "les faits",
                                  "résume le dossier", "résumé du dossier", "fais une synthèse", "fais un résumé",
                                  "dossier plomberie", "synthèse dossier", "récap dossier", "recap dossier",
                                  "synthese complete", "synthèse complète"]
            is_synthesis_request = any(kw in user_input.lower() for kw in synthesis_keywords)

            # Generate synthesis if request detected AND we have conversation history (min 1 message)
            if is_synthesis_request and conversation_history and len(conversation_history) > 0:
                # Generate synthesis from conversation history, not RAG
                logger.info("generating_conversation_synthesis", history_length=len(conversation_history))

                if thought_stream:
                    await thought_stream.add_thought(
                        ThoughtType.PROCESSING,
                        title="Génération de la synthèse",
                        content="Je vais analyser l'historique de notre conversation pour générer une synthèse complète.",
                        agent="synthesis_agent",
                        progress=0.5
                    )

                synthesis = await self._generate_conversation_synthesis(user_input, conversation_history)

                if thought_stream:
                    await thought_stream.add_thought(
                        ThoughtType.COMPLETED,
                        title="Synthèse générée",
                        content="J'ai compilé les informations clés de notre échange.",
                        agent="synthesis_agent",
                        progress=1.0
                    )

                return AgentResponse(
                    success=True,
                    message=synthesis,
                    agents_used=["synthesis_agent"],
                    confidence=0.85,
                    data={"type": "conversation_synthesis"}
                )

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
        import re

        try:
            # CRITICAL: Early detection for PRESTATAIRE emails
            # If user is emailing a prestataire/vendor, bypass intelligent flow
            # and let EmailAgent handle it directly (it knows how to find prestataire)
            user_input_lower = user_input.lower()
            prestataire_keywords = ["prestataire", "plomberie", "électricité", "plombier",
                                    "électricien", "entreprise", "fournisseur", "artisan"]
            copro_keywords = ["copropriétaires", "coproprietaires", "résidents", "habitants"]

            is_for_prestataire = any(kw in user_input_lower for kw in prestataire_keywords)
            is_for_copros = any(kw in user_input_lower for kw in copro_keywords)

            # If targeting prestataire AND NOT copros, go directly to EmailAgent
            if is_for_prestataire and not is_for_copros:
                logger.info("email_to_prestataire_detected_bypassing_intelligent_flow")
                if thought_stream:
                    await thought_stream.add_thought(
                        ThoughtType.ANALYZING,
                        title="Email au prestataire détecté",
                        content="Je recherche le prestataire dans la base de données...",
                        agent="orchestrator",
                        progress=0.2
                    )
                # Go directly to EmailAgent which has proper prestataire detection
                return await self._handle_send_email(
                    user_input, db, context, conversation_history, session_id,
                    state_manager=state_manager, thought_stream=thought_stream
                )
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

            # NOUVEAU: Check context_store for SQL results if no recipients from query_data
            if not recipients_found and session_id:
                sql_results = context_store.get_sql_results(session_id)
                if sql_results and sql_results.get("results"):
                    for row in sql_results["results"]:
                        if isinstance(row, dict) and "email" in row and row["email"]:
                            recipients_found.append(str(row["email"]))
                    if recipients_found:
                        logger.info("recipients_from_context_store_intelligent", session_id=session_id, count=len(recipients_found))
                        if thought_stream:
                            await thought_stream.add_thought(
                                ThoughtType.ANALYZING,
                                title="Destinataires récupérés",
                                content=f"✓ {len(recipients_found)} destinataire(s) récupéré(s) du contexte de conversation",
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
            # CRITICAL: Pass state_manager and thought_stream for draft persistence
            return await self._handle_send_email(
                user_input, db, context, conversation_history, session_id,
                state_manager=state_manager, thought_stream=thought_stream
            )

        except Exception as e:
            logger.error("intelligent_email_handling_failed", error=str(e), exc_info=True)
            # Fallback to standard email handling (with state persistence)
            return await self._handle_send_email(
                user_input, db, context, conversation_history, session_id,
                state_manager=state_manager, thought_stream=thought_stream
            )

    async def _handle_send_email(
        self,
        user_input: str,
        db: AsyncSession,
        context: Dict[str, Any] = None,
        conversation_history: List[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        state_manager = None,
        thought_stream = None
    ) -> AgentResponse:
        """
        Handle email generation with human-in-the-loop validation

        Shows draft first, then asks for validation before sending
        Uses emails from previous SQL query if available

        CRITICAL: Stores draft in state_manager for confirmation workflow
        """
        from .email_agent import EmailAgent

        email_agent = EmailAgent()
        agents_used = []

        # Extract emails from context if available (from previous SQL query)
        recipients_from_context = []
        if context and "emails_available" in context:
            recipients_from_context = context["emails_available"]
            logger.info("recipients_found_in_context", count=len(recipients_from_context))

        # NOUVEAU: Check context_store for SQL results if no recipients in direct context
        if not recipients_from_context and session_id:
            sql_results = context_store.get_sql_results(session_id)
            if sql_results and sql_results.get("results"):
                # Extract emails from SQL results
                for row in sql_results["results"]:
                    if isinstance(row, dict) and "email" in row and row["email"]:
                        recipients_from_context.append({
                            "name": f"{row.get('prenom', '')} {row.get('nom', '')}".strip(),
                            "email": row["email"],
                            "id": row.get("id")
                        })
                if recipients_from_context:
                    logger.info("recipients_from_context_store", session_id=session_id, count=len(recipients_from_context))
                    # Add to context so email_agent can use them
                    if not context:
                        context = {}
                    context["emails_available"] = recipients_from_context

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
        if thought_stream:
            await thought_stream.add_thought(
                ThoughtType.EMAIL_DRAFTING,
                title="Rédaction du brouillon",
                content="Génération de l'email en cours...",
                agent="email_agent",
                progress=0.5
            )

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
            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.ERROR,
                    title="Échec de la rédaction",
                    content=f"Erreur : {email_draft.get('message', 'Erreur inconnue')[:100]}",
                    agent="email_agent",
                    progress=0.6
                )
            return AgentResponse(
                success=False,
                message=email_draft["message"],
                agents_used=agents_used
            )

        # Extract draft details
        draft_data = email_draft.get("data", {})

        if thought_stream:
            recipients_count = len(draft_data.get("recipients", []))
            await thought_stream.add_thought(
                ThoughtType.COMPLETED,
                title=f"Brouillon prêt ({recipients_count} dest.)",
                content="En attente de confirmation pour envoi",
                agent="email_agent",
                data={
                    "recipients_count": recipients_count,
                    "subject": draft_data.get("subject", "")[:50]
                },
                progress=0.7
            )
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

        # ================================================================
        # CRITICAL: Store draft in state_manager for confirmation workflow
        # Without this, the "ok"/"envoyer" confirmation won't find the draft
        # ================================================================
        if state_manager:
            from .conversation_state import ActionType
            # Store the complete draft data
            state_manager.state.email_draft = draft_data
            state_manager.state.set_pending_action(
                ActionType.AWAITING_EMAIL_CONFIRMATION,
                {"draft": draft_data, "session_id": session_id}
            )
            logger.info("email_draft_stored_in_state",
                       has_recipients=bool(draft_data.get("recipients")),
                       subject=subject[:50] if subject else "N/A")

            # Emit thought about awaiting confirmation
            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.WAITING,
                    title="En attente de confirmation",
                    content=f"Brouillon prêt avec {len(recipient_display)} destinataire(s). En attente de votre validation.",
                    agent="orchestrator",
                    progress=0.9
                )
        else:
            logger.warning("email_draft_not_stored_no_state_manager",
                          note="Draft generated but state_manager not available for persistence")

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

    async def _handle_generate_digest(self, user_input: str, db: AsyncSession, thought_stream=None) -> AgentResponse:
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

                # Emit thought for classification
                if thought_stream:
                    total_emails = len(urgent_emails) + len(important_emails) + len(routine_emails)
                    await thought_stream.add_thought(
                        ThoughtType.DIGEST_CLASSIFYING,
                        title=f"Classification de {total_emails} email(s)",
                        content=f"🔴 {len(urgent_emails)} urgent(s), 🟡 {len(important_emails)} important(s), 🟢 {len(routine_emails)} routine",
                        agent="digest_agent",
                        data={
                            "urgent_count": len(urgent_emails),
                            "important_count": len(important_emails),
                            "routine_count": len(routine_emails)
                        },
                        progress=0.7
                    )

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

        V3 Architecture - Simplified Emergency Handling:
        - First check if this is an emergency using EmergencyChecklistAgent
        - If emergency: generate checklist template (no N8N, no auto-emails)
        - If not emergency: use WorkflowAgent V2 for other workflows

        The user receives a checklist and decides what actions to take.
        """
        try:
            # ===== NEW V3: Check for emergency first =====
            from .emergency_checklist_agent import get_emergency_checklist_agent

            emergency_agent = get_emergency_checklist_agent()

            # Check if this looks like an emergency
            if emergency_agent.is_emergency_query(user_input):
                logger.info("emergency_detected", query=user_input[:100])

                # Add thought for CoT
                if thought_stream:
                    await thought_stream.add_thought(
                        ThoughtType.ANALYZING,
                        title="Situation d'urgence détectée",
                        content="Génération de la checklist de gestion...",
                        agent="emergency_checklist_agent",
                        progress=0.3
                    )

                # Build context from session
                checklist_context = {}
                if context:
                    checklist_context = {
                        "copropriete": context.get("copropriete_name"),
                        "adresse": context.get("adresse"),
                    }

                # Generate checklist (template or LLM fallback)
                result = await emergency_agent.generate_checklist(
                    user_input=user_input,
                    context=checklist_context
                )

                # Add completion thought
                if thought_stream:
                    await thought_stream.add_thought(
                        ThoughtType.COMPLETED,
                        title=f"Checklist: {result.template_name}",
                        content=f"Niveau d'urgence: {result.urgency_level}",
                        agent="emergency_checklist_agent",
                        progress=1.0
                    )

                # Return the checklist as the response
                return AgentResponse(
                    success=result.success,
                    message=result.checklist_markdown,
                    data={
                        "type": "emergency_checklist",
                        "template_id": result.template_id,
                        "template_name": result.template_name,
                        "urgency_level": result.urgency_level,
                        "category": result.category,
                        "is_llm_generated": result.is_llm_generated
                    },
                    agents_used=["emergency_checklist_agent"],
                    confidence=0.95 if not result.is_llm_generated else 0.80,
                    suggestions=[
                        "Générer un email pour les parties concernées",
                        "Rechercher un professionnel à contacter",
                        "Consulter les documents de la copropriété"
                    ]
                )

            # ===== Not an emergency - use standard workflow handling =====
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

                # ===== NEW: Store structured facts for memory recall =====
                context_data = result.get("context_data", {})

                # Store budget as fact
                if context_data.get("budget"):
                    context_store.add_fact(session_id, "budget", {
                        "amount": context_data["budget"],
                        "for": context_data.get("description", "workflow"),
                        "workflow_type": result.get("workflow_type")
                    })

                # Store date as fact
                if context_data.get("date"):
                    context_store.add_fact(session_id, "date", {
                        "event": context_data.get("event_type", result.get("workflow_type")),
                        "date": context_data["date"],
                        "workflow_type": result.get("workflow_type")
                    })

                # Store description/context as fact
                if context_data.get("description"):
                    context_store.add_fact(session_id, "workflow_context", {
                        "description": context_data["description"],
                        "workflow_type": result.get("workflow_type"),
                        "subtype": result.get("subtype")
                    })

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

            # Thought 1: Starting search
            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.WEB_SEARCHING,
                    title="Recherche sur internet",
                    content="Interrogation de DuckDuckGo en cours...",
                    agent="web_agent",
                    progress=0.4
                )

            # Perform search with conversation history for contextual understanding
            search_results = await web_agent.search(
                query=user_input,
                num_results=5,
                search_depth="basic",
                region="fr-fr",
                conversation_history=conversation_history,
                thought_stream=thought_stream  # Pass thought_stream for CoT
            )

            # Thought 2: Results found with structured data
            if thought_stream:
                if search_results.results:
                    # Extract domains for display
                    domains = []
                    for r in search_results.results[:5]:
                        if r.url:
                            try:
                                domain = r.url.split("/")[2]
                                domains.append(domain)
                            except:
                                pass
                    unique_domains = list(set(domains))[:5]

                    # Calculate average score
                    top_scores = [r.relevance_score for r in search_results.results[:3]]
                    avg_score = sum(top_scores) / len(top_scores) if top_scores else 0

                    await thought_stream.add_thought(
                        ThoughtType.WEB_RESULTS,
                        title=f"{len(search_results.results)} résultat(s) trouvé(s)",
                        content=f"Sources : {', '.join(unique_domains[:3])}",
                        agent="web_agent",
                        data={
                            "domains": unique_domains,
                            "confidence": avg_score
                        },
                        progress=0.7
                    )
                else:
                    await thought_stream.add_thought(
                        ThoughtType.WEB_RESULTS,
                        title="Aucun résultat pertinent trouvé",
                        content="La recherche n'a pas retourné de résultats",
                        agent="web_agent",
                        data={
                            "domains": [],
                            "confidence": 0
                        },
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
                    ThoughtType.LEGAL_ANALYZING,
                    title="Analyse juridique",
                    content="Traitement de votre demande juridique...",
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
                sources_count = len(result.get("result", {}).get("sources", []))

                await thought_stream.add_thought(
                    ThoughtType.LEGAL_RESULTS,
                    title=f"{action_label} terminée",
                    content=f"{sources_count} source(s) juridique(s)" if sources_count else "",
                    agent="legal_agent",
                    data={
                        "action": result.get("action", "unknown"),
                        "sources_count": sources_count
                    },
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

    async def _generate_conversation_synthesis(
        self,
        user_input: str,
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """
        Generate a synthesis of the conversation history.

        This is used when the user asks for a summary/recap of the conversation
        rather than searching documents.
        """
        try:
            # Handle empty or missing conversation history
            if not conversation_history or len(conversation_history) == 0:
                return """## 📋 Synthèse du dossier

Je n'ai pas encore suffisamment d'informations dans notre conversation pour générer une synthèse complète.

Pour obtenir une synthèse pertinente, veuillez d'abord:
1. Rechercher les informations nécessaires (factures, contrats, etc.)
2. Consulter les données des copropriétaires concernés
3. Effectuer les actions requises (emails, devis, etc.)

Ensuite, redemandez-moi une synthèse et je compilerai toutes les informations de notre échange."""

            # Format conversation history (increased limit for synthesis)
            formatted_history = ""
            for i, msg in enumerate(conversation_history):
                role = "Utilisateur" if msg.get("role") == "user" else "Assistant"
                content = msg.get("content", "")[:800]  # Increased limit for more context
                formatted_history += f"\n{i+1}. [{role}]: {content}\n"

            prompt = f"""Tu es un expert en synthèse pour un syndic de copropriété.

DEMANDE DE L'UTILISATEUR:
{user_input}

HISTORIQUE DE LA CONVERSATION:
{formatted_history}

GÉNÈRE UNE SYNTHÈSE STRUCTURÉE avec:

## 📋 Résumé de la conversation

### 1. Les faits établis
- (liste des informations factuelles découvertes: montants, dates, noms, etc.)

### 2. Les actions effectuées
- (liste des actions réalisées: emails générés/envoyés, recherches effectuées, etc.)

### 3. Le cadre juridique (si applicable)
- (articles de loi mentionnés, obligations légales, etc.)

### 4. Prochaines étapes recommandées
- (actions à entreprendre)

IMPORTANT:
- Sois précis avec les chiffres et dates mentionnés dans la conversation
- Si des montants ont été trouvés (ex: 587,40€), inclus-les
- Si des articles de loi ont été cités (ex: article 18), mentionne-les
- Si des emails ont été générés/envoyés, indique-le

SYNTHÈSE:"""

            response = await self.llm_service.generate_response(
                prompt=prompt,
                max_tokens=1000,
                temperature=0.3
            )

            logger.info("conversation_synthesis_generated",
                       history_length=len(conversation_history),
                       response_length=len(response))

            return response

        except Exception as e:
            logger.error("conversation_synthesis_failed", error=str(e))
            return "Je n'ai pas pu générer la synthèse de notre conversation. Veuillez réessayer."

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
                temperature=0.7,
                conversation_history=conversation_history
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
            IntentType.GENERATE_DIGEST: self._handle_generate_digest,  # Email digest generation
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

    async def _execute_with_world_class_router(
        self,
        user_input: str,
        db,
        thought_stream=None,
        state_manager=None,
        context: Dict[str, Any] = None,
        conversation_history: List[Dict] = None
    ) -> AgentResponse:
        """
        Execute query using World-Class Router (Perplexity-style)

        This method:
        1. Pre-filters query to determine sources (~1ms)
        2. Retrieves from all relevant sources in parallel (~200-400ms)
        3. Reranks results with Cross-Encoder (~100ms)
        4. Synthesizes response with Mistral

        Total latency: ~500ms for routing + retrieval
        """
        from app.services.agents.world_class_router import SourceType

        try:
            logger.info("world_class_router_execution_started", query=user_input[:50])

            # Thought: Starting intelligent routing
            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.ANALYZING,
                    title="Routage intelligent",
                    content="J'analyse votre demande pour déterminer automatiquement les meilleures sources d'information...",
                    agent="world_class_router",
                    progress=0.1
                )

            # 1. Route and retrieve using World-Class Router
            # Pass thought_stream for progress emissions (Option C streaming)
            router_result = await self.world_class_router.route_and_retrieve(
                query=user_input,
                db=db,
                context=context,
                top_k=5,
                thought_stream=thought_stream  # Enable progress streaming
            )

            # Thought: Sources determined and retrieved
            if thought_stream:
                sources_str = ", ".join([s.value for s in router_result.sources_used])
                await thought_stream.add_thought(
                    ThoughtType.EXECUTING,
                    title=f"Sources consultées : {sources_str}",
                    content=f"Récupération parallèle terminée en {router_result.retrieval_time_ms:.0f}ms. {len(router_result.documents)} documents trouvés.",
                    agent="world_class_router",
                    progress=0.5
                )

            # 2. If no documents found, handle based on scenario
            if not router_result.documents:
                logger.warning("world_class_router_no_results", query=user_input[:50])

                # SCENARIO 2: Sources were queried but no data found
                # → Use LLM to generate intelligent alternatives
                if router_result.sources_queried:
                    logger.info("no_data_scenario", sources_queried=[s.value for s in router_result.sources_queried])

                    if thought_stream:
                        await thought_stream.add_thought(
                            ThoughtType.THINKING,
                            title="Aucune donnée trouvée",
                            content="Génération d'une réponse intelligente avec alternatives...",
                            agent="world_class_router",
                            progress=0.8
                        )

                    # Use SynthesisAgent's smart empty response
                    from app.services.agents.synthesis_agent import SynthesisAgent
                    synthesis_agent = SynthesisAgent()
                    smart_response = await synthesis_agent._generate_empty_response_smart(user_input)

                    if thought_stream:
                        await thought_stream.add_thought(
                            ThoughtType.COMPLETED,
                            title="Alternatives proposées",
                            content="Réponse générée avec suggestions d'actions.",
                            agent="world_class_router",
                            progress=1.0
                        )

                    return AgentResponse(
                        success=True,
                        message=smart_response.text,
                        data={},
                        agents_used=["world_class_router", "synthesis_agent"],
                        sources_used=[s.value for s in router_result.sources_queried],
                        confidence=0.5,
                        suggestions=[],
                        warnings=smart_response.warnings
                    )

                # SCENARIO 1: No sources identified → Routing ambiguity
                # → Ask user to clarify
                else:
                    logger.info("routing_ambiguity_scenario")

                    if thought_stream:
                        await thought_stream.add_thought(
                            ThoughtType.COMPLETED,
                            title="Demande peu claire",
                            content="Demande de clarification à l'utilisateur.",
                            agent="world_class_router",
                            progress=1.0
                        )

                    return AgentResponse(
                        success=True,
                        message="Je n'ai pas bien compris votre demande. Pouvez-vous préciser ce que vous recherchez ?",
                        data={},
                        agents_used=["world_class_router"],
                        sources_used=[],
                        confidence=0.3,
                        suggestions=["Reformuler la question", "Préciser le contexte", "Donner un exemple"],
                        warnings=[]
                    )

            # 3. ÉTAPE 3: Adaptive response - Skip synthesis for simple queries
            if router_result.skip_synthesis:
                # Simple SQL/WEB query → Use document content directly (template response or pre-synthesized)
                doc = router_result.documents[0]
                response_message = doc.content

                # Determine agent and source based on complexity
                if router_result.complexity.value == "simple_sql":
                    agent_name = "sql_agent"
                    sources = [DataSource.SQL]
                    thought_title = "Réponse SQL directe (fast-path)"
                    thought_content = f"Requête SQL simple - réponse directe en {router_result.total_time_ms:.0f}ms"
                elif router_result.complexity.value == "simple_web":
                    agent_name = "web_agent"
                    sources = [DataSource.WEB]
                    thought_title = "Réponse Web directe (fast-path)"
                    thought_content = f"Recherche web - réponse pré-synthétisée en {router_result.total_time_ms:.0f}ms"
                elif router_result.complexity.value == "simple_legal":
                    agent_name = "legal_agent"
                    sources = [DataSource.LEGIFRANCE]
                    thought_title = "Réponse juridique (fast-path)"
                    thought_content = f"Recherche Légifrance - réponse en {router_result.total_time_ms:.0f}ms"
                else:
                    agent_name = "fast_path"
                    sources = [s.value for s in router_result.sources_used]
                    thought_title = "Réponse directe (fast-path)"
                    thought_content = f"Réponse directe en {router_result.total_time_ms:.0f}ms"

                if thought_stream:
                    await thought_stream.add_thought(
                        ThoughtType.COMPLETED,
                        title=thought_title,
                        content=thought_content,
                        agent=agent_name,
                        progress=1.0
                    )

                logger.info("world_class_router_fast_path_complete",
                           query=user_input[:50],
                           complexity=router_result.complexity.value,
                           total_time_ms=router_result.total_time_ms)

                return AgentResponse(
                    success=True,
                    message=response_message,
                    data={
                        "router_metrics": {
                            "prefilter_ms": router_result.prefilter_time_ms,
                            "retrieval_ms": router_result.retrieval_time_ms,
                            "rerank_ms": router_result.rerank_time_ms,
                            "total_ms": router_result.total_time_ms,
                            "complexity": router_result.complexity.value,
                            "fast_path": True,
                            "is_legal_query": router_result.is_legal_query,
                            "is_pure_legal": router_result.is_pure_legal,
                            "sources_queried": [s.value for s in router_result.sources_queried],
                            "sources_used": [s.value for s in router_result.sources_used]
                        }
                    },
                    agents_used=["world_class_router", agent_name],
                    sources_used=sources,
                    confidence=0.95,
                    suggestions=[],
                    warnings=[]
                )

            # 4. Full synthesis for hybrid/complex queries
            # Convert documents to multi-source format for optimized synthesis
            documents = []
            for doc in router_result.documents:
                documents.append({
                    "content": doc.content,
                    "score": doc.score,
                    "source": doc.source.value,
                    "metadata": doc.metadata
                })

            # Use SynthesisAgent with multi-source synthesis (SINGLE LLM CALL)
            from app.services.agents.synthesis_agent import SynthesisAgent
            from app.services.agents.thought_stream import PROGRESS_MESSAGES
            synthesis_agent = SynthesisAgent()

            # Build router metrics for synthesis context
            router_metrics = {
                "complexity": router_result.complexity.value,
                "sources_queried": [s.value for s in router_result.sources_queried],
                "sources_used": [s.value for s in router_result.sources_used],
                "is_legal_query": router_result.is_legal_query,
                "is_pure_legal": router_result.is_pure_legal
            }

            # === PROGRESS: Synthesis (emit before LLM call) ===
            if thought_stream:
                msg = PROGRESS_MESSAGES["synthesis"]
                await thought_stream.add_thought(
                    msg["type"],
                    title=msg["title"],
                    content=msg["content"],
                    agent="synthesis",
                    progress=msg["progress"]
                )

            synthesized = await synthesis_agent.synthesize_multi_source(
                query=user_input,
                documents=documents,
                router_metrics=router_metrics,
                conversation_context=str(conversation_history[-3:]) if conversation_history else None
            )

            # Thought: Response synthesized
            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.COMPLETED,
                    title="Réponse synthétisée",
                    content=f"Confiance: {synthesized.overall_confidence:.0%}. {len(synthesized.sources)} sources citées.",
                    agent="synthesis",
                    progress=1.0
                )

            # 5. Build final response
            logger.info("world_class_router_complete",
                       query=user_input[:50],
                       complexity=router_result.complexity.value,
                       sources_used=[s.value for s in router_result.sources_used],
                       documents_count=len(router_result.documents),
                       total_time_ms=router_result.total_time_ms)

            return AgentResponse(
                success=True,
                message=synthesized.text,
                data={
                    "sources": [s.model_dump() for s in synthesized.sources],
                    "router_metrics": {
                        "prefilter_ms": router_result.prefilter_time_ms,
                        "retrieval_ms": router_result.retrieval_time_ms,
                        "rerank_ms": router_result.rerank_time_ms,
                        "total_ms": router_result.total_time_ms,
                        "complexity": router_result.complexity.value,
                        "is_legal_query": router_result.is_legal_query,
                        "is_pure_legal": router_result.is_pure_legal,
                        "sources_queried": [s.value for s in router_result.sources_queried],
                        "sources_used": [s.value for s in router_result.sources_used]
                    }
                },
                agents_used=["world_class_router", "synthesis"],
                sources_used=[DataSource.SQL if s == SourceType.SQL else
                             DataSource.RAG if s == SourceType.RAG else
                             DataSource.WEB if s == SourceType.WEB else
                             DataSource.LEGIFRANCE
                             for s in router_result.sources_used],
                confidence=synthesized.overall_confidence,
                suggestions=[],
                warnings=synthesized.warnings
            )

        except Exception as e:
            logger.error("world_class_router_error", error=str(e), query=user_input[:50])

            # Fallback to traditional routing
            return AgentResponse(
                success=False,
                message=f"Erreur lors du traitement: {str(e)}",
                data={},
                agents_used=["world_class_router"],
                sources_used=[],
                confidence=0.0,
                suggestions=["Réessayer", "Reformuler la question"],
                warnings=[str(e)]
            )

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
            response_data = {}
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

                # Build structured sources for this case
                if sql_rag_result.has_sql:
                    all_sources.append({"type": "sql", "title": "Base de données DisruptIQ"})

                if sql_rag_result.has_rag and sql_rag_result.rag_result.data:
                    rag_data = sql_rag_result.rag_result.data
                    chunks = rag_data.get("chunks", [])
                    for i, chunk in enumerate(chunks[:5], 1):
                        source_name = chunk.get("metadata", {}).get("title", "Document") or f"Document {chunk.get('document_id', i)}"
                        all_sources.append({
                            "type": "rag",
                            "id": i,
                            "title": source_name,
                            "document": source_name,
                            "confidence": chunk.get("score", chunk.get("cross_encoder_score", 0.5))
                        })

                # Update response_data with SQL results and sources
                if sql_rag_result.has_sql and sql_rag_result.sql_result.data:
                    response_data.update(sql_rag_result.sql_result.data)

                response_data["sources"] = all_sources

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

    # ================================================================
    # FACT EXTRACTION & STORAGE - Nice-to-Have Enhancement
    # ================================================================

    async def _extract_and_store_facts(
        self,
        user_input: str,
        session_id: str
    ):
        """
        Extract structured facts from user input and store in BOTH:
        - context_store (legacy compatibility)
        - UnifiedContextManager (Phase 3 - SSOT)

        Extracts:
        - Budgets (75000€, 50k, 120000 euros)
        - Dates (25 février, 10 avril 2024, le 15/03)
        - Contacts (M. Dupont, apt 45, marie@gmail.com)
        - Counts (2 emails, 5 jardiniers, 8 copros)
        """
        import re

        try:
            # Get UnifiedContextManager for this session
            unified_ctx = get_unified_context_manager(session_id)

            # Extract budgets - improved regex for all formats
            budget_patterns = [
                (r'(\d+)\s?k€?', lambda m: int(m) * 1000),  # 75k, 50k€
                (r'(\d+)\s+(?:mille|thousand)\s+(?:euros?|€)?', lambda m: int(m) * 1000),  # 75 mille euros
                (r'(\d+(?:\s?\d+)*)\s?(?:€|euros?)', lambda m: int(m.replace(' ', '')))  # 75000€, 75 000€, 120000 euros
            ]

            for pattern, converter in budget_patterns:
                matches = re.finditer(pattern, user_input, re.IGNORECASE)
                for match_obj in matches:
                    try:
                        amount = converter(match_obj.group(1))
                        fact_data = {
                            "amount": amount,
                            "original_text": match_obj.group(0),
                            "extracted_from": user_input[:100]
                        }
                        # Store in both systems
                        context_store.add_fact(session_id, "budget", fact_data)
                        unified_ctx.add_fact("budget", fact_data)
                        logger.info("fact_extracted_budget", amount=amount, session=session_id)
                    except:
                        pass

            # Extract dates - improved to capture full date strings
            date_patterns = [
                r'(\d{1,2}\s+(?:janvier|février|f[ée]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[ée]cembre)(?:\s+\d{4})?)',
                r'le\s+(\d{1,2}[/\-]\d{1,2}(?:[/\-]\d{2,4})?)',
                r'(\d{1,2}\s+(?:jan|f[ée]v|mar|avr|mai|jun|jul|ao[uû]|sep|oct|nov|d[ée]c)(?:\.|\s))',
            ]
            for pattern in date_patterns:
                matches = re.findall(pattern, user_input, re.IGNORECASE)
                for match in matches:
                    date_clean = match.strip()
                    fact_data = {
                        "date_text": date_clean,
                        "extracted_from": user_input[:100]
                    }
                    # Store in both systems
                    context_store.add_fact(session_id, "date", fact_data)
                    unified_ctx.add_fact("date", fact_data)
                    logger.info("fact_extracted_date", date=date_clean, session=session_id)

            # Extract counts
            count_patterns = [
                r'(\d+)\s+(?:emails?|mails?|messages?)',
                r'(\d+)\s+(?:copropriétaires?|copros?|résidents?)',
                r'(\d+)\s+(?:professionnels?|jardiniers?|plombiers?|couvreurs?|peintres?)',
            ]
            for pattern in count_patterns:
                matches = re.findall(pattern, user_input, re.IGNORECASE)
                for match in matches:
                    fact_data = {
                        "count": int(match),
                        "extracted_from": user_input[:100]
                    }
                    # Store in both systems
                    context_store.add_fact(session_id, "count", fact_data)
                    unified_ctx.add_fact("count", fact_data)
                    logger.info("fact_extracted_count", count=match, session=session_id)

        except Exception as e:
            logger.error("fact_extraction_failed", error=str(e))
            # Don't fail the whole request if extraction fails
            pass

    async def _handle_email_confirmation(
        self,
        state_manager,
        db: AsyncSession,
        session_id: Optional[str] = None,
        thought_stream = None
    ) -> AgentResponse:
        """
        Handle email confirmation - send draft via N8N webhook

        Args:
            state_manager: State manager with email_draft
            db: Database session
            session_id: Session ID for context
            thought_stream: ThoughtStream for real-time updates

        Returns:
            AgentResponse with send status
        """
        from app.services.webhook_service import WebhookService

        try:
            # Get draft from state
            email_draft = state_manager.state.email_draft
            if not email_draft:
                logger.error("email_confirmation_no_draft")
                return AgentResponse(
                    success=False,
                    message="❌ Aucun brouillon d'email trouvé. Veuillez d'abord générer un email.",
                    data={},
                    agents_used=["orchestrator"],
                    sources_used=[],
                    confidence=1.0,
                    suggestions=["Générer un nouvel email"],
                    warnings=[]
                )

            # Extract email data
            subject = email_draft.get("subject", "Sans objet")
            body = email_draft.get("body", "")
            recipients = email_draft.get("recipients", [])
            tone = email_draft.get("tone", "professional")
            urgency = email_draft.get("urgency", "medium")

            # Validate recipients
            if not recipients or len(recipients) == 0:
                logger.error("email_confirmation_no_recipients")
                return AgentResponse(
                    success=False,
                    message="❌ Aucun destinataire trouvé dans le brouillon. Impossible d'envoyer l'email.",
                    data={"email_draft": email_draft},
                    agents_used=["orchestrator"],
                    sources_used=[],
                    confidence=1.0,
                    suggestions=["Générer un nouvel email avec destinataires"],
                    warnings=[]
                )

            logger.info("sending_email_confirmation",
                       recipients_count=len(recipients),
                       subject=subject[:50])

            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.WORKFLOW_SENDING,
                    title="Envoi vers N8N",
                    content=f"Transmission de l'email à {len(recipients)} destinataire(s)...",
                    agent="workflow_agent",
                    data={
                        "recipients_count": len(recipients),
                        "subject": subject[:50]
                    },
                    progress=0.7
                )

            # Send via N8N webhook
            webhook_service = WebhookService()
            result = None

            # Extract thought_stream_id if available
            ts_id = thought_stream.session_id if thought_stream else None

            try:
                result = await webhook_service.send_email(
                    subject=subject,
                    body=body,
                    recipients=recipients,
                    tenant_id="default",  # TODO: Get from context
                    user_id="user",       # TODO: Get from context
                    urgency=urgency,
                    tone=tone,
                    request_id=f"email_{session_id}" if session_id else None,
                    thought_stream_id=ts_id,
                    conversation_id=session_id
                )

            finally:
                await webhook_service.close()

            # Check result (AFTER try/finally to avoid exception catching the return)
            if result:
                # Déterminer le statut de l'envoi
                # N8N peut retourner plusieurs formats selon la config du workflow:
                # 1. Réponse d'email correcte: {"success": true, "emails_sent": [...]}
                # 2. Réponse callback (bug workflow): {"status": "warning/success", "message": "..."}
                # 3. Erreur: {"success": false, "error": "..."}

                has_explicit_success = result.get("success") == True
                has_emails_sent = "emails_sent" in result  # Marqueur de vraie réponse d'email
                has_status_success = result.get("status") == "success"
                has_status_warning = result.get("status") == "warning"

                # Si on a emails_sent, c'est la bonne réponse
                # Si on a status warning/success mais pas emails_sent, c'est la réponse du callback
                # Dans ce cas, on considère que l'email a été envoyé (le callback n'est qu'une notification)
                is_success = has_explicit_success or has_emails_sent or has_status_success or has_status_warning
                has_warning = has_status_warning and not has_emails_sent  # Warning seulement si pas de vraie réponse

                if is_success:
                    logger.info("email_sent_successfully",
                               recipients_count=len(recipients),
                               has_warning=has_warning,
                               n8n_response=result)

                    if thought_stream:
                        await thought_stream.add_thought(
                            ThoughtType.WORKFLOW_SUCCESS,
                            title=f"Email envoyé ({len(recipients)} dest.)",
                            content="Workflow N8N exécuté avec succès",
                            agent="workflow_agent",
                            data={
                                "recipients_count": len(recipients),
                                "status": "sent"
                            },
                            progress=1.0
                        )

                    # Clear draft and pending action
                    state_manager.state.email_draft = None
                    state_manager.state.clear_pending_action()

                    # Format recipient list for display
                    recipient_list = []
                    for r in recipients:
                        if isinstance(r, dict):
                            recipient_list.append(r.get("email", str(r)))
                        else:
                            recipient_list.append(str(r))

                    message = f"✅ **Email envoyé avec succès !**\n\n"
                    message += f"**Destinataire(s):** {', '.join(recipient_list)}\n"
                    message += f"**Objet:** {subject}\n\n"
                    message += "L'email a été envoyé via N8N et devrait arriver dans quelques instants."

                    # Ajouter un avertissement si le callback N8N a échoué (non-bloquant)
                    warnings_list = []
                    if has_warning:
                        warning_msg = result.get("message", "")
                        if warning_msg:
                            warnings_list.append(f"Note: {warning_msg}")

                    return AgentResponse(
                        success=True,
                        message=message,
                        data={
                            "n8n_response": result,
                            "recipients_count": len(recipients),
                            "subject": subject
                        },
                        agents_used=["orchestrator", "webhook_service", "n8n"],
                        sources_used=[],
                        confidence=1.0,
                        suggestions=[],
                        warnings=warnings_list
                    )
                else:
                    # N8N error
                    error_msg = result.get("error", result.get("message", "Erreur inconnue"))
                    logger.error("n8n_email_send_failed",
                                error=error_msg,
                                n8n_response=result)

                    if thought_stream:
                        await thought_stream.add_thought(
                            ThoughtType.WORKFLOW_ERROR,
                            title="Échec de l'envoi N8N",
                            content=f"Erreur : {error_msg[:100]}",
                            agent="workflow_agent",
                            data={
                                "error": error_msg,
                                "status": "failed"
                            },
                            progress=1.0
                        )

                    return AgentResponse(
                        success=False,
                        message=f"❌ **Erreur lors de l'envoi de l'email**\n\n{error_msg}\n\nLe brouillon est toujours disponible. Vous pouvez réessayer ou le modifier.",
                        data={
                            "email_draft": email_draft,
                            "error": error_msg,
                            "n8n_response": result
                        },
                        agents_used=["orchestrator", "webhook_service"],
                        sources_used=[],
                        confidence=1.0,
                        suggestions=["Réessayer", "Modifier l'email", "Annuler"],
                        warnings=[f"Erreur N8N: {error_msg}"]
                    )

        except Exception as e:
            logger.error("email_confirmation_failed",
                        error=str(e),
                        exc_info=True)

            if thought_stream:
                await thought_stream.add_thought(
                    ThoughtType.ERROR,
                    title="Erreur système",
                    content=f"❌ Erreur technique : {str(e)}",
                    agent="orchestrator",
                    progress=1.0
                )

            return AgentResponse(
                success=False,
                message=f"❌ **Erreur technique lors de l'envoi**\n\n{str(e)}\n\nVeuillez réessayer ou contacter le support si le problème persiste.",
                data={},
                agents_used=["orchestrator"],
                sources_used=[],
                confidence=1.0,
                suggestions=["Réessayer", "Annuler"],
                warnings=[f"Exception: {str(e)}"]
            )

    async def _recall_from_context_store(
        self,
        user_input: str,
        session_id: str
    ) -> Optional[str]:
        """
        Recall structured facts from context_store

        More reliable than LLM memory for structured data like budgets/dates
        """
        import re

        try:
            # Detect what user is asking for
            user_lower = user_input.lower()

            # Budget recall
            if any(kw in user_lower for kw in ['budget', 'montant', 'combien', 'coût', 'prix', '€', 'euros']):
                budget_facts = context_store.query_facts(session_id, "budget")
                if budget_facts:
                    # Get most recent budget
                    latest = max(budget_facts, key=lambda f: f['timestamp'])
                    amount = latest['data']['amount']

                    # Format nicely
                    if amount >= 1000:
                        formatted = f"{amount:,}€".replace(',', ' ')
                    else:
                        formatted = f"{amount}€"

                    return f"Le budget était de **{formatted}**."

            # Date recall
            if any(kw in user_lower for kw in ['date', 'quand', 'jour', 'février', 'mars', 'avril']):
                date_facts = context_store.query_facts(session_id, "date")
                if date_facts:
                    latest = max(date_facts, key=lambda f: f['timestamp'])
                    date_text = latest['data']['date_text']
                    return f"La date était le **{date_text}**."

            # Count recall
            if any(kw in user_lower for kw in ['combien', 'nombre', 'total']) and any(kw in user_lower for kw in ['email', 'mail', 'copro', 'résident']):
                count_facts = context_store.query_facts(session_id, "count")
                if count_facts:
                    # Sum all counts mentioned
                    total = sum(f['data']['count'] for f in count_facts)
                    return f"Il y avait **{total}** au total."

            return None

        except Exception as e:
            logger.error("context_store_recall_failed", error=str(e))
            return None
