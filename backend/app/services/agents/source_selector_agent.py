"""
Source Selector Agent V2 - Smart Multi-Source Routing

Architecture:
1. Quick Rules (0ms) - Pattern matching for bypass flows (email, chat)
2. Pre-activation hints - Boost confidence for relevant sources
3. LLM Source Selector - Proposes 1-2 source candidates with scores
4. UI context as signal (not absolute) - Documents cochés = boost RAG, pas force

Key principle: Sources are CANDIDATES, not binary choices.
The orchestrator will query multiple sources and let synthesis decide.
"""

import structlog
import re
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

from app.services.llm_service import LLMService
from app.core.config import settings

logger = structlog.get_logger()


class SourceType(str, Enum):
    """Available data sources"""
    SQL = "sql"
    RAG = "rag"
    LEGAL = "legal"
    WEB = "web"


class BypassType(str, Enum):
    """Special bypass flows (skip source selection)"""
    EMAIL_FLOW = "email_flow"
    EMAIL_MODIFY = "email_modify"
    EMAIL_CONFIRM = "email_confirm"
    EMAIL_CANCEL = "email_cancel"
    CHAT = "chat"
    NONE = "none"


@dataclass
class SourceDecision:
    """Decision for a single source"""
    needed: bool
    confidence: float
    reason: str = ""
    pre_activated: bool = False
    ui_boosted: bool = False  # NEW: boosted by UI context (documents selected)


@dataclass
class SourceSelectionResult:
    """Complete source selection result"""
    sources: Dict[str, SourceDecision] = field(default_factory=dict)
    bypass: BypassType = BypassType.NONE
    bypass_reason: str = ""
    quick_rules_applied: List[str] = field(default_factory=list)

    def get_needed_sources(self) -> List[str]:
        """Get list of sources that should be queried, ordered by confidence"""
        needed = [(name, decision) for name, decision in self.sources.items() if decision.needed]
        # Sort by confidence descending
        needed.sort(key=lambda x: x[1].confidence, reverse=True)
        return [name for name, _ in needed]

    def get_top_sources(self, max_sources: int = 2) -> List[str]:
        """Get top N sources by confidence (for parallel query)"""
        return self.get_needed_sources()[:max_sources]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sources": {
                name: {
                    "needed": dec.needed,
                    "confidence": dec.confidence,
                    "reason": dec.reason,
                    "pre_activated": dec.pre_activated,
                    "ui_boosted": dec.ui_boosted
                }
                for name, dec in self.sources.items()
            },
            "bypass": self.bypass.value,
            "bypass_reason": self.bypass_reason,
            "quick_rules_applied": self.quick_rules_applied,
            "needed_sources": self.get_needed_sources()
        }


