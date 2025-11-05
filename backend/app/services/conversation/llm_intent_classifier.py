"""
LLM-Enhanced Intent Classifier - Classification hybride avec LLM

Utilise une approche à deux niveaux :
- Niveau 1 : Pattern matching rapide (hérité d'IntentClassifier)
- Niveau 2 : LLM pour les cas complexes ou ambigus

Usage :
    classifier = LLMIntentClassifier(llm_service)
    scores = await classifier.classify_async(message, context)
"""

from typing import Dict, List, Optional
import json
import structlog

from app.models.conversation import ConversationTurn
from app.services.conversation.intent_classifier import IntentClassifier
from app.services.llm_service import LLMService

logger = structlog.get_logger(__name__)


class LLMIntentClassifier(IntentClassifier):
    """
    Classificateur d'intent hybride avec fallback LLM

    Combine pattern matching rapide et compréhension LLM pour
    une meilleure précision sur les requêtes complexes
    """

    # Threshold pour déclencher le LLM
    LLM_CONFIDENCE_THRESHOLD = 0.75

    # Intent descriptions for LLM
    INTENT_DESCRIPTIONS = {
        "QUERY_INVOICE": "Rechercher, lister ou afficher des factures. Exemples: 'montre les factures', 'factures de plomberie', 'facture 123'",
        "QUERY_SUPPLIER": "Rechercher ou lister des fournisseurs/prestataires. Exemples: 'qui est le plombier', 'liste des fournisseurs', 'contact électricien'",
        "QUERY_STATS": "Obtenir des statistiques, totaux, moyennes, comptages. Exemples: 'combien de factures', 'quel est le total', 'moyenne des montants'",
        "QUERY_DOCUMENT": "Rechercher des documents, PDF, fichiers. Exemples: 'cherche le document', 'où est le PDF', 'trouve le contrat'",
        "ACTION_CREATE": "Créer ou ajouter une nouvelle entité. Exemples: 'créer une facture', 'ajouter un fournisseur', 'nouveau document'",
        "ACTION_UPDATE": "Modifier ou mettre à jour une entité existante. Exemples: 'modifier la facture', 'changer le montant', 'mettre à jour le statut'",
        "ACTION_DELETE": "Supprimer une entité. Exemples: 'supprimer la facture', 'effacer le document', 'retirer le fournisseur'",
        "CLARIFICATION": "Demander une clarification ou reformuler. Exemples: 'je ne comprends pas', 'peux-tu clarifier', 'qu'est-ce que tu veux dire'",
        "FEEDBACK": "Donner un feedback ou signaler un problème. Exemples: 'c'est faux', 'ça ne marche pas', 'erreur'",
        "GREETING": "Salutation ou politesse. Exemples: 'bonjour', 'salut', 'bonsoir', 'merci'",
        "HELP": "Demander de l'aide ou des instructions. Exemples: 'aide-moi', 'comment faire', 'je ne sais pas'",
        "OTHER": "Autre intention non catégorisée"
    }

    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Initialise le classificateur hybride

        Args:
            llm_service: Service LLM pour la classification avancée
        """
        super().__init__()
        self.llm_service = llm_service
        self.logger = logger.bind(service="llm_intent_classifier")

    async def classify_async(
        self,
        message: str,
        conversation_context: Optional[List[ConversationTurn]] = None,
        use_llm: bool = True
    ) -> Dict[str, float]:
        """
        Classifie l'intent avec support LLM asynchrone

        Args:
            message: Message utilisateur
            conversation_context: Historique de conversation
            use_llm: Si True, utilise le LLM quand nécessaire

        Returns:
            Dict de scores par intent
        """
        # Étape 1: Classification rapide par patterns
        scores = self.classify(message, conversation_context)

        # Get top intent and confidence
        if not scores:
            top_confidence = 0.0
            top_intent = "OTHER"
        else:
            top_intent = max(scores.items(), key=lambda x: x[1])[0]
            top_confidence = scores[top_intent]

        # Étape 2: Si confidence faible, utiliser le LLM
        if use_llm and self.llm_service and top_confidence < self.LLM_CONFIDENCE_THRESHOLD:
            self.logger.info(
                "low_confidence_using_llm",
                top_intent=top_intent,
                confidence=top_confidence,
                threshold=self.LLM_CONFIDENCE_THRESHOLD
            )

            try:
                llm_scores = await self._classify_with_llm(message, conversation_context)

                # Merge scores: prendre le max entre pattern et LLM
                merged_scores = {}
                all_intents = set(scores.keys()) | set(llm_scores.keys())

                for intent in all_intents:
                    pattern_score = scores.get(intent, 0.0)
                    llm_score = llm_scores.get(intent, 0.0)
                    # Prendre le max avec un bonus pour le LLM
                    merged_scores[intent] = max(pattern_score, llm_score * 1.1)

                self.logger.info(
                    "llm_classification_complete",
                    pattern_top=top_intent,
                    llm_top=max(llm_scores.items(), key=lambda x: x[1])[0] if llm_scores else None,
                    merged_top=max(merged_scores.items(), key=lambda x: x[1])[0]
                )

                return self._normalize_scores(merged_scores)

            except Exception as e:
                self.logger.error("llm_classification_error", error=str(e), exc_info=True)
                # Fallback to pattern matching
                return scores

        return scores

    async def _classify_with_llm(
        self,
        message: str,
        context: Optional[List[ConversationTurn]] = None
    ) -> Dict[str, float]:
        """
        Utilise le LLM pour classifier l'intent

        Args:
            message: Message utilisateur
            context: Historique de conversation

        Returns:
            Dict de scores par intent
        """
        # Format context for LLM
        context_text = self._format_context_for_llm(context) if context else "Pas de contexte précédent."

        # Build intent list
        intent_list = "\n".join([
            f"- {intent}: {desc}"
            for intent, desc in self.INTENT_DESCRIPTIONS.items()
        ])

        prompt = f"""Tu es un système d'analyse d'intentions pour un logiciel de gestion de copropriété.

