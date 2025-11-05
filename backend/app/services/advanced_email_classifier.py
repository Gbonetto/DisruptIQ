"""
Advanced Email Classifier
Classification multi-dimension des emails avec extraction d'entités

Architecture:
- Classification LLM (urgency + category + sentiment + action detection)
- Extraction d'entités (montants, dates, personnes via EntityExtractor)
- Priority scoring composite (0-100)
- Thread awareness (contexte conversation)
- Suggested actions generation
"""

from typing import Dict, Any, List, Optional
import structlog
from datetime import datetime
import json
import re

from app.services.llm_service import LLMService
from app.services.conversation.entity_extractor import EntityExtractor
from app.models.email_category import EmailCategory, EmailSentiment
from app.models.email import EmailUrgency

logger = structlog.get_logger(__name__)


class AdvancedEmailClassifier:
    """
    Classificateur d'emails avancé

    Capacités:
    - Classification multi-dimension (urgency + category + sentiment)
    - Extraction d'entités (montants, dates, personnes, lieux)
    - Détection d'actions requises (réponse, validation, deadline)
    - Score de priorité composite (0-100)
    - Détection de threads/conversations
    - Suggestions de réponse
    """

    # Pondération pour priority score
    URGENCY_WEIGHT = 40
    CATEGORY_WEIGHT = 20
    DEADLINE_WEIGHT = 20
    AMOUNT_WEIGHT = 10
    SENDER_WEIGHT = 10

    # Catégories haute priorité
    HIGH_PRIORITY_CATEGORIES = [
        EmailCategory.INTERVENTION_URGENTE,
        EmailCategory.RECLAMATION_COPROPRIETAIRE,
        EmailCategory.VOTE_DECISION,
    ]

    MEDIUM_PRIORITY_CATEGORIES = [
        EmailCategory.FACTURE_FOURNISSEUR,
        EmailCategory.DEVIS_FOURNISSEUR,
        EmailCategory.PAIEMENT_CHARGES,
    ]

    def __init__(self):
        self.llm_service = LLMService()
        self.entity_extractor = EntityExtractor()

    async def classify_advanced(
        self,
        email: Dict[str, Any],
        thread_emails: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Classification avancée d'un email

        Args:
            email: Email à classifier
            thread_emails: Emails du même thread (pour contexte)

        Returns:
            Dict avec classification complète pour llm_analysis JSON column
            {
                "urgency": "urgent|important|routine",
                "category": "devis_fournisseur|...",
                "subcategory": "plomberie|...",
                "sentiment": "positive|neutral|negative|angry",
                "confidence": 0.85,
                "entities": {...},
                "action_required": true,
                "deadline": "2024-11-15T17:00:00Z",
                "priority_score": 85,
                "thread_summary": "...",
                "suggested_response": "...",
                "tags": ["plomberie", "urgent"]
            }
        """
        try:
            # Étape 1: Extraction d'entités depuis texte
            text = f"{email.get('subject', '')} {email.get('body', '')}"
            entities = self.entity_extractor.extract_entities(text)

            logger.debug(
                "entities_extracted",
                message_id=email.get('message_id'),
                entities_count=sum(len(v) if isinstance(v, list) else 1 for v in entities.values())
            )

            # Étape 2: Classification LLM
            llm_result = await self._classify_with_llm(email, thread_emails, entities)

            # Étape 3: Calcul du score de priorité
            priority_score = self._calculate_priority_score(
                urgency=llm_result.get('urgency', 'routine'),
                category=llm_result.get('category', EmailCategory.AUTRE.value),
                has_deadline=llm_result.get('deadline') is not None,
                has_amount=len(entities.get('amounts', [])) > 0,
                sender=email.get('sender', '')
            )

            # Étape 4: Assemblage résultat final
            result = {
                "urgency": llm_result.get('urgency', 'routine'),
                "category": llm_result.get('category', EmailCategory.AUTRE.value),
                "subcategory": llm_result.get('subcategory'),
                "sentiment": llm_result.get('sentiment', EmailSentiment.NEUTRAL.value),
                "confidence": llm_result.get('confidence', 0.5),
                "entities": entities,
                "action_required": llm_result.get('action_required', False),
                "deadline": llm_result.get('deadline'),
                "priority_score": priority_score,
                "thread_summary": llm_result.get('thread_summary'),
                "suggested_response": llm_result.get('suggested_response'),
                "tags": llm_result.get('tags', []),
            }

            logger.info(
                "email_classified_advanced",
                message_id=email.get('message_id'),
                urgency=result['urgency'],
                category=result['category'],
                priority_score=priority_score,
                action_required=result['action_required']
            )

            return result

        except Exception as e:
            logger.error(
                "advanced_classification_failed",
                message_id=email.get('message_id'),
                error=str(e),
                exc_info=True
            )
            # Fallback to basic classification
            return {
                "urgency": "routine",
                "category": EmailCategory.AUTRE.value,
                "subcategory": None,
                "sentiment": EmailSentiment.NEUTRAL.value,
                "confidence": 0.3,
                "entities": {},
                "action_required": False,
                "deadline": None,
                "priority_score": 30,
                "thread_summary": None,
                "suggested_response": None,
                "tags": [],
                "error": str(e)
            }

    async def _classify_with_llm(
        self,
        email: Dict[str, Any],
        thread_emails: Optional[List[Dict[str, Any]]],
        entities: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Classification LLM avec prompt structuré

        Args:
            email: Email à classifier
            thread_emails: Contexte du thread
            entities: Entités extraites

        Returns:
            Classification LLM
        """
        prompt = self._build_classification_prompt(email, thread_emails, entities)

        try:
            # Appel LLM avec response format JSON
            response = await self.llm_service.generate_response(
                prompt=prompt,
                temperature=0.1,  # Bas pour cohérence
                max_tokens=500
            )

            # Parser JSON response
            try:
                result = json.loads(response)
            except json.JSONDecodeError:
                # Essayer d'extraire JSON depuis markdown
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group(0))
                else:
                    raise ValueError("LLM response not valid JSON")

            return result

        except Exception as e:
            logger.error("llm_classification_failed", error=str(e))
            # Fallback basique
            return {
                "urgency": "routine",
                "category": EmailCategory.AUTRE.value,
                "sentiment": EmailSentiment.NEUTRAL.value,
                "confidence": 0.3,
                "action_required": False
            }

    def _build_classification_prompt(
        self,
        email: Dict[str, Any],
        thread_emails: Optional[List[Dict[str, Any]]],
        entities: Dict[str, Any]
    ) -> str:
        """Construit le prompt pour le LLM"""

        # Format entités pour le prompt
        entities_str = "Aucune"
        if entities:
            entity_parts = []
            if entities.get('amounts'):
                entity_parts.append(f"Montants: {entities['amounts']}")
            if entities.get('dates'):
                entity_parts.append(f"Dates: {entities['dates']}")
            if entities.get('suppliers'):
                entity_parts.append(f"Fournisseurs: {entities['suppliers']}")
            entities_str = " | ".join(entity_parts) if entity_parts else "Aucune"

        # Contexte du thread
        thread_context = self._format_thread_context(thread_emails) if thread_emails else "Premier email de la conversation"

        prompt = f"""Tu es un assistant de classification d'emails pour un syndic de copropriété.

**EMAIL À CLASSIFIER:**
Sujet: {email.get('subject', 'Sans objet')}
Expéditeur: {email.get('sender', 'Inconnu')}
Corps (début): {email.get('body', '')[:500]}...

**ENTITÉS DÉTECTÉES:**
{entities_str}

**CONTEXTE DU THREAD:**
{thread_context}

**CATÉGORIES POSSIBLES:**
- devis_fournisseur: Devis de prestataire/fournisseur
- facture_fournisseur: Facture à payer
- travaux_planification: Planification de travaux
- intervention_urgente: Intervention urgente nécessaire
- reclamation_coproprietaire: Réclamation/plainte d'un copropriétaire
- question_coproprietaire: Question d'un copropriétaire
- paiement_charges: Paiement de charges
- assemblee_generale: Assemblée générale
- vote_decision: Vote ou décision à prendre
- document_administratif: Document administratif
- comptabilite: Comptabilité
- budget: Budget
- paiement: Paiement
- information: Information générale
- spam: Spam/pub
- autre: Autre

**INSTRUCTIONS:**
1. Analyse l'email et détermine:
   - urgency: urgent (action immédiate), important (action bientôt), routine (pas urgent)
   - category: une des catégories ci-dessus
   - subcategory: type spécifique (ex: "plomberie", "électricité", "peinture")
   - sentiment: positive, neutral, negative, angry
   - action_required: true si une action est nécessaire (réponse, validation, paiement)
   - deadline: date limite au format ISO si mentionnée
   - suggested_response: action suggérée en 1 phrase
   - tags: 2-3 mots-clés pertinents

2. Retourne UNIQUEMENT un JSON valide (pas de markdown):
{{
    "urgency": "urgent|important|routine",
    "category": "category_name",
    "subcategory": "specific_type",
    "sentiment": "positive|neutral|negative|angry",
    "confidence": 0.85,
    "action_required": true|false,
    "deadline": "2024-11-15T17:00:00Z" ou null,
    "thread_summary": "Résumé du contexte en 1 phrase",
    "suggested_response": "Action suggérée",
    "tags": ["mot1", "mot2", "mot3"]
}}
"""
        return prompt

    def _format_thread_context(self, thread_emails: List[Dict[str, Any]]) -> str:
        """Formate le contexte du thread pour le prompt"""
        if not thread_emails or len(thread_emails) <= 1:
            return "Premier email de la conversation"

        context = f"Conversation de {len(thread_emails)} emails:\n"
        for i, email in enumerate(thread_emails[-3:], 1):  # Derniers 3 emails
            context += f"{i}. {email.get('subject', 'Sans objet')} (de {email.get('sender', 'Inconnu')})\n"

        return context

    def _calculate_priority_score(
        self,
        urgency: str,
        category: str,
        has_deadline: bool,
        has_amount: bool,
        sender: str
    ) -> int:
        """
        Calcule un score de priorité composite (0-100)

        Pondération:
        - Urgency: 40 points max
        - Category: 20 points max
        - Deadline: 20 points max
        - Amount: 10 points max
        - Sender: 10 points max
        """
        score = 0

        # Urgency (40 points)
        urgency_scores = {
            EmailUrgency.URGENT.value: 40,
            EmailUrgency.IMPORTANT.value: 25,
            EmailUrgency.ROUTINE.value: 10
        }
        score += urgency_scores.get(urgency, 10)

        # Category (20 points)
        if category in [c.value for c in self.HIGH_PRIORITY_CATEGORIES]:
            score += 20
        elif category in [c.value for c in self.MEDIUM_PRIORITY_CATEGORIES]:
            score += 15
        else:
            score += 10

        # Deadline (20 points)
        if has_deadline:
            score += 20

        # Amount (10 points)
        if has_amount:
            score += 10

        # Sender importance (10 points)
        score += self._get_sender_importance(sender)

        return min(score, 100)

    def _get_sender_importance(self, sender: str) -> int:
        """
        Évalue l'importance de l'expéditeur (0-10)

        TODO: Intégrer avec base de données (professionnels, coproprietaires)
        Pour l'instant, logique simple basée sur patterns
        """
        sender_lower = sender.lower()

        # Expéditeurs non importants
        if any(pattern in sender_lower for pattern in ['noreply', 'no-reply', 'donotreply', 'newsletter']):
            return 0

        # Expéditeurs gouvernementaux/officiels
        if any(pattern in sender_lower for pattern in ['@gouv.fr', '@mairie', '@prefecture']):
            return 10

        # Domaines professionnels (plomberie, électricité, etc.)
        if any(pattern in sender_lower for pattern in ['.fr', '.com', '.eu']):
            # Email professionnel standard
            return 5

        # Email personnel (gmail, outlook, etc.)
        if any(pattern in sender_lower for pattern in ['@gmail', '@outlook', '@hotmail', '@yahoo']):
            return 3

        # Défaut
        return 5
