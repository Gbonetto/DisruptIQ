"""
LLM Intent Classifier - World-Class Multi-Agent Routing

Uses Groq (Llama 3.1 8B) as primary for ultra-fast classification with:
- Semantic understanding (not just keywords)
- Conversation context awareness
- Few-shot examples for each intent type
- Chain-of-thought reasoning
- Confidence scoring with calibrated thresholds
- Fallback cascade (Groq → Mistral)

This replaces keyword-based classification for complex/ambiguous cases.
"""

import structlog
import json
import re
import os
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
from pydantic import BaseModel
from datetime import datetime

from app.models.intent import IntentType, Domain, DataSource, IntentClassification
from app.core.config import settings

logger = structlog.get_logger()


# ============================================================================
# GROQ CLIENT INITIALIZATION
# ============================================================================

_groq_client = None

def get_groq_client():
    """Get or create Groq client singleton."""
    global _groq_client
    if _groq_client is None:
        try:
            from groq import Groq
            api_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY")
            if api_key:
                _groq_client = Groq(api_key=api_key)
                logger.info("groq_client_initialized", model=settings.GROQ_MODEL)
            else:
                logger.warning("groq_api_key_not_configured")
        except ImportError:
            logger.warning("groq_package_not_installed")
    return _groq_client


# ============================================================================
# CONFIGURATION
# ============================================================================

# Provider preference (Groq primary, Mistral fallback)
CLASSIFIER_PROVIDER = "groq"  # "groq" or "mistral"

# Groq models
GROQ_MODEL_FAST = "llama-3.1-8b-instant"  # Primary: ultra-fast
GROQ_MODEL_ACCURATE = "llama-3.3-70b-versatile"  # Fallback: more accurate

# Legacy Mistral models (fallback)
MISTRAL_MODELS = [
    "mistral-small-latest",  # Fallback if Groq fails
]

# Confidence thresholds
CONFIDENCE_HIGH = 0.85       # Proceed without question
CONFIDENCE_MEDIUM = 0.70     # Proceed but log for review
CONFIDENCE_LOW = 0.50        # Ask clarification
CONFIDENCE_VERY_LOW = 0.30   # Definitely ask clarification

# Max conversation history to include (recent messages)
MAX_HISTORY_MESSAGES = 6


# ============================================================================
# CLASSIFIER PROMPT - THE HEART OF THE SYSTEM
# ============================================================================