Contexte de conversation précédente:
{context_text}

Message actuel de l'utilisateur: "{message}"

Analyse cette demande et détermine l'intention principale parmi ces catégories:
{intent_list}

Réponds UNIQUEMENT avec un objet JSON valide contenant les scores de confiance pour chaque intention (entre 0 et 1).
La somme des scores n'a pas besoin d'être égale à 1. Indique 0 pour les intentions non pertinentes.

Format de réponse (JSON uniquement, sans texte additionnel):
{{
    "QUERY_INVOICE": 0.9,
    "QUERY_SUPPLIER": 0.1,
    "QUERY_STATS": 0.0,
    "QUERY_DOCUMENT": 0.0,
    "ACTION_CREATE": 0.0,
    "ACTION_UPDATE": 0.0,
    "ACTION_DELETE": 0.0,
    "CLARIFICATION": 0.0,
    "FEEDBACK": 0.0,
    "GREETING": 0.0,
    "HELP": 0.0,
    "OTHER": 0.0
}}

Réponse JSON:"""

        try:
            # Call LLM
            response = await self.llm_service.generate_async(
                prompt=prompt,
                max_tokens=300,
                temperature=0.1  # Low temperature for consistent classification
            )

            # Parse JSON response
            scores = self._parse_llm_response(response)

            return scores

        except Exception as e:
            self.logger.error("llm_call_error", error=str(e))
            raise

    def _format_context_for_llm(self, context: List[ConversationTurn]) -> str:
        """
        Formate le contexte pour le LLM

        Args:
            context: Liste de tours de conversation

        Returns:
            Texte formaté du contexte
        """
        if not context:
            return "Pas de contexte."

        # Take last 3 turns for context
        recent_context = context[-3:] if len(context) > 3 else context

        lines = []
        for turn in recent_context:
            lines.append(f"User: {turn.user_message}")
            lines.append(f"Assistant: {turn.assistant_message[:100]}...")  # Truncate long responses
            lines.append(f"(Intent détecté: {turn.detected_intent})")
            lines.append("")

        return "\n".join(lines)

    def _parse_llm_response(self, response: str) -> Dict[str, float]:
        """
        Parse la réponse JSON du LLM

        Args:
            response: Réponse brute du LLM

        Returns:
            Dict de scores
        """
        try:
            # Try to extract JSON from response
            # Sometimes LLM adds text before/after JSON
            json_start = response.find('{')
            json_end = response.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                scores = json.loads(json_str)

                # Validate and normalize scores
                validated_scores = {}
                for intent, score in scores.items():
                    if intent in self.INTENT_DESCRIPTIONS:
                        # Ensure score is between 0 and 1
                        validated_scores[intent] = max(0.0, min(1.0, float(score)))

                return validated_scores
            else:
                raise ValueError("No JSON found in LLM response")

        except (json.JSONDecodeError, ValueError) as e:
            self.logger.error("llm_response_parse_error", response=response[:200], error=str(e))
            # Return empty scores as fallback
            return {}

    async def explain_classification(
        self,
        message: str,
        context: Optional[List[ConversationTurn]] = None
    ) -> Dict[str, any]:
        """
        Explique la classification avec détails

        Utile pour debugging et logging

        Args:
            message: Message à classifier
            context: Contexte conversationnel

        Returns:
            Dict avec scores et explications
        """
        # Get pattern-based scores
        pattern_scores = self.classify(message, context)
        top_pattern_intent = max(pattern_scores.items(), key=lambda x: x[1])[0] if pattern_scores else "OTHER"
        top_pattern_confidence = pattern_scores.get(top_pattern_intent, 0.0)

        explanation = {
            "message": message,
            "pattern_classification": {
                "scores": pattern_scores,
                "top_intent": top_pattern_intent,
                "confidence": top_pattern_confidence
            },
            "used_llm": False,
            "llm_classification": None,
            "final_classification": None
        }

        # Try LLM if confidence is low
        if self.llm_service and top_pattern_confidence < self.LLM_CONFIDENCE_THRESHOLD:
            try:
                llm_scores = await self._classify_with_llm(message, context)
                top_llm_intent = max(llm_scores.items(), key=lambda x: x[1])[0] if llm_scores else "OTHER"

                explanation["used_llm"] = True
                explanation["llm_classification"] = {
                    "scores": llm_scores,
                    "top_intent": top_llm_intent,
                    "confidence": llm_scores.get(top_llm_intent, 0.0)
                }

                # Merge scores
                merged = {}
                all_intents = set(pattern_scores.keys()) | set(llm_scores.keys())
                for intent in all_intents:
                    merged[intent] = max(pattern_scores.get(intent, 0.0), llm_scores.get(intent, 0.0) * 1.1)

                top_final_intent = max(merged.items(), key=lambda x: x[1])[0]
                explanation["final_classification"] = {
                    "scores": merged,
                    "top_intent": top_final_intent,
                    "confidence": merged[top_final_intent]
                }

            except Exception as e:
                explanation["llm_error"] = str(e)
                explanation["final_classification"] = explanation["pattern_classification"]
        else:
            explanation["final_classification"] = explanation["pattern_classification"]

        return explanation


# Convenience function for backward compatibility
async def classify_intent_with_llm(
    message: str,
    llm_service: LLMService,
    context: Optional[List[ConversationTurn]] = None
) -> Dict[str, float]:
    """
    Helper function pour classifier rapidement avec LLM

    Args:
        message: Message à classifier
        llm_service: Service LLM
        context: Contexte optionnel

    Returns:
        Scores d'intent
    """
    classifier = LLMIntentClassifier(llm_service)
    return await classifier.classify_async(message, context)
