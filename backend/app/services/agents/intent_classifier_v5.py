"""
Intent Classifier V5 - Clean & Simplified
Phase 2 Refactoring - Uses centralized intent system

Key Improvements:
- Uses app.models.intent directly (no duplicate enums)
- Simplified logic (70% Quick Rules + 30% LLM)
- Returns IntentClassification model directly
- No DataSource.AMBIGUOUS complexity
- Clean error handling

Author: Claude Code - Phase 2 Refactoring
Date: November 22, 2025
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
    Simplified intent classifier using centralized intent system

    Philosophy:
    - Quick rules catch 70% of queries
    - LLM handles remaining 30%
    - Returns IntentClassification model directly
    - Agents have full autonomy over data sources
    """

    def __init__(self):
        self.llm_service = LLMService()

        # Confidence thresholds
        self.THRESHOLD_HIGH = 0.85
        self.THRESHOLD_MEDIUM = 0.70
        self.THRESHOLD_LOW = 0.50

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

        # PHASE 1: Quick Rules (70% of queries)
        quick_result = await self._quick_rules_classification(query_lower, has_documents)

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

    async def _quick_rules_classification(
        self,
        query_lower: str,
        has_documents: bool
    ) -> Optional[IntentClassification]:
        """
        Quick rule-based classification (70% accuracy target)

        Priority order:
        1. Email actions (highest confidence)
        2. SQL queries (aggregations, lists)
        3. Legal keywords
        4. Web search (explicit internet requests)
        5. Document search (when documents exist)
        """

        # 1. EMAIL - High priority (explicit action verbs)
        email_verbs = ["envoie", "envoyer", "envoi", "contacte", "contacter",
                      "écris un email", "écris un message", "transmets"]

        if any(verb in query_lower for verb in email_verbs):
            return IntentClassification(
                intent=IntentType.SEND_EMAIL,
                domain=Domain.PROPERTY_MGMT,
                confidence=0.90,
                suggested_sources=[DataSource.SQL, DataSource.CONVERSATION],
                reasoning="Email action verb detected",
                keywords_matched=["email", "envoie"]
            )

        # 2. SQL QUERIES - Aggregations & Lists
        sql_strong_keywords = {
            "combien": 0.95,
            "nombre de": 0.95,
            "liste des": 0.85,
            "liste-moi": 0.90,
            "tous les": 0.80,
            "moyenne": 0.95,
            "total": 0.85,
        }

        for keyword, confidence in sql_strong_keywords.items():
            if keyword in query_lower:
                # Additional context: copropriétaires, professionnels, documents
                if any(word in query_lower for word in ["copropriétaire", "copropriété", "professionnel", "syndic"]):
                    return IntentClassification(
                        intent=IntentType.QUERY_DATA,
                        domain=Domain.PROPERTY_MGMT,
                        confidence=confidence,
                        suggested_sources=[DataSource.SQL],
                        reasoning=f"SQL keyword '{keyword}' + database entity",
                        keywords_matched=[keyword]
                    )

        # 3. LEGAL - Strong legal keywords
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

        # 6. QUOTES - Vendor requests
        quote_keywords = ["devis", "demande de devis", "prix", "tarif"]

        if any(kw in query_lower for kw in quote_keywords):
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

    async def _llm_classification(
        self,
        user_input: str,
        context: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, str]]]
    ) -> IntentClassification:
        """
        LLM-based classification for complex queries
        """

        # Build context string
        context_str = ""
        if context.get("has_uploaded_documents"):
            context_str += "- L'utilisateur a uploadé des documents\n"
        if conversation_history and len(conversation_history) > 0:
            context_str += f"- Historique: {len(conversation_history)} messages\n"

        prompt = f"""Classifie l'intention de cette requête utilisateur.

Requête: "{user_input}"

Contexte:
{context_str if context_str else "Aucun contexte spécifique"}

Intents disponibles:
1. query_data - Requêtes SQL (nombres, listes, statistiques sur copropriétaires/professionnels)
2. search_documents - Recherche sémantique dans documents (contrats, règlements, PDFs)
3. web_search - Recherche internet (infos actuelles, news)
4. send_email - Générer et envoyer des emails
5. request_quotes - Demander des devis
6. trigger_workflow - Déclencher un workflow N8N
7. legal - Analyse juridique, jurisprudence, clauses abusives
8. general_question - Questions générales d'assistant

Domaines:
- legal: Juridique, lois, contrats
- plumbing: Plomberie, eau, chauffage
- property_mgmt: Gestion copropriété
- vendor_mgmt: Fournisseurs, devis
- general: Questions générales

Réponds en JSON:
{{
    "intent": "query_data",
    "domain": "property_mgmt",
    "confidence": 0.85,
    "reasoning": "La requête demande une liste, donc SQL",
    "suggested_sources": ["sql"]
}}

Sois précis et justifie ton raisonnement."""

        try:
            response = await self.llm_service.generate_response(prompt)

            # Parse JSON response
            import json
            # Extract JSON from markdown if needed
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

            return IntentClassification(
                intent=intent,
                domain=domain,
                confidence=confidence,
                suggested_sources=suggested_sources,
                reasoning=reasoning,
                keywords_matched=[],
                needs_clarification=confidence < self.THRESHOLD_MEDIUM
            )

        except Exception as e:
            logger.error("llm_classification_failed", error=str(e), exc_info=True)

            # Fallback to general question
            return IntentClassification(
                intent=IntentType.GENERAL_QUESTION,
                domain=Domain.GENERAL,
                confidence=0.50,
                suggested_sources=[DataSource.CONVERSATION],
                reasoning=f"LLM classification failed: {str(e)}",
                keywords_matched=[],
                needs_clarification=True
            )