CLASSIFIER_SYSTEM_PROMPT = """Tu es un routeur intelligent expert pour un logiciel de gestion de copropriété (syndic).

TON RÔLE: Analyser la demande de l'utilisateur et déterminer QUEL AGENT doit répondre.

## AGENTS DISPONIBLES

### 1. SQL_AGENT (intent: "query_data")
Interroge la BASE DE DONNÉES interne de la copropriété.
UTILISER POUR:
- Questions sur les copropriétaires (qui habite où, contacts, tantièmes)
- Questions sur les copropriétés (adresse, nombre de lots, équipements)
- Questions sur les professionnels (plombiers, électriciens, prestataires)
- Statistiques, comptages, listes ("combien", "liste des", "tous les")
- Données structurées existantes dans le système

EXEMPLES:
- "Combien de copropriétaires aux Mimosas ?" → query_data
- "Liste des plombiers disponibles" → query_data
- "Qui habite au lot 305 ?" → query_data
- "Email de M. Dupont" → query_data
- "Quels sont les lots vacants ?" → query_data

### 2. RAG_AGENT (intent: "search_documents")
Recherche dans les DOCUMENTS UPLOADÉS (factures, contrats, PV, devis).
UTILISER POUR:
- Questions sur le contenu des documents
- Résumés de documents
- Recherche d'informations dans factures/contrats/PV
- "Que dit ce document", "selon le contrat", "dans la facture"

EXEMPLES:
- "Que dit le contrat de syndic ?" → search_documents
- "Résume la dernière facture" → search_documents
- "Quel montant dans le devis du plombier ?" → search_documents
- "Analyse ce document" → search_documents

### 3. LEGAL_AGENT (intent: "legal")
Analyse juridique et réglementation (LOI, jurisprudence, obligations légales).
UTILISER POUR:
- Questions sur LA LOI (pas les documents internes)
- Conformité réglementaire (Loi ELAN, Loi Climat, Code civil)
- Obligations légales du syndic/copropriétaires
- Jurisprudence, textes de loi
- "Que dit la loi", "est-ce légal", "obligations légales"

EXEMPLES:
- "Que dit la loi sur les AG ?" → legal
- "Quelles sont les obligations du syndic ?" → legal
- "Est-ce conforme à la loi ELAN ?" → legal
- "Peut-on augmenter les charges légalement ?" → legal
- "Modalités de vote selon la loi" → legal

### 4. EMAIL_AGENT (intent: "send_email")
Rédige et envoie des emails aux destinataires.
UTILISER POUR:
- ACTIONS d'envoi d'email à quelqu'un
- "Envoie un email à...", "contacte...", "préviens...", "notifie..."
- Communication avec copropriétaires ou professionnels

⚠️ ATTENTION - DISTINCTION CRITIQUE:
- "Envoie-moi le budget" = DEMANDE D'INFO → query_data ou search_documents
- "Envoie email aux copropriétaires" = ACTION → send_email
- "Dis-moi", "donne-moi", "affiche" = DEMANDE D'INFO, PAS send_email

EXEMPLES:
- "Envoie un email aux copropriétaires pour l'AG" → send_email
- "Contacte le plombier pour intervention" → send_email
- "Préviens M. Dupont du dégât des eaux" → send_email
- "Envoie-moi la liste" → query_data (PAS send_email!)
- "Donne-moi les contacts" → query_data (PAS send_email!)

### 5. WORKFLOW_AGENT (intent: "trigger_workflow")
Gère les urgences et workflows automatisés multi-étapes.
UTILISER POUR:
- Situations d'URGENCE (fuite, dégât des eaux, gaz)
- Coordination multi-professionnels
- Plans d'action complexes
- Convocations AG avec workflow complet
- Processus automatisés ("déclenche", "lance le processus", "appels de fonds")

⚠️ DISTINCTION CRITIQUE workflow vs email:
- "Déclenche l'envoi des appels de fonds" = WORKFLOW (processus automatisé)
- "Envoie un email aux copropriétaires" = EMAIL (envoi simple)

EXEMPLES:
- "URGENT: fuite d'eau apt 12" → trigger_workflow
- "Dégât des eaux, coordonne les interventions" → trigger_workflow
- "Odeurs de gaz au 3e étage" → trigger_workflow
- "Organise l'AG du 15 décembre" → trigger_workflow
- "Déclenche l'envoi des appels de fonds" → trigger_workflow
- "Lance le processus de relance" → trigger_workflow

### 6. DIGEST_AGENT (intent: "generate_digest")
Génère des résumés d'emails et d'activité.
UTILISER POUR:
- Résumés d'emails reçus
- Digest quotidien/hebdomadaire
- Vue d'ensemble de l'activité email
- Questions sur les emails récents/urgents

⚠️ DISTINCTION: Toute question sur les EMAILS → generate_digest (pas query_data)

EXEMPLES:
- "Génère le digest des emails" → generate_digest
- "Résumé des emails de la semaine" → generate_digest
- "Emails urgents du jour" → generate_digest
- "Quels emails urgents ai-je reçus ?" → generate_digest
- "Y a-t-il des emails importants ?" → generate_digest

### 7. WEB_AGENT (intent: "web_search")
Recherche sur internet (actualités, tarifs du marché, entreprises externes).
UTILISER POUR:
- Recherche d'entreprises/prestataires EXTERNES (pas dans la base)
- Tarifs du MARCHÉ (prix moyens, estimations)
- Actualités, informations externes
- "Trouve-moi", "cherche sur internet", "prix moyen"

⚠️ DISTINCTION CRITIQUE web vs query_data:
- "Liste des plombiers" = query_data (dans notre base interne)
- "Trouve-moi des entreprises de ravalement" = web_search (recherche externe)
- "Prix moyen d'un ascenseur en 2024" = web_search (prix du marché)

EXEMPLES:
- "Tarifs électriciens à Paris" → web_search
- "Actualités loi copropriété 2024" → web_search
- "Trouve-moi des entreprises de ravalement" → web_search
- "Prix moyen d'un ascenseur en 2024" → web_search
- "Recherche des devis en ligne" → web_search
- "Recherche sur internet: isolation thermique" → web_search

### 8. GENERAL (intent: "general_question")
Questions générales, salutations, aide.
UTILISER POUR:
- Salutations, remerciements
- Questions sur le fonctionnement du système
- Demandes vagues nécessitant clarification

## RÈGLES DE CLASSIFICATION

1. **INFO vs ACTION**:
   - "Envoie-MOI", "donne-moi", "dis-moi", "affiche" = DEMANDE D'INFO (query_data/search_documents)
   - "Envoie À [personne]", "contacte", "préviens" = ACTION (send_email)

2. **LOI vs DOCUMENT**:
   - "Que dit LA LOI" = legal (droit externe)
   - "Que dit LE DOCUMENT/contrat/facture" = search_documents (données internes)

3. **DONNÉES vs DOCUMENTS**:
   - Données structurées (noms, emails, listes) = query_data (SQL)
   - Contenu de fichiers (factures, contrats, PV) = search_documents (RAG)

4. **URGENCE**: Mots comme "URGENT", "fuite", "dégât", "gaz" → trigger_workflow

5. **CONTEXTE CONVERSATION**: Utilise l'historique pour comprendre les références
   - "et pour les autres ?" → se réfère à la question précédente
   - "envoie-leur" → se réfère aux personnes mentionnées avant

6. **QUESTIONS FOLLOW-UP** (TRÈS IMPORTANT):
   Si la question est COURTE et commence par "Et...", "Aussi...", "Et pour...", "Qu'en est-il de...":
   - C'est probablement un FOLLOW-UP de la question précédente
   - PRIVILÉGIER le même intent que la question précédente
   - Exemples:
     * Historique: "Que dit le règlement sur les animaux?" (search_documents)
       Follow-up: "Et pour les chiens?" → search_documents (pas legal!)
     * Historique: "Combien de copropriétaires?" (query_data)
       Follow-up: "Et ceux en impayé?" → query_data
     * Historique: "Liste des plombiers" (query_data)
       Follow-up: "Contacte le premier" → send_email (changement d'action explicite)

## FORMAT DE RÉPONSE

Réponds UNIQUEMENT avec un JSON valide (pas de texte avant/après):

{
  "intent": "query_data|search_documents|legal|send_email|trigger_workflow|generate_digest|web_search|general_question",
  "confidence": 0.0 à 1.0,
  "reasoning": "Explication courte de ton choix (1-2 phrases)",
  "domain": "property_mgmt|legal|plumbing|vendor_mgmt|general",
  "suggested_sources": ["sql", "rag", "web", "legifrance"],
  "entities_detected": ["noms de personnes/lieux/documents mentionnés"],
  "needs_clarification": true/false,
  "clarification_question": "Question à poser si ambiguïté (ou null)"
}
"""


