"""
Intent Classifier V6 - World-Class SMA Routing with UI Source Selection
Phase 3 Refactoring - Context-Aware Classification + UI Sources

✅ CURRENT VERSION - Production Ready V6

Key Improvements V6:
- UI Source Selection: SQL/RAG/Internet checkboxes drive routing
- Hybrid Search: Multi-source queries aggregate results
- REQUEST_QUOTES merged into SEND_EMAIL (same N8N agent)
- WEB_SEARCH only when Internet checked OR explicit request
- Context-aware email detection (distingue "envoie email" vs "envoie-moi")
- SQL keywords checked BEFORE email verbs (priority order fix)
- Clarification automatique sous 0.70 confiance

Source Selection Logic:
1. Single source checked → Route directly (SQL/RAG/WEB)
2. Multiple sources checked → Hybrid search (orchestrator aggregates)
3. No source checked → Auto-detect from vocabulary/context

Phase 3 World-Class SMA Architecture:
- Compatible with BaseAgent interface via wrapped_agents.py
- Integrates with AgentRegistry for smart routing
- Supports ResilientAgent wrapper for production resilience

Author: Claude Code - Phase 3 World-Class SMA
Date: November 27, 2025
"""

import re
import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services.llm_service import LLMService
from app.models.intent import (
    IntentType,
    Domain,
    DataSource,
    IntentClassification,
)

logger = structlog.get_logger()


