"""
Suggestion Engine - Génération de suggestions proactives

Génère des suggestions intelligentes après chaque réponse pour
guider l'utilisateur vers les prochaines actions pertinentes.

Types de suggestions:
- Filter: Raffiner les résultats
- Drill-down: Plus de détails
- Related: Entités liées
- Action: Actions possibles

Usage:
    engine = SuggestionEngine()
    suggestions = engine.generate_suggestions(
        intent="QUERY_INVOICE",
        query_result={...},
        user_profile=profile
    )
"""

from typing import List, Dict, Optional, Any
from enum import Enum
import structlog

from app.models.conversation import UserProfile

logger = structlog.get_logger(__name__)


class SuggestionType(str, Enum):
    """Types de suggestions"""
    FILTER = "filter"           # Raffiner les résultats
    DRILL_DOWN = "drill_down"   # Voir plus de détails
    RELATED = "related"         # Voir entités liées
    ACTION = "action"           # Effectuer une action
    ANALYSIS = "analysis"       # Analyser les données


class Suggestion:
    """Représente une suggestion"""

    def __init__(
        self,
        type: SuggestionType,
        text: str,
        query: Optional[str] = None,
        action: Optional[str] = None,
        params: Optional[Dict] = None,
        priority: int = 0
    ):
        self.type = type
        self.text = text
        self.query = query
        self.action = action
        self.params = params or {}
        self.priority = priority

    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dict pour JSON"""
        return {
            "type": self.type,
            "text": self.text,
            "query": self.query,
            "action": self.action,
            "params": self.params,
            "priority": self.priority
        }


class SuggestionEngine:
    """
    Génère des suggestions intelligentes contextuelles
    """

    def __init__(self):
        self.logger = logger.bind(service="suggestion_engine")

    def generate_suggestions(
        self,
        intent: str,
        query_result: Optional[Dict[str, Any]] = None,
        user_profile: Optional[UserProfile] = None,
        extracted_entities: Optional[Dict[str, Any]] = None,
        max_suggestions: int = 3
    ) -> List[Suggestion]:
        """
        Génère des suggestions basées sur le contexte

        Args:
            intent: Intent détecté
            query_result: Résultat de la requête
            user_profile: Profil utilisateur
            extracted_entities: Entités extraites
            max_suggestions: Nombre max de suggestions

        Returns:
            Liste de suggestions triées par pertinence
        """
        suggestions = []

        # Generate intent-specific suggestions
        if intent == "QUERY_INVOICE":
            suggestions.extend(self._suggest_for_invoice_query(query_result, extracted_entities))
        elif intent == "QUERY_SUPPLIER":
            suggestions.extend(self._suggest_for_supplier_query(query_result))
        elif intent == "QUERY_STATS":
            suggestions.extend(self._suggest_for_stats_query(query_result))
        elif intent == "ACTION_CREATE":
            suggestions.extend(self._suggest_after_create())
        elif intent == "ACTION_UPDATE":
            suggestions.extend(self._suggest_after_update())

        # Add personalized suggestions from user profile
        if user_profile:
            suggestions.extend(self._suggest_from_profile(user_profile, intent))

        # Rank and limit
        suggestions = self._rank_suggestions(suggestions)
        return suggestions[:max_suggestions]

    def _suggest_for_invoice_query(
        self,
        query_result: Optional[Dict],
        extracted_entities: Optional[Dict]
    ) -> List[Suggestion]:
        """Suggestions pour les requêtes de factures"""
        suggestions = []

        # If many results, suggest filtering
        if query_result and query_result.get("count", 0) > 10:
            suggestions.append(Suggestion(
                type=SuggestionType.FILTER,
                text="Voir seulement celles en attente",
                query="Factures en attente",
                priority=10
            ))

            suggestions.append(Suggestion(
                type=SuggestionType.FILTER,
                text="Filtrer par montant (> 500€)",
                query="Factures supérieures à 500€",
                priority=8
            ))

        # Suggest drill-down
        suggestions.append(Suggestion(
            type=SuggestionType.DRILL_DOWN,
            text="Voir le détail d'une facture",
            query="Détails de la facture [numero]",
            priority=7
        ))

        # Suggest related analysis
        suggestions.append(Suggestion(
            type=SuggestionType.ANALYSIS,
            text="Analyser les montants par mois",
            query="Total des factures par mois",
            priority=9
        ))

        # If no amount filter yet, suggest it
        if not extracted_entities or not extracted_entities.get("amounts"):
            suggestions.append(Suggestion(
                type=SuggestionType.FILTER,
                text="Filtrer par montant",
                query="Factures entre 100 et 1000€",
                priority=6
            ))

        # Suggest related entities
        suggestions.append(Suggestion(
            type=SuggestionType.RELATED,
            text="Voir les fournisseurs associés",
            query="Fournisseurs de ces factures",
            priority=5
        ))

        return suggestions

    def _suggest_for_supplier_query(
        self,
        query_result: Optional[Dict]
    ) -> List[Suggestion]:
        """Suggestions pour les requêtes de fournisseurs"""
        suggestions = []

        # Suggest seeing invoices
        suggestions.append(Suggestion(
            type=SuggestionType.RELATED,
            text="Voir les factures de ce fournisseur",
            query="Factures du fournisseur [name]",
            priority=10
        ))

        # Suggest filtering
        suggestions.append(Suggestion(
            type=SuggestionType.FILTER,
            text="Voir seulement les fournisseurs actifs",
            query="Fournisseurs actifs",
            priority=8
        ))

        # Suggest analysis
        suggestions.append(Suggestion(
            type=SuggestionType.ANALYSIS,
            text="Analyser les dépenses par fournisseur",
            query="Total des dépenses par fournisseur",
            priority=7
        ))

        return suggestions

    def _suggest_for_stats_query(
        self,
        query_result: Optional[Dict]
    ) -> List[Suggestion]:
        """Suggestions pour les statistiques"""
        suggestions = []

        # Suggest drilling down
        suggestions.append(Suggestion(
            type=SuggestionType.DRILL_DOWN,
            text="Voir le détail des données",
            query="Détail des factures",
            priority=9
        ))

        # Suggest different grouping
        suggestions.append(Suggestion(
            type=SuggestionType.ANALYSIS,
            text="Grouper par catégorie",
            query="Total par catégorie de service",
            priority=8
        ))

        suggestions.append(Suggestion(
            type=SuggestionType.ANALYSIS,
            text="Comparer avec l'année précédente",
            query="Évolution par rapport à l'année dernière",
            priority=7
        ))

        return suggestions

    def _suggest_after_create(self) -> List[Suggestion]:
        """Suggestions après création"""
        suggestions = []

        suggestions.append(Suggestion(
            type=SuggestionType.ACTION,
            text="Voir l'élément créé",
            action="view_created",
            priority=10
        ))

        suggestions.append(Suggestion(
            type=SuggestionType.ACTION,
            text="Créer un autre élément",
            action="create_another",
            priority=7
        ))

        suggestions.append(Suggestion(
            type=SuggestionType.RELATED,
            text="Voir la liste complète",
            query="Liste complète",
            priority=5
        ))

        return suggestions

    def _suggest_after_update(self) -> List[Suggestion]:
        """Suggestions après modification"""
        suggestions = []

        suggestions.append(Suggestion(
            type=SuggestionType.ACTION,
            text="Voir l'élément modifié",
            action="view_updated",
            priority=10
        ))

        suggestions.append(Suggestion(
            type=SuggestionType.RELATED,
            text="Voir les autres éléments",
            query="Liste des éléments",
            priority=6
        ))

        return suggestions

    def _suggest_from_profile(
        self,
        user_profile: UserProfile,
        current_intent: str
    ) -> List[Suggestion]:
        """
        Génère des suggestions basées sur l'historique utilisateur

        Args:
            user_profile: Profil utilisateur
            current_intent: Intent actuel

        Returns:
            Suggestions personnalisées
        """
        suggestions = []

        # Suggest based on common intents
        if user_profile.most_common_intents:
            # Get top 2 most common intents (excluding current)
            top_intents = sorted(
                user_profile.most_common_intents.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]

            for intent, count in top_intents:
                if intent != current_intent:
                    # Add suggestion based on this intent
                    if intent == "QUERY_INVOICE":
                        suggestions.append(Suggestion(
                            type=SuggestionType.RELATED,
                            text="Voir vos factures habituelles",
                            query="Mes factures récentes",
                            priority=6
                        ))
                    elif intent == "QUERY_STATS":
                        suggestions.append(Suggestion(
                            type=SuggestionType.ANALYSIS,
                            text="Voir les statistiques",
                            query="Statistiques du mois",
                            priority=5
                        ))

        # Suggest based on favorite queries
        if user_profile.favorite_queries:
            # Suggest repeating a favorite query
            if len(user_profile.favorite_queries) > 0:
                fav = user_profile.favorite_queries[0]
                suggestions.append(Suggestion(
                    type=SuggestionType.RELATED,
                    text=f"Répéter: {fav[:40]}...",
                    query=fav,
                    priority=4
                ))

        return suggestions

    def _rank_suggestions(self, suggestions: List[Suggestion]) -> List[Suggestion]:
        """
        Trie les suggestions par pertinence

        Args:
            suggestions: Liste de suggestions

        Returns:
            Liste triée
        """
        # Sort by priority (descending)
        return sorted(suggestions, key=lambda s: s.priority, reverse=True)

    def suggest_quick_actions(
        self,
        context: Dict[str, Any]
    ) -> List[Suggestion]:
        """
        Génère des actions rapides contextuelles

        Args:
            context: Contexte de la conversation

        Returns:
            Liste d'actions rapides
        """
        actions = []

        # Common quick actions
        actions.append(Suggestion(
            type=SuggestionType.ACTION,
            text="📊 Voir le tableau de bord",
            action="dashboard",
            priority=10
        ))

        actions.append(Suggestion(
            type=SuggestionType.ACTION,
            text="🔍 Recherche avancée",
            action="advanced_search",
            priority=8
        ))

        actions.append(Suggestion(
            type=SuggestionType.ACTION,
            text="❓ Aide",
            action="help",
            priority=5
        ))

        return actions


# Convenience function
def generate_suggestions_for_intent(
    intent: str,
    result: Optional[Dict] = None,
    user_profile: Optional[UserProfile] = None
) -> List[Dict[str, Any]]:
    """
    Helper function pour générer rapidement des suggestions

    Args:
        intent: Intent détecté
        result: Résultat de la requête
        user_profile: Profil utilisateur

    Returns:
        Liste de dicts de suggestions
    """
    engine = SuggestionEngine()
    suggestions = engine.generate_suggestions(intent, result, user_profile)
    return [s.to_dict() for s in suggestions]