def _build_context_section(
    conversation_history: List[Dict[str, str]],
    context: Optional[Dict[str, Any]] = None
) -> str:
    """Build the context section of the prompt with conversation history and state."""

    sections = []

    # Conversation history (recent messages)
    if conversation_history:
        recent = conversation_history[-MAX_HISTORY_MESSAGES:]
        history_text = "\n".join([
            f"{'Utilisateur' if msg.get('role') == 'user' else 'Assistant'}: {msg.get('content', '')[:300]}"
            for msg in recent
        ])
        sections.append(f"## HISTORIQUE CONVERSATION RÉCENT\n{history_text}")

    # Current state/context
    if context:
        context_parts = []

        # Topic being discussed
        if context.get('topic'):
            context_parts.append(f"- Sujet en cours: {context['topic']}")

        # Pending action
        if context.get('pending_action'):
            context_parts.append(f"- Action en attente: {context['pending_action']}")

        # Last entities found (people, properties)
        if context.get('last_query_entities'):
            entities = context['last_query_entities'][:5]  # Limit
            entity_names = [e.get('name', e.get('nom', str(e))) for e in entities]
            context_parts.append(f"- Entités récemment trouvées: {', '.join(entity_names)}")

        # Active documents
        if context.get('active_document_names'):
            docs = context['active_document_names'][:3]
            context_parts.append(f"- Documents sélectionnés: {', '.join(docs)}")
        elif context.get('active_document_ids'):
            context_parts.append(f"- Documents sélectionnés: {len(context['active_document_ids'])} document(s)")

        # Email draft in progress
        if context.get('email_draft'):
            context_parts.append("- Un brouillon d'email est en cours de rédaction")

        # Business context (urgency, incident type)
        if context.get('business_context'):
            bc = context['business_context']
            if bc.get('urgency'):
                context_parts.append(f"- Niveau d'urgence: {bc['urgency']}")
            if bc.get('incident_type'):
                context_parts.append(f"- Type d'incident: {bc['incident_type']}")

        # Last intent (for cascading/follow-up questions)
        if context.get('last_intent'):
            context_parts.append(f"- Dernière intention détectée: {context['last_intent']}")
            context_parts.append("  ⚠️ Si la question est un follow-up court (Et..., Aussi..., précision), privilégier cette intention")

        if context_parts:
            sections.append("## CONTEXTE ACTUEL\n" + "\n".join(context_parts))

    return "\n\n".join(sections) if sections else ""