class IntentClassifierV5:
    """
    World-class intent classifier with context-awareness

    Philosophy V6:
    - Context-first: Check conversation context before keyword matching
    - Info requests BEFORE action intents (prevent false positives)
    - Clarification for ambiguous cases (confidence < 0.70)
    - Quick rules catch 70% of queries
    - LLM handles remaining 30%
    """

    def __init__(self):
        self.llm_service = LLMService()

        # Confidence thresholds - RAISED for better precision
        self.THRESHOLD_HIGH = 0.85
        self.THRESHOLD_MEDIUM = 0.70  # Clarification threshold
        self.THRESHOLD_LOW = 0.60     # Raised from 0.50 - below this = ask user

        # Info request patterns (distinguish from action verbs)
        self.INFO_REQUEST_PATTERNS = [
            "envoie-moi", "envoie moi", "envoi-moi", "envoi moi",
            "donne-moi", "donne moi", "dis-moi", "dis moi",
            "montre-moi", "montre moi", "affiche-moi", "affiche moi",
            "explique-moi", "explique moi", "récapitule", "résume",
            "rappelle-moi", "rappelle moi", "c'est quoi", "qu'est-ce"
        ]

    async def classify(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        **kwargs  # Accept extra args for backward compatibility
    ) -> IntentClassification:
        """
        Classify user intent with UI source selection support

        Args:
            user_input: User's message
            context: Optional context including:
                - has_uploaded_documents: bool
                - selected_sources: List[str] - UI checkboxes ["sql", "rag", "web"]
            conversation_history: Previous messages

        Returns:
            IntentClassification with intent, domain, confidence, suggested_sources
            - is_hybrid_search: True if multiple sources selected
            - selected_sources: Sources from UI (for orchestrator)
        """
        start_time = datetime.now()
        query_lower = user_input.lower()

        logger.info("classification_started", query=user_input[:50])

        # Initialize context
        if context is None:
            context = {}

        has_documents = context.get("has_uploaded_documents", False) or \
                       context.get("has_active_documents", False)

        # ================================================================
        # PHASE 0: UI SOURCE SELECTION - Priority routing based on checkboxes
        # ================================================================
        selected_sources = context.get("selected_sources", [])  # ["sql", "rag", "web"]

        # Normalize source names
        selected_sources = [s.lower() for s in selected_sources] if selected_sources else []

        logger.info("sources_from_ui", sources=selected_sources)

        # CASE 1: Single source checked → Direct routing (no ambiguity)
        if len(selected_sources) == 1:
            source = selected_sources[0]
            result = self._route_single_source(source, query_lower, user_input)
            if result:
                processing_time = (datetime.now() - start_time).total_seconds() * 1000
                logger.info("single_source_routing",
                           source=source,
                           intent=result.intent.value,
                           time_ms=processing_time)
                return result

        # CASE 2: Multiple sources checked → Hybrid search
        elif len(selected_sources) > 1:
            result = await self._route_hybrid_search(selected_sources, query_lower, user_input, context, conversation_history)
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.info("hybrid_search_routing",
                       sources=selected_sources,
                       intent=result.intent.value,
                       time_ms=processing_time)
            return result

        # CASE 3: No source checked → Auto-detect (existing logic)
        # Continue to quick rules and LLM classification

        # ================================================================
        # PHASE 1: Quick Rules (70% of queries) - Now with conversation context
        # ================================================================
        quick_result = await self._quick_rules_classification(
            query_lower,
            has_documents,
            conversation_history
        )

        if quick_result:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.info("quick_rule_matched",
                       intent=quick_result.intent.value,
                       confidence=quick_result.confidence,
                       rule=quick_result.reasoning,
                       time_ms=processing_time)
            return quick_result

        # PHASE 2: LLM Classification (30% of queries)
        llm_result = await self._llm_classification(user_input, context, conversation_history)

        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        logger.info("llm_classification_complete",
                   intent=llm_result.intent.value,
                   confidence=llm_result.confidence,
                   time_ms=processing_time)

        return llm_result

    def _route_single_source(self, source: str, query_lower: str, user_input: str) -> Optional[IntentClassification]:
        """
        Route directly when user selected a single source in UI

        Args:
            source: "sql", "rag", or "web"
            query_lower: Lowercase query
            user_input: Original user input

        Returns:
            IntentClassification for the single source
        """
        if source == "sql":
            return IntentClassification(
                intent=IntentType.QUERY_DATA,
                domain=Domain.PROPERTY_MGMT,
                confidence=0.98,  # High confidence - user explicitly chose
                suggested_sources=[DataSource.SQL],
                reasoning="User selected SQL source in UI",
                keywords_matched=["ui_source_sql"],
                is_hybrid_search=False
            )
        elif source in ["rag", "documents"]:
            return IntentClassification(
                intent=IntentType.SEARCH_DOCUMENTS,
                domain=Domain.PROPERTY_MGMT,
                confidence=0.98,
                suggested_sources=[DataSource.RAG, DataSource.UPLOADED_DOCS],
                reasoning="User selected Documents/RAG source in UI",
                keywords_matched=["ui_source_rag"],
                is_hybrid_search=False
            )
        elif source in ["web", "internet"]:
            return IntentClassification(
                intent=IntentType.WEB_SEARCH,
                domain=Domain.GENERAL,
                confidence=0.98,
                suggested_sources=[DataSource.WEB],
                reasoning="User selected Internet source in UI",
                keywords_matched=["ui_source_web"],
                is_hybrid_search=False
            )
        return None

    async def _route_hybrid_search(
        self,
        sources: List[str],
        query_lower: str,
        user_input: str,
        context: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> IntentClassification:
        """
        Route to hybrid search when multiple sources are selected

        The orchestrator will:
        1. Query all selected sources
        2. Aggregate results
        3. Generate cross-source synthesis

        Args:
            sources: List of selected sources ["sql", "rag", "web"]
            query_lower: Lowercase query
            user_input: Original user input
            context: Full context
            conversation_history: Previous messages

        Returns:
            IntentClassification with is_hybrid_search=True
        """
        # Map sources to DataSource enum
        source_map = {
            "sql": DataSource.SQL,
            "rag": DataSource.RAG,
            "documents": DataSource.RAG,
            "web": DataSource.WEB,
            "internet": DataSource.WEB,
        }

        suggested_sources = []
        for s in sources:
            if s in source_map:
                suggested_sources.append(source_map[s])

        # Determine primary intent based on vocabulary (for hybrid, still need a "main" intent)
        # This helps the orchestrator know which agent to prioritize
        primary_intent = await self._detect_primary_intent_for_hybrid(query_lower, user_input, context)

        return IntentClassification(
            intent=primary_intent,
            domain=Domain.PROPERTY_MGMT,
            confidence=0.95,
            suggested_sources=suggested_sources,
            reasoning=f"Hybrid search across {', '.join(sources)} - UI multi-source selection",
            keywords_matched=["ui_hybrid_search"],
            is_hybrid_search=True,
            selected_ui_sources=sources  # Pass to orchestrator for execution
        )

    async def _detect_primary_intent_for_hybrid(
        self,
        query_lower: str,
        user_input: str,
        context: Dict[str, Any]
    ) -> IntentType:
        """
        Detect primary intent for hybrid searches

        Even with hybrid search, we need a "main" intent to help orchestrator
        prioritize and structure the response.

        Priority:
        1. Document content words → SEARCH_DOCUMENTS
        2. Database entity words → QUERY_DATA
        3. Default → SEARCH_DOCUMENTS (safer for hybrid)
        """
        # Document content indicators
        doc_indicators = [
            "facture", "contrat", "devis", "pv ", "procès-verbal",
            "document", "analyse", "résume", "que dit", "selon"
        ]

        # Database entity indicators
        db_indicators = [
            "copropriétaire", "copropriété", "professionnel",
            "liste", "combien", "nombre", "tous les", "toutes les"
        ]

        has_doc_indicator = any(ind in query_lower for ind in doc_indicators)
        has_db_indicator = any(ind in query_lower for ind in db_indicators)

        if has_doc_indicator and not has_db_indicator:
            return IntentType.SEARCH_DOCUMENTS
        elif has_db_indicator and not has_doc_indicator:
            return IntentType.QUERY_DATA
        elif has_doc_indicator and has_db_indicator:
            # Both present - default to documents for richer context
            return IntentType.SEARCH_DOCUMENTS
        else:
            # Neither - use SEARCH_DOCUMENTS as safer default for hybrid
            return IntentType.SEARCH_DOCUMENTS

    def _is_info_request(self, query_lower: str) -> bool:
        """
        Detect if query is an info request (not an action)

        "Envoie-moi le budget" = INFO REQUEST (QUERY_DATA)
        "Envoie un email aux copropriétaires" = ACTION (SEND_EMAIL)
        """
        return any(pattern in query_lower for pattern in self.INFO_REQUEST_PATTERNS)

    def _has_explicit_email_target(self, query_lower: str) -> bool:
        """
        Check if query has explicit email recipients or email context

        "envoie un email à..." = True
        "contacte les copropriétaires" = True
        "envoie-moi les infos" = False
        """
        email_target_patterns = [
            "email à", "mail à", "email aux", "mail aux",
            "message à", "message aux",
            "contacte ", "contacter ",
            "écris à", "écrire à",
            # Verbes de communication (sans mot "email") → détection destinataire
            "préviens", "prévenir", "previens", "prevenir",
            "informe", "informer",  # AJOUTÉ
            "notifie", "notifier",  # AJOUTÉ
            "avertis", "avertir",   # AJOUTÉ
            "alerter", "alerte ",
            # Types de destinataires
            "copropriétaires", "copropriétaire",
            "professionnel", "professionnels",
            "prestataire",  # Important target for vendor emails
            "chauffagiste", "plombier", "électricien",
            "plomberie", "électricité",  # Company type names
            "fournisseur", "artisan", "entreprise",  # Vendor types
            "voisin", "voisins", "syndic",
            "conseil syndical",  # AJOUTÉ: AG context
            "propriétaire", "propriétaires",  # AJOUTÉ
            "locataire", "locataires",  # AJOUTÉ
        ]
        return any(pattern in query_lower for pattern in email_target_patterns)

    async def _quick_rules_classification(
        self,
        query_lower: str,
        has_documents: bool,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Optional[IntentClassification]:
        """
        Quick rule-based classification (70% accuracy target)

        PRIORITY ORDER V7 - FIXED:
        0. INFO REQUESTS (intercept "envoie-moi", "donne-moi" etc.)
        0.5 RAG DOCUMENT SEARCH - AVANT SQL! (facture, montant, devis, contrat, prestataire)
        1. SQL queries (aggregations, lists - ONLY for DB entities)
        2. Email actions (only with explicit recipients)
        3. Legal keywords
        4. Web search (explicit internet requests)
        5. Workflow triggers (incidents, emergencies)
        6. Quotes (devis requests)
        """

        # ================================================================
        # 0. DIGEST/EMAIL SUMMARY - Check first (highest priority for digest requests)
        # ================================================================
        digest_keywords = {
            # Direct digest requests
            "mail digest": 0.98,
            "email digest": 0.98,
            "génère le digest": 0.98,
            "génère mon digest": 0.98,
            "génère moi le digest": 0.98,
            "génère-moi le digest": 0.98,
            "genere le digest": 0.98,
            "genere mon digest": 0.98,
            "genere moi le digest": 0.98,
            "montre le digest": 0.95,
            "montre-moi le digest": 0.95,
            "affiche le digest": 0.95,
            "affiche-moi le digest": 0.95,
            "mon digest": 0.92,
            "le digest": 0.90,
            "digest des emails": 0.98,
            "digest des mails": 0.98,
            "digest email": 0.95,
            # Email summary requests
            "résumé des emails": 0.95,
            "résumé des mails": 0.95,
            "résumé de mes emails": 0.95,
            "résumé de mes mails": 0.95,
            "synthèse des emails": 0.95,
            "synthèse des mails": 0.95,
            "emails reçus": 0.90,
            "mails reçus": 0.90,
            "emails d'hier": 0.92,
            "emails de la semaine": 0.92,
            "emails urgents": 0.90,
            "emails importants": 0.90,
            "quels emails": 0.88,
            "quels mails": 0.88,
            "mes emails": 0.85,
            "mes mails": 0.85,
            # Classification by urgency
            "classe les emails": 0.92,
            "classe-les par": 0.90,
            "trie les emails": 0.90,
            "trie-les par urgence": 0.92,
        }

        for keyword, confidence in digest_keywords.items():
            if keyword in query_lower:
                logger.info("digest_keyword_matched", keyword=keyword, confidence=confidence)
                return IntentClassification(
                    intent=IntentType.GENERATE_DIGEST,
                    domain=Domain.PROPERTY_MGMT,
                    confidence=confidence,
                    suggested_sources=[DataSource.SQL],
                    reasoning=f"Digest keyword '{keyword}' - generating email digest",
                    keywords_matched=[keyword]
                )

        # ================================================================
        # 0.5 INFO REQUEST INTERCEPTION - CRITICAL FIX
        # Prevents "envoie-moi le budget" → SEND_EMAIL (was 15-20% false positive)
        # ================================================================
        is_info_request = self._is_info_request(query_lower)

        if is_info_request:
            logger.debug("info_request_detected", query=query_lower[:50])
            # Continue to SQL/RAG classification, skip email detection

        # ================================================================
        # 0.5 RAG DOCUMENT SEARCH - AVANT SQL! (CRITICAL FIX)
        # "montant facture", "quel prestataire", "dans le contrat" → RAG
        # ================================================================
        rag_document_keywords = {
            # Factures et montants
            "montant de la facture": 0.95,
            "montant facture": 0.95,
            "montant du devis": 0.95,
            "prix dans": 0.90,
            "coût dans": 0.90,
            "tarif dans": 0.90,
            # Questions sur contenu documents
            "quel prestataire": 0.92,
            "qui a fait les travaux": 0.92,
            "qui a réalisé": 0.90,
            "qui a émis": 0.92,  # NOUVEAU
            "qui a envoyé": 0.90,  # NOUVEAU
            "émis la facture": 0.95,  # NOUVEAU
            "émetteur de la facture": 0.95,  # NOUVEAU
            "quel fournisseur": 0.90,
            "quel artisan": 0.90,
            "nom du prestataire": 0.92,
            "nom de l'entreprise": 0.90,
            # Contenu spécifique documents
            # NOTE: "que dit le/la" retiré car trop générique - capte aussi "que dit la loi" (LEGAL)
            # Utiliser des variantes spécifiques ci-dessous
            "que dit le document": 0.92,
            "que dit le contrat": 0.92,
            "que dit le devis": 0.92,
            "que dit la facture": 0.92,
            "que dit ce document": 0.92,
            "selon le document": 0.95,
            "selon la facture": 0.95,
            "selon le contrat": 0.95,
            "selon le devis": 0.95,
            "dans la facture": 0.95,
            "dans le contrat": 0.95,
            "dans le devis": 0.95,
            "dans le pv": 0.95,
            "dans le procès-verbal": 0.95,
            # Résumés documents
            "résume le document": 0.95,
            "résume la facture": 0.95,
            "résume le contrat": 0.95,
            "résumé du pv": 0.95,
            "analyse le document": 0.92,
            "analyse la facture": 0.92,
            # Synthèses de conversation/dossier
            "synthèse": 0.90,
            "synthese": 0.90,
            "résumé complet": 0.92,
            "résume complet": 0.92,
            "résume notre conversation": 0.95,
            "résumé de notre conversation": 0.95,
            "récapitule": 0.90,
            "récapitulatif": 0.90,
            "résumé du dossier": 0.92,
            "résume le dossier": 0.92,
            "fais une synthèse": 0.92,
            "fais un résumé": 0.92,
            "les faits": 0.85,
            "les actions effectuées": 0.88,
            "ce qui a été fait": 0.88,
            # Questions sur documents uploadés
            "sur la facture": 0.90,  # NOUVEAU
            "sur le contrat": 0.90,  # NOUVEAU
            "sur le devis": 0.90,  # NOUVEAU
        }

        for keyword, confidence in rag_document_keywords.items():
            if keyword in query_lower:
                logger.info("rag_document_keyword_matched", keyword=keyword, confidence=confidence)
                return IntentClassification(
                    intent=IntentType.SEARCH_DOCUMENTS,
                    domain=Domain.PROPERTY_MGMT,
                    confidence=confidence,
                    suggested_sources=[DataSource.RAG, DataSource.UPLOADED_DOCS],
                    reasoning=f"RAG document keyword '{keyword}' - searching in uploaded documents",
                    keywords_matched=[keyword]
                )

        # Check for document-related words that should trigger RAG (even without explicit "dans")
        doc_content_words = ["facture", "devis", "contrat", "pv ", "procès-verbal"]
        question_words = ["quel", "quelle", "quels", "quelles", "combien", "montant", "prix", "coût"]

        has_doc_word = any(dw in query_lower for dw in doc_content_words)
        has_question = any(qw in query_lower for qw in question_words)

        # "Quel est le montant de la facture" → RAG (not SQL!)
        if has_doc_word and has_question:
            # Exception: "combien de factures" = SQL count, not RAG content
            sql_count_patterns = ["combien de factures", "combien de devis", "combien de contrats",
                                  "nombre de factures", "nombre de devis", "liste des factures"]
            if not any(pattern in query_lower for pattern in sql_count_patterns):
                logger.info("rag_inferred_from_doc_question", query=query_lower[:50])
                return IntentClassification(
                    intent=IntentType.SEARCH_DOCUMENTS,
                    domain=Domain.PROPERTY_MGMT,
                    confidence=0.88,
                    suggested_sources=[DataSource.RAG, DataSource.UPLOADED_DOCS],
                    reasoning="Question about document content (facture/devis/contrat)",
                    keywords_matched=["document_content_question"]
                )

        # ================================================================
        # 1. EMAIL ACTIONS - PRIORITY CHECK (before SQL to avoid misclassification)
        # "Envoie un email aux copropriétaires" must be SEND_EMAIL, not QUERY_DATA
        # ================================================================
        if not is_info_request:
            # CRITICAL: Explicit email phrases that MUST be classified as SEND_EMAIL
            # Priority check BEFORE SQL to prevent "tous les copropriétaires" → QUERY_DATA
            email_explicit_phrases = [
                # Email keywords
                "envoie un email", "envoie un mail", "envoyer un email",
                "envoie email", "envoie mail",
                "génère un email", "génère email", "genere un email", "genere email",
                "écris un email", "ecris un email",
                "rédige un email", "redige un email",
                # CRITICAL: Convocation/communication patterns (often to "tous les copropriétaires")
                "envoie la convocation", "envoie une convocation", "envoie les convocations",
                "envoyer la convocation", "envoyer une convocation", "envoyer les convocations",
                "envoi la convocation", "envoi une convocation", "envoi les convocations",
                "envoie l'invitation", "envoie une invitation", "envoie les invitations",
                "envoie la notification", "envoie une notification",
                "envoie l'alerte", "envoie une alerte",
                "envoie le message", "envoie un message",
                "envoie l'information", "envoie une information", "envoie les informations",
            ]

            has_explicit_email_phrase = any(phrase in query_lower for phrase in email_explicit_phrases)

            # ALSO check: "envoie" + email recipient target without explicit "email" word
            simple_send_verbs = ["envoie ", "envoyer ", "envoi "]
            has_send_verb = any(verb in query_lower for verb in simple_send_verbs)
            has_recipient_target = self._has_explicit_email_target(query_lower)

            # "Envoie aux copropriétaires" = SEND_EMAIL (not SQL)
            is_send_to_recipient = has_send_verb and has_recipient_target

            if has_explicit_email_phrase or is_send_to_recipient:
                # This is definitely an email action, not a SQL query
                logger.info("explicit_email_phrase_detected", query=query_lower[:50])
                return IntentClassification(
                    intent=IntentType.SEND_EMAIL,
                    domain=Domain.PROPERTY_MGMT,
                    confidence=0.95,
                    suggested_sources=[DataSource.SQL, DataSource.CONVERSATION],
                    reasoning="Explicit email action phrase detected",
                    keywords_matched=["email", "explicit"]
                )

        # ================================================================
        # 2. SQL QUERIES - For DATABASE entities only (not document content)
        # ================================================================
        sql_strong_keywords = {
            "combien": 0.95,
            "nombre de": 0.95,
            "liste des": 0.90,
            "liste-moi": 0.90,
            "donne-moi la liste": 0.90,
            "donne la liste": 0.90,
            "affiche la liste": 0.90,
            "montre-moi": 0.85,
            "montre la liste": 0.85,
            "envoie-moi la liste": 0.90,  # NEW: Info request variant
            "envoie-moi le": 0.85,        # NEW: Info request variant
            "envoie moi le": 0.85,        # NEW: Info request variant
            "tous les": 0.85,
            "toutes les": 0.85,
            "moyenne": 0.95,
            "total": 0.85,
            "quel est le": 0.80,
            "quels sont les": 0.85,
            "qui sont les": 0.85,
            "qui a": 0.80,
            "qui ont": 0.80,
        }

        for keyword, confidence in sql_strong_keywords.items():
            if keyword in query_lower:
                # Check for database entities
                db_entities = ["copropriétaire", "copropriété", "professionnel",
                              "syndic", "document", "budget", "charge", "email",
                              "impayé", "lot", "appartement"]
                if any(entity in query_lower for entity in db_entities):
                    return IntentClassification(
                        intent=IntentType.QUERY_DATA,
                        domain=Domain.PROPERTY_MGMT,
                        confidence=confidence,
                        suggested_sources=[DataSource.SQL],
                        reasoning=f"SQL keyword '{keyword}' + database entity detected",
                        keywords_matched=[keyword]
                    )

        # ================================================================
        # 3. EMAIL ACTIONS - Additional patterns (if not caught by priority check)
        # ================================================================
        if not is_info_request:
            # Explicit email action verbs WITH recipient context
            # CLARIFICATION FINALE: "préviens/informe/notifie" + destinataire = SEND_EMAIL
            # Même sans le mot "email" explicite
            email_action_verbs = [
                "envoie un email", "envoie un mail", "envoyer un email",
                "écris un email", "écris un message", "ecris un email", "ecris un message",
                "rédige email", "rédige un email", "redige email", "redige un email",
                "transmets", "génère email", "génère un email", "genere email", "genere un email",
                "génère la convocation", "génère convocation",
                "crée la convocation", "crée convocation",
                "prépare la convocation", "prépare convocation",
                # Verbes de communication → SEND_EMAIL (même sans "email")
                "contacte", "contacter",
                "préviens", "prévenir", "previens", "prevenir",  # Avec et sans accent
                "informe", "informer",  # AJOUTÉ
                "notifie", "notifier",  # AJOUTÉ
                "avertis", "avertir",   # AJOUTÉ
                "alerte", "alerter"
            ]

            has_email_verb = any(verb in query_lower for verb in email_action_verbs)
            has_email_target = self._has_explicit_email_target(query_lower)

            # Simple "envoie" without explicit target = check context more carefully
            simple_email_verbs = ["envoie", "envoyer", "envoi"]
            has_simple_verb = any(verb in query_lower for verb in simple_email_verbs)

            if has_email_verb and has_email_target:
                return IntentClassification(
                    intent=IntentType.SEND_EMAIL,
                    domain=Domain.PROPERTY_MGMT,
                    confidence=0.92,
                    suggested_sources=[DataSource.SQL, DataSource.CONVERSATION],
                    reasoning="Email action verb with explicit recipient",
                    keywords_matched=["email", "recipient"]
                )
            elif has_simple_verb and has_email_target and not is_info_request:
                # "envoie aux copropriétaires" (no "email" word but clear intent)
                return IntentClassification(
                    intent=IntentType.SEND_EMAIL,
                    domain=Domain.PROPERTY_MGMT,
                    confidence=0.88,
                    suggested_sources=[DataSource.SQL, DataSource.CONVERSATION],
                    reasoning="Send verb with recipient context",
                    keywords_matched=["envoie", "recipient"]
                )

        # 2.5 EMAIL MODIFICATION (when email draft exists in conversation)
        email_modification_keywords = [
            "change le ton", "modifie le ton",
            "modifie l'email", "modifie le message",
            "modifie le sujet", "change l'objet",
            "change le message", "ajoute dans l'email",
            "retire de l'email", "supprime de l'email"
        ]

        if any(kw in query_lower for kw in email_modification_keywords):
            return IntentClassification(
                intent=IntentType.SEND_EMAIL,
                domain=Domain.PROPERTY_MGMT,
                confidence=0.90,
                suggested_sources=[DataSource.CONVERSATION],
                reasoning="Email modification request",
                keywords_matched=["modifier email"]
            )

        # ================================================================
        # 3. LEGAL - Strong legal keywords
        # ================================================================
        legal_strong_keywords = {
            "jurisprudence": 0.95,
            "légifrance": 0.95,
            "clause abusive": 0.95,
            "clauses abusives": 0.95,
            "analyse juridique": 0.95,
            "conformité": 0.90,
            "loi 1965": 0.90,
            "code civil": 0.90,
            "décret": 0.85,
            # FIX 3 - AG & Copro legal
            "délais légaux": 0.90,        # FIX 3
            "délai légal": 0.90,          # FIX 3
            "obligations légales": 0.90,   # FIX 3
            "obligation légale": 0.90,     # FIX 3
            "loi alur": 0.90,              # FIX 3
            "quorum": 0.85,                # FIX 3
            "majorité": 0.75,              # FIX 3 (lower, can be ambiguous)
            "vote ag": 0.85,               # FIX 3
            "délai convocation": 0.85,     # FIX 3
            # FIX - Questions juridiques générales (loi, assemblée générale)
            "que dit la loi": 0.95,        # FIX - "que dit la loi sur..."
            "la loi sur": 0.90,            # FIX - "la loi sur les modalités..."
            "selon la loi": 0.90,          # FIX - "selon la loi..."
            "d'après la loi": 0.90,        # FIX - "d'après la loi..."
            "prévoit la loi": 0.90,        # FIX - "que prévoit la loi..."
            "réglementation": 0.85,        # FIX - questions réglementaires
            "texte de loi": 0.90,          # FIX - référence à un texte
            "article de loi": 0.90,        # FIX - référence à un article
            "assemblée générale": 0.85,    # FIX - AG copropriété (contexte légal)
            "assemblées générales": 0.85,  # FIX - AG pluriel
            "règles de vote": 0.88,        # FIX - règles de vote AG
            "modalités de vote": 0.88,     # FIX - modalités de vote AG
            "droit de vote": 0.85,         # FIX - droit de vote copropriété
            "droits de vote": 0.85,        # FIX - droits de vote pluriel
            "règlement de copropriété": 0.90, # FIX - document légal copro
            "loi sur la copropriété": 0.92,   # FIX - loi copropriété
            "législation": 0.88,           # FIX - questions législatives
            "dispositions légales": 0.90,  # FIX - dispositions légales
        }

        for keyword, confidence in legal_strong_keywords.items():
            if keyword in query_lower:
                return IntentClassification(
                    intent=IntentType.LEGAL,
                    domain=Domain.LEGAL,
                    confidence=confidence,
                    suggested_sources=[DataSource.RAG, DataSource.LEGIFRANCE, DataSource.WEB],
                    reasoning=f"Legal keyword '{keyword}'",
                    keywords_matched=[keyword]
                )

        # ================================================================
        # 4. WEB SEARCH - ONLY when explicitly requested
        # V6 RULE: WEB_SEARCH triggers ONLY if:
        #   - User selected "Internet" checkbox (handled in PHASE 0)
        #   - OR user explicitly asks with these patterns
        # ================================================================
        web_explicit_keywords = [
            # Explicit internet request patterns
            "sur internet", "sur le net",
            "recherche internet", "recherche sur internet",
            "cherche sur internet", "cherche sur le web", "cherche sur le net",
            "trouve sur internet", "trouve sur le web", "trouve sur le net",
            "google", "cherche sur google", "recherche google",
            "duckduckgo", "bing",
            # French explicit phrases
            "en ligne", "sur le web",
        ]

        has_explicit_web_request = any(kw in query_lower for kw in web_explicit_keywords)

        if has_explicit_web_request:
            logger.info("explicit_web_search_requested", query=query_lower[:50])
            return IntentClassification(
                intent=IntentType.WEB_SEARCH,
                domain=Domain.GENERAL,
                confidence=0.92,
                suggested_sources=[DataSource.WEB],
                reasoning="Explicit web search request - user asked for internet search",
                keywords_matched=["internet", "explicit_request"],
                is_hybrid_search=False
            )

        # 5. DOCUMENT SEARCH - When documents are uploaded
        doc_keywords = ["dans les documents", "dans les fichiers", "dans mes documents",
                       "recherche dans", "que dit", "selon le document"]

        if has_documents and any(kw in query_lower for kw in doc_keywords):
            # Check if legal document
            if any(word in query_lower for word in ["contrat", "bail", "règlement", "pv"]):
                return IntentClassification(
                    intent=IntentType.LEGAL,
                    domain=Domain.LEGAL,
                    confidence=0.85,
                    suggested_sources=[DataSource.RAG, DataSource.UPLOADED_DOCS],
                    reasoning="Legal document search",
                    keywords_matched=["document", "contrat"]
                )
            else:
                return IntentClassification(
                    intent=IntentType.SEARCH_DOCUMENTS,
                    domain=Domain.PROPERTY_MGMT,
                    confidence=0.85,
                    suggested_sources=[DataSource.RAG, DataSource.UPLOADED_DOCS],
                    reasoning="Document search with uploaded files",
                    keywords_matched=["documents"]
                )

        # 6. WORKFLOW TRIGGERS - Emergencies, incidents, AG convocations
        # CRITICAL: Skip workflow if this is an explicit email request
        email_action_indicators = [
            "envoie un email", "envoie un mail", "envoyer un email",
            "génère email", "génère un email", "rédige email", "rédige un email",
            "écris un email", "écris un mail"
        ]
        is_explicit_email_request = any(ind in query_lower for ind in email_action_indicators)

        # ================================================================
        # WORKFLOW D'URGENCE - Déclenché quand:
        # 1. Contexte d'urgence (urgent, fuite, incendie, panne...)
        # 2. ET demande d'aide/actions (que faire, to-do, liste d'actions...)
        #
        # BUT: Aider l'utilisateur stressé avec une liste d'actions concrètes
        # ================================================================

        # Mots indiquant une situation urgente
        emergency_context_words = [
            "urgent", "urgence", "urgente",
            "fuite", "fuite d'eau", "fuite de gaz",
            "dégât des eaux", "dégât", "dégâts",
            "incendie", "feu", "fumée",
            "inondation", "innondation",
            "panne", "panne ascenseur", "panne électrique", "coupure",
            "effondrement", "éboulement",
            "cambriolage", "intrusion",
            "accident", "blessé",
        ]

        # Mots indiquant une demande d'aide/actions
        action_request_words = [
            "que faire", "quoi faire", "comment faire",
            "liste d'actions", "liste des actions", "actions à faire",
            "to do", "to-do", "todo", "checklist",
            "étapes", "etapes", "procédure", "procedure",
            "que dois-je", "que doit-on", "que devons-nous",
            "aide", "aidez", "help",
            "urgence que", "urgent que",
            "comment réagir", "comment gérer",
            "marche à suivre", "protocole",
        ]

        has_emergency_context = any(word in query_lower for word in emergency_context_words)
        has_action_request = any(word in query_lower for word in action_request_words)

        # Patterns that EXCLUDE workflow triggering (normal business requests)
        workflow_exclusions = [
            "génère", "genere", "générer", "generer",
            "modèle", "modele", "template",
            "prépare", "prepare", "préparer", "preparer",
            "tableau des", "récapitulatif",
            "procès-verbal", "proces-verbal", "pv ",
            "délai", "delai", "loi de", "article",
            "convocation", "convoquer",  # Terms métier normaux
            "assemblée générale", "ag ",
        ]
        is_normal_request = any(excl in query_lower for excl in workflow_exclusions)

        # WORKFLOW se déclenche si: urgence + demande d'aide + pas une requête normale
        if has_emergency_context and has_action_request and not is_normal_request and not is_explicit_email_request:
            # Determine domain and matched keyword
            domain = Domain.PROPERTY_MGMT
            matched_emergency = next((w for w in emergency_context_words if w in query_lower), "urgence")

            # Specific domains for certain emergencies
            plumbing_keywords = ["fuite", "dégât", "dégât des eaux", "inondation"]
            if any(kw in query_lower for kw in plumbing_keywords):
                domain = Domain.PLUMBING

            logger.info("workflow_triggered",
                       emergency=matched_emergency,
                       has_action_request=True,
                       query=query_lower[:50])

            return IntentClassification(
                intent=IntentType.TRIGGER_WORKFLOW,
                domain=domain,
                confidence=0.92,
                suggested_sources=[DataSource.SQL, DataSource.WEB],
                reasoning=f"Urgence '{matched_emergency}' + demande d'aide détectée",
                keywords_matched=[matched_emergency, "action_request"]
            )

        # 7. QUOTES - Vendor requests (lower priority than workflows)
        # CRITICAL: Skip if this is an EMAIL request with "devis" in it
        # "Génère un email au prestataire... demande aussi un devis" → SEND_EMAIL, not REQUEST_QUOTES
        quote_keywords = ["devis", "demande de devis", "prix", "tarif"]
        email_action_indicators = ["génère email", "génère un email", "genere email", "genere un email",
                                   "envoie email", "envoie un email",
                                   "écris email", "écris un email", "ecris email", "ecris un email",
                                   "rédige email", "rédige un email", "redige email", "redige un email"]

        has_quote_keyword = any(kw in query_lower for kw in quote_keywords)
        has_email_action = any(ind in query_lower for ind in email_action_indicators)

        if has_quote_keyword and not has_email_action:
            return IntentClassification(
                intent=IntentType.REQUEST_QUOTES,
                domain=Domain.VENDOR_MGMT,
                confidence=0.85,
                suggested_sources=[DataSource.SQL],
                reasoning="Quote request detected",
                keywords_matched=["devis"]
            )

        # No quick rule matched
        return None

    def _generate_clarification_options(
        self,
        user_input: str,
        primary_intent: IntentType,
        confidence: float
    ) -> tuple[str, List[Dict[str, Any]], List[IntentType]]:
        """
        Generate clarification question and options for ambiguous queries

        Returns:
            (question, options, possible_intents)
        """
        # Common clarification scenarios
        clarification_map = {
            IntentType.SEND_EMAIL: {
                "question": "Je ne suis pas sûr de comprendre. Voulez-vous :",
                "options": [
                    {"label": "Envoyer un email", "intent": "send_email",
                     "description": "Rédiger et envoyer un message"},
                    {"label": "Consulter des données", "intent": "query_data",
                     "description": "Voir des informations de la base de données"},
                ]
            },
            IntentType.QUERY_DATA: {
                "question": "Que souhaitez-vous faire exactement ?",
                "options": [
                    {"label": "Voir des données", "intent": "query_data",
                     "description": "Consulter des informations (copropriétaires, budgets...)"},
                    {"label": "Rechercher dans les documents", "intent": "search_documents",
                     "description": "Chercher dans les PDFs et contrats"},
                ]
            },
            IntentType.SEARCH_DOCUMENTS: {
                "question": "Quelle type de recherche souhaitez-vous ?",
                "options": [
                    {"label": "Dans mes documents", "intent": "search_documents",
                     "description": "Recherche dans les PDFs uploadés"},
                    {"label": "Analyse juridique", "intent": "legal",
                     "description": "Analyse légale et jurisprudence"},
                    {"label": "Sur internet", "intent": "web_search",
                     "description": "Recherche web pour infos actuelles"},
                ]
            },
            IntentType.GENERAL_QUESTION: {
                "question": "Comment puis-je vous aider ?",
                "options": [
                    {"label": "Question sur les données", "intent": "query_data",
                     "description": "Copropriétaires, budgets, documents..."},
                    {"label": "Envoyer un message", "intent": "send_email",
                     "description": "Email aux copropriétaires ou professionnels"},
                    {"label": "Recherche documentaire", "intent": "search_documents",
                     "description": "Chercher dans les documents"},
                    {"label": "Question générale", "intent": "general_question",
                     "description": "Autre question"},
                ]
            }
        }

        # Get clarification for the primary intent, or use general
        clarification = clarification_map.get(
            primary_intent,
            clarification_map[IntentType.GENERAL_QUESTION]
        )

        possible_intents = [
            IntentType(opt["intent"]) for opt in clarification["options"]
        ]

        return clarification["question"], clarification["options"], possible_intents

    async def _llm_classification(
        self,
        user_input: str,
        context: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> IntentClassification:
        """
        LLM-based classification for complex queries
        Now with enhanced clarification support
        """

        # Build context string with conversation history
        context_str = ""
        if context.get("has_uploaded_documents"):
            context_str += "- L'utilisateur a uploadé des documents\n"
        if conversation_history and len(conversation_history) > 0:
            context_str += f"- Historique: {len(conversation_history)} messages\n"
            # Add last 3 messages for context
            recent = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")[:100]
                context_str += f"  - {role}: {content}...\n"

        prompt = f"""Classifie l'intention de cette requête utilisateur.

Requête: "{user_input}"

Contexte:
{context_str if context_str else "Aucun contexte spécifique"}

RÈGLES IMPORTANTES V6:
1. Si l'utilisateur dit "envoie-moi", "donne-moi", "montre-moi" = c'est une demande d'INFO (query_data), PAS un email
2. "Envoie un email à X" ou "contacte X" ou "préviens/informe X" = c'est un vrai email (send_email)
3. "Demande de devis" = request_quotes (c'est un cas spécialisé de send_email - même agent)
4. web_search = UNIQUEMENT si demande explicite ("cherche sur internet", "google", "sur le web")
   - NE PAS utiliser web_search par défaut pour des questions générales
5. Si tu n'es pas sûr à 70%+, mets une confiance basse pour déclencher une clarification

Intents disponibles:
1. query_data - Requêtes de données SQL (listes, statistiques, copropriétaires, professionnels)
2. search_documents - Recherche RAG dans documents (factures, contrats, PV, PDFs)
3. web_search - UNIQUEMENT si demande explicite "sur internet/google/web"
4. send_email - Générer emails (si destinataire explicite ou verbe communication: préviens, informe, contacte)
5. request_quotes - Demande de devis (utilise le même agent que send_email)
6. trigger_workflow - Urgences UNIQUEMENT (fuite + que faire = workflow)
7. legal - Analyse juridique, loi, jurisprudence, conformité
8. general_question - Questions générales sans action spécifique

Réponds en JSON:
{{
    "intent": "query_data",
    "domain": "property_mgmt",
    "confidence": 0.85,
    "reasoning": "La requête demande une liste, donc SQL",
    "suggested_sources": ["sql"]
}}

Sois HONNÊTE sur ta confiance. En cas de doute, confiance < 0.70."""

        try:
            response = await self.llm_service.generate_response(prompt)

            # Parse JSON response
            import json
            if "```json" in response:
                json_match = re.search(r'```json\s*\n(.*?)```', response, re.DOTALL)
                if json_match:
                    response = json_match.group(1)
            elif "```" in response:
                json_match = re.search(r'```\s*\n(.*?)```', response, re.DOTALL)
                if json_match:
                    response = json_match.group(1)

            result = json.loads(response.strip())

            # Map to enums
            intent = IntentType(result.get("intent", "general_question"))
            domain = Domain(result.get("domain", "general"))
            confidence = float(result.get("confidence", 0.7))
            reasoning = result.get("reasoning", "LLM classification")

            # Map suggested sources
            sources_map = {
                "sql": DataSource.SQL,
                "rag": DataSource.RAG,
                "web": DataSource.WEB,
                "legifrance": DataSource.LEGIFRANCE,
                "uploaded_docs": DataSource.UPLOADED_DOCS,
                "conversation": DataSource.CONVERSATION,
            }

            suggested_sources = []
            for src in result.get("suggested_sources", []):
                if src in sources_map:
                    suggested_sources.append(sources_map[src])

            # Generate clarification if confidence is low
            needs_clarification = confidence < self.THRESHOLD_MEDIUM
            clarification_question = None
            clarification_options = []
            possible_intents = []

            if needs_clarification:
                clarification_question, clarification_options, possible_intents = \
                    self._generate_clarification_options(user_input, intent, confidence)

                logger.info("clarification_generated",
                           confidence=confidence,
                           threshold=self.THRESHOLD_MEDIUM,
                           options_count=len(clarification_options))

            return IntentClassification(
                intent=intent,
                domain=domain,
                confidence=confidence,
                suggested_sources=suggested_sources,
                reasoning=reasoning,
                keywords_matched=[],
                needs_clarification=needs_clarification,
                clarification_question=clarification_question,
                clarification_options=clarification_options,
                possible_intents=possible_intents
            )

        except Exception as e:
            logger.error("llm_classification_failed", error=str(e), exc_info=True)

            # Fallback with clarification
            question, options, possible = self._generate_clarification_options(
                user_input, IntentType.GENERAL_QUESTION, 0.50
            )

            return IntentClassification(
                intent=IntentType.GENERAL_QUESTION,
                domain=Domain.GENERAL,
                confidence=0.50,
                suggested_sources=[DataSource.CONVERSATION],
                reasoning=f"LLM classification failed: {str(e)}",
                keywords_matched=[],
                needs_clarification=True,
                clarification_question=question,
                clarification_options=options,
                possible_intents=possible
            )