class SourceSelectorAgent:
    """
    Intelligent source selector V2 - Multi-source with soft routing

    Key changes from V1:
    - UI context (documents selected) = boost signal, not absolute force
    - Always returns 1-2 sources for parallel query
    - LLM proposes candidates with confidence scores
    - Orchestrator queries multiple and synthesis decides
    """

    # === BYPASS PATTERNS (Email, Chat) ===
    EMAIL_PATTERNS = [
        r'\b(envoie|envoi|envoyer|rédige|rédiger|écris|écrire)\b.*\b(email|mail|message|courrier)\b',
        r'\b(email|mail)\b.*\b(à|pour|aux)\b',
    ]

    CHAT_PATTERNS = [
        r'^(bonjour|salut|hello|hi|hey|coucou|bonsoir)[\s,!.?]*$',
        r'^(merci|thanks|au revoir|bye|à bientôt)[\s,!.?]*$',
        r'^(ok|d\'accord|compris|parfait|super|génial)[\s,!.?]*$',
    ]

    # === PRE-ACTIVATION PATTERNS (boost confidence, don't force) ===
    SQL_HINT_PATTERNS = [
        # Termes techniques DB
        r'\b(table|base de données|bdd|sql)\b',
        # Comptage et listes
        r'\b(combien|nombre|count|total)\b.*\b(copropriétaire|lot|professionnel|facture)\b',
        r'\b(liste|lister|donne|trouve)\b.*\b(copropriétaire|lot|professionnel|artisan|prestataire)\b',
        # Recherche de coordonnées
        r'\b(copropriétaire|professionnel|électricien|plombier|artisan|prestataire)\b.*\b(coordonnées|contact|email|téléphone|adresse)\b',
        r'\b(email|téléphone|coordonnées)\s+(de|du|des)\b',
        r'\bcontact(er)?\s+(le|la|un|une)\s+(plombier|électricien|professionnel|artisan)\b',
        # Questions existentielles
        r'\bavons[- ]nous\b.*\b(plombier|électricien|professionnel|artisan)\b',
        r'\bqui est\b.*\b(copropriétaire|professionnel)\b',
        r'\b(existe|référencé|enregistré)\b.*\b(base|données)\b',
        # Notre base / nos données
        r'\b(notre|nos)\s+(base|données|liste)\b',
        r'\bdans\s+(la|notre)\s+base\b',
    ]

    RAG_HINT_PATTERNS = [
        r'\b(document|pdf|fichier|contrat|règlement|pv|procès-verbal)\b',
        r'\bque dit\b.*\b(document|contrat|règlement)\b',
        r'\bdans (le|les|mon|mes|notre|nos)\b.*\b(document|fichier)\b',
        r'\b(résume|résumer|synthèse|analyser|analyse)\b.*\b(document|fichier|facture)\b',
        r'\b(sélectionné|coché|choisi)\b',
    ]

    LEGAL_HINT_PATTERNS = [
        # Articles de loi explicites
        r'\b(loi|article|art\.?)\s*\d+',
        r'\b(loi|décret)\s*(de|du)?\s*\d{4}\b',
        # Lois connues copropriété
        r'\b(alur|elan|hoguet|carrez)\b',
        # Termes juridiques généraux
        r'\b(juridique|légal|légale|légalement|réglementaire|réglementation)\b',
        r'\b(obligation|obligatoire|obligatoirement)\s*(légale|du syndic)?\b',
        # Majorités (plus flexible)
        r'\b(majorité|majorités)\b.*\b(vote|voter|requise|nécessaire|faut)\b',
        r'\bquelle\s+majorité\b',
        r'\bmajorité\s+(simple|absolue|double|qualifiée)\b',
        # Délais légaux
        r'\b(délai|délais)\s*(légal|légaux|de convocation|de contestation)\b',
        r'\bdélai\s+pour\b',
        # Copropriété spécifique
        r'\b(syndic|copropriété)\b.*\b(obligation|droit|loi|légal)\b',
        r'\b(assemblée générale|ag)\b.*\b(convocation|délai|vote)\b',
        # Questions "que dit la loi"
        r'\bque\s+(dit|prévoit|impose)\s+(la\s+)?(loi|le\s+décret)\b',
    ]

    WEB_HINT_PATTERNS = [
        r'\b(prix|tarif|coût)\s*(du|de la|actuel|marché|m²)\b',
        r'\b(aujourd\'hui|actuellement|récemment)\b',
        r'\b(actualité|news|dernière)\b',
        r'\b(indice|taux|inflation)\b',
    ]

    # Thresholds
    MIN_CONFIDENCE = 0.4  # Below this, source is not queried
    HIGH_CONFIDENCE = 0.8  # Above this, source is definitely queried

    def __init__(self):
        self.llm_service = LLMService()

        # Compile patterns
        self._email_re = [re.compile(p, re.IGNORECASE) for p in self.EMAIL_PATTERNS]
        self._chat_re = [re.compile(p, re.IGNORECASE) for p in self.CHAT_PATTERNS]
        self._sql_hint_re = [re.compile(p, re.IGNORECASE) for p in self.SQL_HINT_PATTERNS]
        self._rag_hint_re = [re.compile(p, re.IGNORECASE) for p in self.RAG_HINT_PATTERNS]
        self._legal_hint_re = [re.compile(p, re.IGNORECASE) for p in self.LEGAL_HINT_PATTERNS]
        self._web_hint_re = [re.compile(p, re.IGNORECASE) for p in self.WEB_HINT_PATTERNS]

        logger.info("source_selector_v2_initialized")

    async def select_sources(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> SourceSelectionResult:
        """
        Select sources to query - returns 1-2 candidates with confidence scores.

        Architecture:
        1. Check bypass flows (email, chat)
        2. Apply pre-activation hints (regex patterns)
        3. Apply UI context boost (documents selected)
        4. LLM refines selection with semantic understanding
        5. Return top 1-2 sources for parallel query
        """
        context = context or {}
        result = SourceSelectionResult()

        # Initialize all sources with base confidence
        for source in SourceType:
            result.sources[source.value] = SourceDecision(
                needed=False,
                confidence=0.3,  # Base confidence
                reason="Default"
            )

        # === STEP 1: Bypass flows ===
        bypass = self._check_bypass_rules(query, context, result)
        if bypass != BypassType.NONE:
            result.bypass = bypass
            logger.info("source_selector_bypass", bypass=bypass.value)
            return result

        # === STEP 2: Pre-activation hints (boost, don't force) ===
        self._apply_preactivation_hints(query, result)

        # === STEP 3: UI Context boost (documents selected = boost RAG) ===
        self._apply_ui_context_boost(context, result)

        # === STEP 4: LLM Selection (refine with semantic understanding) ===
        await self._llm_select_sources(query, context, result)

        # === STEP 5: Finalize - ensure at least 1 source, max 2 for efficiency ===
        self._finalize_selection(result)

        logger.info("source_selector_v2_result",
                   sources=result.get_needed_sources(),
                   top_sources=result.get_top_sources(2),
                   rules=result.quick_rules_applied)

        return result

    def _check_bypass_rules(
        self,
        query: str,
        context: Dict[str, Any],
        result: SourceSelectionResult
    ) -> BypassType:
        """Check for bypass flows (email, chat)"""
        query_lower = query.lower().strip()

        # Email draft active - check email actions
        if context.get("email_draft") or context.get("awaiting_email_confirmation"):
            cancel_words = ['annuler', 'annule', 'non', 'stop', 'arrête', 'abandonne']
            if any(w in query_lower for w in cancel_words):
                result.quick_rules_applied.append("email_cancel")
                return BypassType.EMAIL_CANCEL

            confirm_words = ['envoyer', 'envoie', 'confirme', 'oui', 'ok', 'valide', 'go']
            modify_words = ['modif', 'chang', 'ajoute', 'enlève', 'corrige']

            if len(query_lower) < 50 and any(w in query_lower for w in confirm_words):
                if not any(w in query_lower for w in modify_words):
                    result.quick_rules_applied.append("email_confirm")
                    return BypassType.EMAIL_CONFIRM

            # Check if this really looks like a modification request
            # Must either contain modification words OR look like a short instruction (<100 chars)
            # AND not look like a new query (questions about factures, documents, etc.)
            new_query_keywords = ['facture', 'document', 'résume', 'tableau', 'liste', 'combien', 'quel', 'quelle', 'qui est', 'montre']
            is_new_query = any(kw in query_lower for kw in new_query_keywords)

            if not is_new_query and (any(w in query_lower for w in modify_words) or (len(query_lower) > 15 and len(query_lower) < 150)):
                result.quick_rules_applied.append("email_modify")
                return BypassType.EMAIL_MODIFY

        # New email flow
        for pattern in self._email_re:
            if pattern.search(query):
                result.quick_rules_applied.append("email_flow")
                return BypassType.EMAIL_FLOW

        # Chat/greeting
        for pattern in self._chat_re:
            if pattern.search(query):
                result.quick_rules_applied.append("chat")
                return BypassType.CHAT

        return BypassType.NONE

    def _apply_preactivation_hints(self, query: str, result: SourceSelectionResult) -> None:
        """Apply pattern-based boosts to source confidence (accumulative)"""

        # SQL hints: +0.15 per match, max 0.45
        sql_matches = 0
        for pattern in self._sql_hint_re:
            if pattern.search(query):
                sql_matches += 1
        if sql_matches > 0:
            boost = min(0.45, sql_matches * 0.15)
            result.sources["sql"].confidence += boost
            result.sources["sql"].pre_activated = True
            result.quick_rules_applied.append(f"sql_hint:{sql_matches}")

        # RAG hints: +0.15 per match, max 0.45
        rag_matches = 0
        for pattern in self._rag_hint_re:
            if pattern.search(query):
                rag_matches += 1
        if rag_matches > 0:
            boost = min(0.45, rag_matches * 0.15)
            result.sources["rag"].confidence += boost
            result.sources["rag"].pre_activated = True
            result.quick_rules_applied.append(f"rag_hint:{rag_matches}")

        # Legal hints: +0.25 per match, max 0.6 (strong boost for legal)
        legal_matches = 0
        for pattern in self._legal_hint_re:
            if pattern.search(query):
                legal_matches += 1
        if legal_matches > 0:
            boost = min(0.6, legal_matches * 0.25)
            result.sources["legal"].confidence += boost
            result.sources["legal"].pre_activated = True
            result.quick_rules_applied.append(f"legal_hint:{legal_matches}")

        # Web hints: +0.2 per match, max 0.5
        web_matches = 0
        for pattern in self._web_hint_re:
            if pattern.search(query):
                web_matches += 1
        if web_matches > 0:
            boost = min(0.5, web_matches * 0.2)
            result.sources["web"].confidence += boost
            result.sources["web"].pre_activated = True
            result.quick_rules_applied.append(f"web_hint:{web_matches}")

    def _apply_ui_context_boost(self, context: Dict[str, Any], result: SourceSelectionResult) -> None:
        """
        Apply UI context as a BOOST signal, not absolute force.

        If documents are selected: +0.4 to RAG (strong signal, but not 100%)
        This allows SQL to still be considered if query clearly needs it.
        """
        active_doc_ids = context.get("active_document_ids", [])

        if active_doc_ids and len(active_doc_ids) > 0:
            # Boost RAG significantly
            boost = min(0.4, 0.1 * len(active_doc_ids))  # More docs = stronger boost, max 0.4
            result.sources["rag"].confidence += boost
            result.sources["rag"].ui_boosted = True
            result.sources["rag"].reason = f"{len(active_doc_ids)} documents sélectionnés"
            result.quick_rules_applied.append(f"ui_docs_boost:{len(active_doc_ids)}")

            logger.info("ui_context_boost_applied",
                       doc_count=len(active_doc_ids),
                       rag_confidence=result.sources["rag"].confidence)

    async def _llm_select_sources(
        self,
        query: str,
        context: Dict[str, Any],
        result: SourceSelectionResult
    ) -> None:
        """LLM-based source selection - refines confidence scores"""

        # Build context summary
        context_parts = []
        if context.get("active_document_ids"):
            context_parts.append(f"- {len(context['active_document_ids'])} documents sélectionnés par l'utilisateur")
        if result.sources["sql"].pre_activated:
            context_parts.append("- Indice SQL détecté (données structurées)")
        if result.sources["rag"].pre_activated:
            context_parts.append("- Indice RAG détecté (documents)")
        if result.sources["legal"].pre_activated:
            context_parts.append("- Indice juridique détecté")

        context_str = "\n".join(context_parts) if context_parts else "Aucun contexte particulier"

        prompt = f"""Tu es un routeur pour un assistant de syndic. Analyse la question et décide quelles sources consulter.

SOURCES:
1. SQL: Base structurée (copropriétaires, lots, professionnels avec emails/téléphones, copropriétés)
2. RAG: Documents uploadés (PDF, factures, contrats, PV). Si des documents sont sélectionnés, privilégie RAG.
3. LEGAL: Légifrance (lois copropriété). Coûteux - seulement si question juridique claire.
4. WEB: Internet. Coûteux - seulement si besoin d'info externe/actuelle.

CONTEXTE:
{context_str}

QUESTION: "{query}"

RÈGLES:
- Propose 1 à 2 sources maximum
- Si documents sélectionnés + question sur leur contenu → RAG prioritaire
- Si question sur coordonnées/listes de personnes → SQL
- Si question juridique explicite (loi, majorité, délai légal, obligations) → LEGAL avec score élevé
- Évite WEB sauf si vraiment nécessaire (prix actuel, actualités)

Réponds UNIQUEMENT en JSON avec des scores entre 0.0 et 1.0:
{{"sql": 0.0, "rag": 0.0, "legal": 0.0, "web": 0.0}}"""

        try:
            response = await self.llm_service.generate_response(
                prompt, max_tokens=150, temperature=0.1
            )

            import json
            response_clean = response.strip()
            if "```" in response_clean:
                response_clean = response_clean.split("```")[1]
                if response_clean.startswith("json"):
                    response_clean = response_clean[4:]
            response_clean = response_clean.strip()

            data = json.loads(response_clean)

            # Update confidence scores (add LLM score to existing)
            for source_name in ["sql", "rag", "legal", "web"]:
                if source_name in data:
                    source_data = data[source_name]
                    # Handle both {"source": {"score": 0.8}} and {"source": 0.8}
                    if isinstance(source_data, (int, float)):
                        llm_score = float(source_data)
                    elif isinstance(source_data, dict):
                        llm_score = float(source_data.get("score", 0))
                    else:
                        llm_score = 0
                    # Combine: existing confidence + LLM score * 0.5
                    result.sources[source_name].confidence += llm_score * 0.5

            logger.info("llm_source_scores",
                       sql=result.sources["sql"].confidence,
                       rag=result.sources["rag"].confidence,
                       legal=result.sources["legal"].confidence,
                       web=result.sources["web"].confidence)

        except Exception as e:
            logger.warning("llm_source_selection_failed", error=str(e))
            # Fallback: rely on pre-activation and UI boost only

    def _finalize_selection(self, result: SourceSelectionResult) -> None:
        """
        Finalize: mark sources as needed based on confidence.
        Ensure at least 1 source, prefer 2 for robustness.
        """
        # Sort sources by confidence
        sources_ranked = sorted(
            result.sources.items(),
            key=lambda x: x[1].confidence,
            reverse=True
        )

        # Top source always needed if confidence >= MIN
        if sources_ranked[0][1].confidence >= self.MIN_CONFIDENCE:
            sources_ranked[0][1].needed = True

        # Second source needed if confidence >= MIN and top is not super confident
        if len(sources_ranked) > 1:
            top_conf = sources_ranked[0][1].confidence
            second_conf = sources_ranked[1][1].confidence

            # Include second source if:
            # - Its confidence is above MIN
            # - AND (top is not super confident OR second is close to top)
            if second_conf >= self.MIN_CONFIDENCE:
                if top_conf < self.HIGH_CONFIDENCE or (top_conf - second_conf) < 0.3:
                    sources_ranked[1][1].needed = True

        # Ensure at least one source is selected
        if not any(d.needed for _, d in sources_ranked):
            # Default to SQL + RAG
            result.sources["sql"].needed = True
            result.sources["sql"].reason = "Fallback default"
            result.sources["rag"].needed = True
            result.sources["rag"].reason = "Fallback default"
            result.quick_rules_applied.append("fallback_sql_rag")

        # Update reasons
        for name, decision in result.sources.items():
            if decision.needed:
                reasons = []
                if decision.pre_activated:
                    reasons.append("pattern match")
                if decision.ui_boosted:
                    reasons.append("docs sélectionnés")
                reasons.append(f"conf={decision.confidence:.2f}")
                decision.reason = ", ".join(reasons)


# Singleton
_source_selector: Optional[SourceSelectorAgent] = None

def get_source_selector() -> SourceSelectorAgent:
    global _source_selector
    if _source_selector is None:
        _source_selector = SourceSelectorAgent()
    return _source_selector
