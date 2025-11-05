"""
Response Adapter - Adaptation des réponses selon le profil utilisateur

Adapte les réponses du système en fonction de:
- Niveau d'expertise (débutant, intermédiaire, expert)
- Style de réponse préféré (concis, détaillé)
- Langue et ton

Usage:
    adapter = ResponseAdapter()
    adapted = adapter.adapt_response(
        response="Voici les résultats...",
        user_profile=profile,
        intent="QUERY_INVOICE"
    )
"""

from typing import Dict, Optional, Any
from enum import Enum
import structlog

from app.models.conversation import UserProfile

logger = structlog.get_logger(__name__)


class ExpertiseLevel(str, Enum):
    """Niveaux d'expertise utilisateur"""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"


class ResponseStyle(str, Enum):
    """Styles de réponse"""
    CONCISE = "concise"
    DETAILED = "detailed"
    TECHNICAL = "technical"


class ResponseAdapter:
    """
    Adapte les réponses selon le profil utilisateur
    """

    # Ajouts pour débutants par intent
    BEGINNER_EXPLANATIONS = {
        "QUERY_INVOICE": "\n\n💡 Astuce: Vous pouvez filtrer par montant, date ou fournisseur. Par exemple: 'Factures supérieures à 500€'",
        "QUERY_SUPPLIER": "\n\n💡 Astuce: Vous pouvez voir les factures d'un fournisseur en disant: 'Factures de [nom du fournisseur]'",
        "QUERY_STATS": "\n\n💡 Astuce: Vous pouvez grouper les statistiques par mois, catégorie ou fournisseur.",
        "ACTION_CREATE": "\n\n💡 Info: La facture sera créée avec les informations fournies. Vous pourrez la modifier ensuite.",
        "ACTION_UPDATE": "\n\n💡 Info: Les modifications seront sauvegardées immédiatement.",
    }

    # Raccourcis pour experts
    EXPERT_SHORTCUTS = {
        "QUERY_INVOICE": "\n\n⚡ Commandes rapides: 'f>500', 'f:plomberie', 'f@janvier'",
        "QUERY_SUPPLIER": "\n\n⚡ Commandes rapides: 's:actif', 's@plomberie'",
    }

    def __init__(self):
        self.logger = logger.bind(service="response_adapter")

    def adapt_response(
        self,
        response: str,
        user_profile: Optional[UserProfile] = None,
        intent: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Adapte la réponse selon le profil utilisateur

        Args:
            response: Réponse originale
            user_profile: Profil utilisateur
            intent: Intent détecté
            context: Contexte additionnel

        Returns:
            Réponse adaptée
        """
        if not user_profile:
            # No profile, return original
            return response

        adapted = response

        # Adapt by expertise level
        expertise = user_profile.expertise_level or "beginner"
        if expertise == ExpertiseLevel.BEGINNER:
            adapted = self._adapt_for_beginner(adapted, intent)
        elif expertise == ExpertiseLevel.EXPERT:
            adapted = self._adapt_for_expert(adapted, intent)

        # Adapt by response style
        style = user_profile.preferred_response_style or "detailed"
        if style == ResponseStyle.CONCISE:
            adapted = self._make_concise(adapted)
        elif style == ResponseStyle.DETAILED and len(adapted) < 100:
            adapted = self._add_details(adapted, intent)

        self.logger.debug(
            "response_adapted",
            expertise=expertise,
            style=style,
            original_length=len(response),
            adapted_length=len(adapted)
        )

        return adapted

    def _adapt_for_beginner(self, response: str, intent: Optional[str]) -> str:
        """
        Ajoute des explications pour les débutants

        Args:
            response: Réponse originale
            intent: Intent détecté

        Returns:
            Réponse avec explications
        """
        # Add explanation if available for this intent
        if intent and intent in self.BEGINNER_EXPLANATIONS:
            explanation = self.BEGINNER_EXPLANATIONS[intent]
            return f"{response}{explanation}"

        return response

    def _adapt_for_expert(self, response: str, intent: Optional[str]) -> str:
        """
        Ajoute des raccourcis pour les experts

        Args:
            response: Réponse originale
            intent: Intent détecté

        Returns:
            Réponse avec raccourcis
        """
        # Remove beginner-friendly language
        # "Voici les résultats" → "Résultats"
        response = response.replace("Voici les résultats:", "Résultats:")
        response = response.replace("Voici la liste", "Liste")

        # Add shortcuts if available
        if intent and intent in self.EXPERT_SHORTCUTS:
            shortcuts = self.EXPERT_SHORTCUTS[intent]
            return f"{response}{shortcuts}"

        return response

    def _make_concise(self, response: str) -> str:
        """
        Rend la réponse plus concise

        Args:
            response: Réponse originale

        Returns:
            Réponse concise
        """
        # Remove filler words
        concise = response
        concise = concise.replace("Voici les résultats de votre recherche:", "Résultats:")
        concise = concise.replace("Voici ce que j'ai trouvé:", "Trouvé:")
        concise = concise.replace("Je vous présente", "")
        concise = concise.replace("Permettez-moi de", "")

        # Remove unnecessary courtesy
        concise = concise.replace("s'il vous plaît", "")
        concise = concise.replace("Merci de votre patience", "")

        # Truncate if too long (keep first 300 chars + "...")
        if len(concise) > 400:
            concise = concise[:300] + "..."

        return concise.strip()

    def _add_details(self, response: str, intent: Optional[str]) -> str:
        """
        Ajoute des détails si la réponse est trop courte

        Args:
            response: Réponse originale
            intent: Intent détecté

        Returns:
            Réponse détaillée
        """
        # If response is very short, add context
        if len(response) < 50:
            if intent == "QUERY_INVOICE":
                response += "\n\nCette recherche porte sur les factures de votre copropriété."
            elif intent == "QUERY_SUPPLIER":
                response += "\n\nCette liste contient les fournisseurs enregistrés."

        return response

    def format_results_list(
        self,
        items: list,
        user_profile: Optional[UserProfile] = None,
        max_items: Optional[int] = None
    ) -> str:
        """
        Formate une liste de résultats selon le profil

        Args:
            items: Liste d'items à formater
            user_profile: Profil utilisateur
            max_items: Nombre max d'items à afficher

        Returns:
            Liste formatée
        """
        if not items:
            return "Aucun résultat trouvé."

        # Determine how many items to show
        if user_profile:
            style = user_profile.preferred_response_style or "detailed"
            if style == ResponseStyle.CONCISE:
                max_items = max_items or 5
            else:
                max_items = max_items or 10
        else:
            max_items = max_items or 10

        # Format items
        shown = items[:max_items]
        lines = [f"Trouvé {len(items)} résultat(s):\n"]

        for i, item in enumerate(shown, 1):
            if isinstance(item, dict):
                # Format dict items
                key_field = self._get_primary_field(item)
                lines.append(f"{i}. {item.get(key_field, 'Item')}")
            else:
                lines.append(f"{i}. {item}")

        # Add "... and X more"
        if len(items) > max_items:
            remaining = len(items) - max_items
            lines.append(f"\n... et {remaining} autre(s)")

        return "\n".join(lines)

    def _get_primary_field(self, item: dict) -> str:
        """
        Détermine le champ principal d'un dict

        Args:
            item: Dict item

        Returns:
            Nom du champ principal
        """
        # Common primary fields
        for field in ["name", "title", "label", "id", "numero"]:
            if field in item:
                return field

        # Fallback to first key
        return list(item.keys())[0] if item else "value"

    def add_action_buttons(
        self,
        response: str,
        actions: list[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Ajoute des boutons d'action à la réponse

        Args:
            response: Réponse textuelle
            actions: Liste d'actions {label, value, type}

        Returns:
            Dict avec response + actions
        """
        return {
            "message": response,
            "actions": actions,
            "has_actions": len(actions) > 0
        }

    def format_error(
        self,
        error_message: str,
        user_profile: Optional[UserProfile] = None
    ) -> str:
        """
        Formate un message d'erreur selon le profil

        Args:
            error_message: Message d'erreur brut
            user_profile: Profil utilisateur

        Returns:
            Message d'erreur formaté
        """
        # For beginners, add more context
        if user_profile and user_profile.expertise_level == ExpertiseLevel.BEGINNER:
            return f"❌ Désolé, une erreur s'est produite: {error_message}\n\n💡 Essayez de reformuler votre demande ou demandez de l'aide."

        # For experts, be concise
        if user_profile and user_profile.expertise_level == ExpertiseLevel.EXPERT:
            return f"❌ Erreur: {error_message}"

        # Default
        return f"Une erreur s'est produite: {error_message}"


# Convenience function
def adapt_response_for_user(
    response: str,
    user_profile: Optional[UserProfile],
    intent: Optional[str] = None
) -> str:
    """
    Helper function pour adapter rapidement

    Args:
        response: Réponse à adapter
        user_profile: Profil utilisateur
        intent: Intent détecté

    Returns:
        Réponse adaptée
    """
    adapter = ResponseAdapter()
    return adapter.adapt_response(response, user_profile, intent)