def _build_user_prompt(
    user_query: str,
    conversation_history: List[Dict[str, str]] = None,
    context: Optional[Dict[str, Any]] = None
) -> str:
    """Build the complete user prompt with context."""

    parts = []

    # Add context if available
    context_section = _build_context_section(conversation_history or [], context)
    if context_section:
        parts.append(context_section)

    # Add the actual query
    parts.append(f"## QUESTION DE L'UTILISATEUR\n\n{user_query}")

    # Reminder for response format
    parts.append("\nAnalyse cette demande et réponds avec le JSON de classification.")

    return "\n\n".join(parts)


def _parse_llm_response(response_text: str) -> Optional[Dict[str, Any]]:
    """Parse the LLM response, handling potential formatting issues."""

    # Try to extract JSON from the response
    text = response_text.strip()

    # Remove potential markdown code blocks
    if text.startswith("```"):
        # Find the JSON content
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if match:
            text = match.group(1).strip()

    # Try direct JSON parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in text
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    logger.warning("llm_response_parse_failed", response_preview=text[:200])
    return None


def _map_to_intent_classification(
    parsed: Dict[str, Any],
    original_query: str
) -> IntentClassification:
    """Convert parsed LLM response to IntentClassification object."""

    # Map intent string to IntentType enum
    intent_map = {
        "query_data": IntentType.QUERY_DATA,
        "search_documents": IntentType.SEARCH_DOCUMENTS,
        "legal": IntentType.LEGAL,
        "send_email": IntentType.SEND_EMAIL,
        "request_quotes": IntentType.REQUEST_QUOTES,
        "trigger_workflow": IntentType.TRIGGER_WORKFLOW,
        "generate_digest": IntentType.GENERATE_DIGEST,
        "web_search": IntentType.WEB_SEARCH,
        "general_question": IntentType.GENERAL_QUESTION,
    }

    intent_str = parsed.get("intent", "general_question").lower()
    intent = intent_map.get(intent_str, IntentType.GENERAL_QUESTION)

    # Map domain string to Domain enum
    domain_map = {
        "legal": Domain.LEGAL,
        "plumbing": Domain.PLUMBING,
        "property_mgmt": Domain.PROPERTY_MGMT,
        "vendor_mgmt": Domain.VENDOR_MGMT,
        "general": Domain.GENERAL,
    }

    domain_str = parsed.get("domain", "general").lower()
    domain = domain_map.get(domain_str, Domain.PROPERTY_MGMT)

    # Map suggested sources
    source_map = {
        "sql": DataSource.SQL,
        "rag": DataSource.RAG,
        "web": DataSource.WEB,
        "legifrance": DataSource.LEGIFRANCE,
        "uploaded_docs": DataSource.UPLOADED_DOCS,
        "conversation": DataSource.CONVERSATION,
    }

    suggested_sources = []
    for src in parsed.get("suggested_sources", []):
        if src.lower() in source_map:
            suggested_sources.append(source_map[src.lower()])

    # Default sources if none provided
    if not suggested_sources:
        from app.models.intent import INTENT_DEFAULT_SOURCES
        suggested_sources = INTENT_DEFAULT_SOURCES.get(intent, [DataSource.CONVERSATION])

    # Build classification
    confidence = float(parsed.get("confidence", 0.7))
    reasoning = parsed.get("reasoning", "Classification par LLM")

    # Clarification handling
    needs_clarification = parsed.get("needs_clarification", False)
    clarification_question = parsed.get("clarification_question")

    # If low confidence, suggest clarification
    if confidence < CONFIDENCE_LOW and not needs_clarification:
        needs_clarification = True
        clarification_question = "Pouvez-vous préciser votre demande ?"

    return IntentClassification(
        intent=intent,
        domain=domain,
        confidence=confidence,
        suggested_sources=suggested_sources,
        reasoning=f"[LLM] {reasoning}",
        keywords_matched=parsed.get("entities_detected", []),
        needs_clarification=needs_clarification,
        clarification_question=clarification_question
    )


