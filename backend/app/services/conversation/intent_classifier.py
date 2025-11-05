"""
Intent Classifier - Classification avancée des intentions utilisateur

Classe les intentions avec multi-label support et contexte conversationnel
"""

from typing import Dict, List, Optional, Tuple
import re

from app.models.conversation import ConversationTurn
import structlog

logger = structlog.get_logger(__name__)


class IntentClassifier:
    """
    Classifie les intentions utilisateur avec support multi-label
    et enrichissement contextuel
    """

    # Intent keywords (French)
    INTENT_PATTERNS = {
        "QUERY_INVOICE": {
            "keywords": [
                "facture", "factures", "invoice", "invoices",
                "montant", "amount", "paiement", "payment"
            ],
            "patterns": [
                r"combien.*facture",
                r"liste.*facture",
                r"montre.*facture",
                r"facture.*\d+",
            ]
        },
        "QUERY_SUPPLIER": {
            "keywords": [
                "fournisseur", "fournisseurs", "supplier",
                "plombier", "électricien", "chauffagiste",
                "prestataire", "professionnel"
            ],
            "patterns": [
                r"qui.*(plombier|électricien|fournisseur)",
                r"contact.*fournisseur",
                r"liste.*fournisseur"
            ]
        },
        "QUERY_STATS": {
            "keywords": [
                "combien", "total", "moyenne", "statistique",
                "nombre", "count", "sum"
            ],
            "patterns": [
                r"combien de",
                r"quel.*total",
                r"quelle.*moyenne"
            ]
        },
        "QUERY_DOCUMENT": {
            "keywords": [
                "document", "doc", "fichier", "pdf",
                "recherche", "cherche", "trouve"
            ],
            "patterns": [
                r"cherch.*document",
                r"où.*document",
                r"trouve.*pdf"
            ]
        },
        "ACTION_CREATE": {
            "keywords": [
                "créer", "créé", "crée",
                "ajouter", "ajouté", "ajoute",
                "nouveau", "nouvelle", "new"
            ],
            "patterns": [
                r"créer (un|une|le|la)",
                r"ajouter (un|une|le|la)",
                r"nouveau (facture|fournisseur|document)"
            ]
        },
        "ACTION_UPDATE": {
            "keywords": [
                "modifier", "modifie", "modifié",
                "changer", "change", "changé",
                "mettre à jour", "update", "edit"
            ],
            "patterns": [
                r"modifier (le|la|l')",
                r"changer (le|la|l')",
                r"mettre à jour"
            ]
        },
        "ACTION_DELETE": {
            "keywords": [
                "supprimer", "supprime", "supprimé",
                "effacer", "efface", "effacé",
                "annuler", "annule", "delete"
            ],
            "patterns": [
                r"supprimer (le|la|l')",
                r"effacer (le|la|l')"
            ]
        },
        "CLARIFICATION": {
            "keywords": [
                "oui", "non", "si", "plutôt",
                "en fait", "actually", "rather",
                "je veux dire", "I mean"
            ],
            "patterns": [
                r"^(oui|non|si)",
                r"plutôt",
                r"en fait"
            ]
        },
        "FEEDBACK": {
            "keywords": [
                "merci", "thank", "parfait", "super",
                "génial", "excellent", "mauvais",
                "nul", "incorrect", "erreur"
            ],
            "patterns": [
                r"^merci",
                r"c'est (parfait|super|génial|mauvais|incorrect)"
            ]
        },
        "GREETING": {
            "keywords": [
                "bonjour", "salut", "hello", "hi",
                "bonsoir", "hey", "coucou"
            ],
            "patterns": [
                r"^(bonjour|salut|hello|hi|bonsoir)"
            ]
        },
        "HELP": {
            "keywords": [
                "aide", "help", "comment", "how",
                "peux-tu", "can you", "sais-tu"
            ],
            "patterns": [
                r"(aide|help).*moi",
                r"comment.*faire",
                r"peux-tu.*expliquer"
            ]
        }
    }

    # Sub-intents for QUERY_INVOICE
    SUB_INTENTS_INVOICE = {
        "BY_AMOUNT": ["montant", "amount", "prix", "coût", "€", "euro"],
        "BY_DATE": ["date", "période", "mois", "année", "récent", "ancien"],
        "BY_SUPPLIER": ["fournisseur", "supplier", "plombier", "électricien"],
        "BY_STATUS": ["statut", "status", "validé", "payé", "annulé"],
        "NEEDS_REVIEW": ["révision", "review", "vérifier", "valider"],
        "DUPLICATES": ["doublon", "duplicate", "en double"]
    }

    def __init__(self, llm_service=None):
        """
        Initialize intent classifier

        Args:
            llm_service: Optional LLM service for advanced classification
        """
        self.llm_service = llm_service
        self.logger = logger.bind(service="intent_classifier")

    def classify(
        self,
        message: str,
        conversation_context: Optional[List[ConversationTurn]] = None
    ) -> Dict[str, float]:
        """
        Classify user intent with multi-label support

        Args:
            message: User message
            conversation_context: Previous conversation turns

        Returns:
            Dict of intent -> confidence score
            Example: {"QUERY_INVOICE": 0.95, "QUERY_STATS": 0.40}
        """
        message_lower = message.lower().strip()

        # 1. Keyword and pattern matching
        scores = self._keyword_pattern_matching(message_lower)

        # 2. Context enhancement
        if conversation_context:
            scores = self._enhance_with_context(scores, message_lower, conversation_context)

        # 3. Normalize scores
        scores = self._normalize_scores(scores)

        self.logger.info(
            "intent_classified",
            message_preview=message[:50],
            top_intent=max(scores.items(), key=lambda x: x[1])[0] if scores else None,
            top_score=max(scores.values()) if scores else 0
        )

        return scores

    def _keyword_pattern_matching(self, message: str) -> Dict[str, float]:
        """
        Match keywords and regex patterns

        Returns:
            Dict of intent -> raw score
        """
        scores = {}

        for intent, config in self.INTENT_PATTERNS.items():
            score = 0.0

            # Keyword matching
            for keyword in config["keywords"]:
                if keyword in message:
                    score += 0.3  # Each keyword adds 0.3

            # Pattern matching
            for pattern in config.get("patterns", []):
                if re.search(pattern, message):
                    score += 0.5  # Each pattern adds 0.5

            if score > 0:
                scores[intent] = score

        return scores

    def _enhance_with_context(
        self,
        scores: Dict[str, float],
        message: str,
        context: List[ConversationTurn]
    ) -> Dict[str, float]:
        """
        Enhance scores using conversation context

        Args:
            scores: Current scores
            message: User message
            context: Previous turns

        Returns:
            Enhanced scores
        """
        if not context:
            return scores

        last_turn = context[-1]

        # If last response was clarification, inherit intent
        if last_turn.response_type == "clarification":
            original_intent = last_turn.detected_intent
            if original_intent:
                scores[original_intent] = scores.get(original_intent, 0) + 0.4

        # If user is providing clarification
        clarification_words = ["oui", "non", "plutôt", "en fait", "si"]
        if any(word in message for word in clarification_words):
            scores["CLARIFICATION"] = scores.get("CLARIFICATION", 0) + 0.5

            # If clarifying, boost last intent
            if last_turn.detected_intent:
                scores[last_turn.detected_intent] = scores.get(last_turn.detected_intent, 0) + 0.3

        # Reference resolution ("ça", "il", "elle", "la", "le")
        reference_words = ["ça", "il", "elle", "la", "le", "this", "that"]
        if any(word in message.split() for word in reference_words):
            # User is likely referring to last mentioned topic
            if last_turn.detected_intent:
                scores[last_turn.detected_intent] = scores.get(last_turn.detected_intent, 0) + 0.2

        return scores

    def _normalize_scores(self, scores: Dict[str, float]) -> Dict[str, float]:
        """
        Normalize scores to 0-1 range

        Args:
            scores: Raw scores

        Returns:
            Normalized scores
        """
        if not scores:
            return {"OTHER": 1.0}

        # Cap at 1.0
        normalized = {k: min(v, 1.0) for k, v in scores.items()}

        return normalized

    def detect_sub_intents(
        self,
        message: str,
        primary_intent: str
    ) -> List[str]:
        """
        Detect sub-intents for primary intent

        Args:
            message: User message
            primary_intent: Primary intent detected

        Returns:
            List of sub-intents
        """
        message_lower = message.lower()
        sub_intents = []

        if primary_intent == "QUERY_INVOICE":
            for sub_intent, keywords in self.SUB_INTENTS_INVOICE.items():
                if any(kw in message_lower for kw in keywords):
                    sub_intents.append(sub_intent)

        return sub_intents

    def should_ask_clarification(
        self,
        scores: Dict[str, float],
        threshold: float = 0.75
    ) -> Tuple[bool, Optional[str]]:
        """
        Determine if clarification is needed

        Args:
            scores: Intent scores
            threshold: Confidence threshold

        Returns:
            (should_clarify, clarification_question)
        """
        if not scores:
            return True, "Je n'ai pas compris. Pouvez-vous reformuler ?"

        top_score = max(scores.values())
        top_intents = [k for k, v in scores.items() if v == top_score]

        # Low confidence
        if top_score < threshold:
            return True, f"Voulez-vous dire {self._intent_to_french(top_intents[0])} ?"

        # Multiple intents with similar scores (ambiguous)
        high_scores = [k for k, v in scores.items() if v >= threshold - 0.1]
        if len(high_scores) > 1:
            options = " ou ".join([self._intent_to_french(i) for i in high_scores[:2]])
            return True, f"Voulez-vous {options} ?"

        return False, None

    def _intent_to_french(self, intent: str) -> str:
        """Convert intent code to French description"""
        mapping = {
            "QUERY_INVOICE": "consulter des factures",
            "QUERY_SUPPLIER": "voir des fournisseurs",
            "QUERY_STATS": "voir des statistiques",
            "QUERY_DOCUMENT": "rechercher un document",
            "ACTION_CREATE": "créer quelque chose",
            "ACTION_UPDATE": "modifier quelque chose",
            "ACTION_DELETE": "supprimer quelque chose",
            "HELP": "obtenir de l'aide"
        }
        return mapping.get(intent, intent.lower())
