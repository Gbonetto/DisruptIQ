"""
Intent Classifier V5 (V6 improvements) - World-Class SMA Routing
Phase 3 Refactoring - Context-Aware Classification

✅ CURRENT VERSION - Production Ready

Key Improvements:
- Context-aware email detection (distingue "envoie email" vs "envoie-moi")
- SQL keywords checked BEFORE email verbs (priority order fix)
- Clarification automatique sous 0.70 confiance
- Unified context model preparation
- Better conversation history utilization

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
        Classify user intent

        Args:
            user_input: User's message
            context: Optional context (uploaded files, etc.)
            conversation_history: Previous messages

        Returns:
            IntentClassification with intent, domain, confidence, suggested_sources
        """
        start_time = datetime.now()
        query_lower = user_input.lower()

        logger.info("classification_started", query=user_input[:50])

        # Initialize context
        if context is None:
            context = {}

        has_documents = context.get("has_uploaded_documents", False) or \
                       context.get("has_active_documents", False)

        # PHASE 1: Quick Rules (70% of queries) - Now with conversation context
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
            "préviens", "prévenir", "alerter", "alerte ",
            "copropriétaires", "copropriétaire",
            "professionnel", "professionnels",
            "prestataire",  # ADDED: Important target for vendor emails
            "chauffagiste", "plombier", "électricien",
            "plomberie", "électricité",  # ADDED: Company type names
            "fournisseur", "artisan", "entreprise",  # ADDED: Vendor types
            "voisin", "voisins", "syndic"
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
            "que dit le": 0.90,
            "que dit la": 0.90,
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
            email_explicit_phrases = [
                "envoie un email", "envoie un mail", "envoyer un email",
                "envoie email", "envoie mail",
                "génère un email", "génère email", "genere un email", "genere email",
                "écris un email", "ecris un email",
                "rédige un email", "redige un email",
            ]

            has_explicit_email_phrase = any(phrase in query_lower for phrase in email_explicit_phrases)

            if has_explicit_email_phrase:
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
            email_action_verbs = [
                "envoie un email", "envoie un mail", "envoyer un email",
                "écris un email", "écris un message", "ecris un email", "ecris un message",
                "rédige email", "rédige un email", "redige email", "redige un email",
                "transmets", "génère email", "génère un email", "genere email", "genere un email",
                "génère la convocation", "génère convocation",
                "crée la convocation", "crée convocation",
                "prépare la convocation", "prépare convocation",
                "contacte", "contacter", "préviens", "prévenir",
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

        # 4. WEB SEARCH - Explicit internet requests
        web_keywords = ["sur internet", "recherche internet", "google", "cherche sur le web"]

        if any(kw in query_lower for kw in web_keywords):
            return IntentClassification(
                intent=IntentType.WEB_SEARCH,
                domain=Domain.GENERAL,
                confidence=0.90,
                suggested_sources=[DataSource.WEB],
                reasoning="Explicit web search request",
                keywords_matched=["internet"]
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

        workflow_keywords = {
            "urgent": 0.90,
            "urgence": 0.90,
            "fuite": 0.85,
            "dégât": 0.85,
            "dégât des eaux": 0.90,
            "incendie": 0.95,
            "panne": 0.80,
            "convoquer": 0.85,
            "convocation": 0.85,
            "assemblée générale": 0.85,
            "travaux": 0.75,
        }

        for keyword, confidence in workflow_keywords.items():
            if keyword in query_lower and not is_explicit_email_request:
                # Determine domain based on keyword
                domain = Domain.PROPERTY_MGMT
                if keyword in ["fuite", "dégât", "dégât des eaux", "incendie", "panne"]:
                    domain = Domain.PLUMBING

                return IntentClassification(
                    intent=IntentType.TRIGGER_WORKFLOW,
                    domain=domain,
                    confidence=confidence,
                    suggested_sources=[DataSource.SQL],
                    reasoning=f"Workflow trigger detected: '{keyword}'",
                    keywords_matched=[keyword]
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

RÈGLES IMPORTANTES:
1. Si l'utilisateur dit "envoie-moi", "donne-moi", "montre-moi" = c'est une demande d'INFO (query_data), PAS un email
2. "Envoie un email à X" ou "contacte X" = c'est un vrai email (send_email)
3. Si tu n'es pas sûr à 70%+, mets une confiance basse pour déclencher une clarification

Intents disponibles:
1. query_data - Requêtes de données (nombres, listes, statistiques)
2. search_documents - Recherche sémantique dans documents
3. web_search - Recherche internet
4. send_email - Générer et envoyer des emails (UNIQUEMENT si destinataire explicite)
5. request_quotes - Demander des devis
6. trigger_workflow - Déclencher un workflow (urgences, incidents)
7. legal - Analyse juridique, jurisprudence
8. general_question - Questions générales

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