class LLMIntentClassifier:
    """
    LLM-based intent classifier for world-class accuracy.

    Uses Groq (Llama 3.1 8B) as primary with:
    - Ultra-fast inference (~700ms)
    - Semantic understanding
    - Conversation context
    - Few-shot examples
    - Fallback cascade (Groq → Mistral)
    """

    def __init__(self):
        self.groq_client = get_groq_client()
        self._mistral_service = None  # Lazy-loaded fallback
        self._call_count = 0
        self._cache: Dict[str, IntentClassification] = {}
        self._groq_available = self.groq_client is not None
        logger.info(
            "llm_intent_classifier_initialized",
            provider="groq" if self._groq_available else "mistral",
            groq_available=self._groq_available
        )

    @property
    def mistral_service(self):
        """Lazy-load Mistral service as fallback."""
        if self._mistral_service is None:
            from app.services.llm_service import LLMService
            self._mistral_service = LLMService()
        return self._mistral_service

    async def classify(
        self,
        user_query: str,
        conversation_history: List[Dict[str, str]] = None,
        context: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> IntentClassification:
        """
        Classify user intent using LLM.

        Args:
            user_query: The user's question/request
            conversation_history: Recent conversation messages [{role, content}]
            context: Current state (topic, entities, documents, etc.)
            use_cache: Whether to use cached results for identical queries

        Returns:
            IntentClassification with intent, confidence, reasoning, etc.
        """

        start_time = datetime.now()
        self._call_count += 1

        # Simple cache for identical recent queries (avoid repeated calls)
        cache_key = f"{user_query}:{hash(str(conversation_history)[-100:]) if conversation_history else ''}"
        if use_cache and cache_key in self._cache:
            logger.info("llm_classifier_cache_hit", query=user_query[:50])
            return self._cache[cache_key]

        # Build prompts
        system_prompt = CLASSIFIER_SYSTEM_PROMPT
        user_prompt = _build_user_prompt(user_query, conversation_history, context)

        logger.info(
            "llm_classification_started",
            query=user_query[:100],
            history_len=len(conversation_history) if conversation_history else 0,
            has_context=context is not None,
            provider="groq" if self._groq_available else "mistral"
        )

        # Try providers in order: Groq (fast) → Mistral (fallback)
        last_error = None
        result = None

        # === STEP 1: Try Groq (primary - ultra fast) ===
        if self._groq_available:
            try:
                result = await self._classify_with_groq(
                    model=GROQ_MODEL_FAST,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    user_query=user_query
                )

                # If low confidence, try more powerful Groq model
                if result.confidence < CONFIDENCE_MEDIUM:
                    logger.info(
                        "groq_low_confidence_retry",
                        model=GROQ_MODEL_FAST,
                        confidence=result.confidence,
                        next_model=GROQ_MODEL_ACCURATE
                    )
                    result = await self._classify_with_groq(
                        model=GROQ_MODEL_ACCURATE,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        user_query=user_query
                    )

            except Exception as e:
                last_error = e
                logger.warning(
                    "groq_classification_failed",
                    error=str(e),
                    falling_back_to="mistral"
                )
                result = None

        # === STEP 2: Fallback to Mistral if Groq failed ===
        if result is None:
            for model in MISTRAL_MODELS:
                try:
                    result = await self._classify_with_mistral(
                        model=model,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        user_query=user_query
                    )
                    break
                except Exception as e:
                    last_error = e
                    logger.warning(
                        "mistral_classification_failed",
                        model=model,
                        error=str(e)
                    )
                    continue

        # === STEP 3: Keyword fallback if all LLMs failed ===
        if result is None:
            logger.error(
                "llm_classifier_all_providers_failed",
                error=str(last_error) if last_error else "Unknown"
            )
            result = self._fallback_classification(user_query)

        # Log timing
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.info(
            "llm_classification_completed",
            intent=result.intent.value,
            confidence=result.confidence,
            duration_ms=round(duration_ms, 2),
            reasoning=result.reasoning[:100]
        )

        # Cache result
        if use_cache:
            self._cache[cache_key] = result
            # Limit cache size
            if len(self._cache) > 100:
                # Remove oldest entries
                keys = list(self._cache.keys())
                for key in keys[:50]:
                    del self._cache[key]

        return result

    async def _classify_with_groq(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        user_query: str
    ) -> IntentClassification:
        """Classify using Groq API (ultra-fast)."""
        import asyncio

        def _call_groq():
            return self.groq_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )

        # Run sync Groq call in executor
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _call_groq)
        response_text = response.choices[0].message.content

        # Parse response
        parsed = _parse_llm_response(response_text)

        if parsed is None:
            raise ValueError(f"Failed to parse Groq response: {response_text[:200]}")

        # Add provider info to reasoning
        result = _map_to_intent_classification(parsed, user_query)
        result.reasoning = result.reasoning.replace("[LLM]", f"[Groq/{model}]")

        logger.debug(
            "groq_classification_success",
            model=model,
            intent=result.intent.value,
            confidence=result.confidence
        )

        return result

    async def _classify_with_mistral(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        user_query: str
    ) -> IntentClassification:
        """Classify using Mistral API (fallback)."""

        # Call Mistral via LLMService
        response = await self.mistral_service.generate_response(
            prompt=user_prompt,
            system_prompt=system_prompt,
            max_tokens=500,
            temperature=0.1
        )

        # Parse response
        parsed = _parse_llm_response(response)

        if parsed is None:
            raise ValueError(f"Failed to parse Mistral response: {response[:200]}")

        # Add provider info to reasoning
        result = _map_to_intent_classification(parsed, user_query)
        result.reasoning = result.reasoning.replace("[LLM]", f"[Mistral/{model}]")

        logger.debug(
            "mistral_classification_success",
            model=model,
            intent=result.intent.value,
            confidence=result.confidence
        )

        return result

    def _fallback_classification(self, user_query: str) -> IntentClassification:
        """Fallback classification when LLM fails."""

        query_lower = user_query.lower()

        # Very basic keyword fallback
        if any(w in query_lower for w in ["loi", "légal", "obligation", "droit"]):
            intent = IntentType.LEGAL
        elif any(w in query_lower for w in ["document", "facture", "contrat", "pv"]):
            intent = IntentType.SEARCH_DOCUMENTS
        elif any(w in query_lower for w in ["urgent", "fuite", "dégât", "gaz"]):
            intent = IntentType.TRIGGER_WORKFLOW
        elif any(w in query_lower for w in ["digest", "résumé email"]):
            intent = IntentType.GENERATE_DIGEST
        elif any(w in query_lower for w in ["envoie email", "contacte", "préviens"]):
            intent = IntentType.SEND_EMAIL
        else:
            intent = IntentType.QUERY_DATA  # Default to data query

        return IntentClassification(
            intent=intent,
            domain=Domain.PROPERTY_MGMT,
            confidence=0.5,  # Low confidence for fallback
            suggested_sources=[DataSource.SQL, DataSource.RAG],
            reasoning="[FALLBACK] Classification par mots-clés (LLM indisponible)",
            needs_clarification=True,
            clarification_question="Le système a eu du mal à comprendre. Pouvez-vous reformuler ?"
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get classifier statistics."""
        return {
            "total_calls": self._call_count,
            "cache_size": len(self._cache)
        }


# Singleton instance
_classifier_instance: Optional[LLMIntentClassifier] = None


def get_llm_intent_classifier() -> LLMIntentClassifier:
    """Get the singleton LLM intent classifier instance."""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = LLMIntentClassifier()
    return _classifier_instance


# ============================================================================
# INTEGRATION HELPER - To be called from orchestrator
# ============================================================================

async def classify_intent_with_llm(
    user_query: str,
    conversation_history: List[Dict[str, str]] = None,
    context: Optional[Dict[str, Any]] = None
) -> IntentClassification:
    """
    Convenience function to classify intent using LLM.

    This is the main entry point for the orchestrator to use.

    Args:
        user_query: User's question
        conversation_history: Recent messages
        context: Current state/context

    Returns:
        IntentClassification
    """
    classifier = get_llm_intent_classifier()
    return await classifier.classify(user_query, conversation_history, context)
