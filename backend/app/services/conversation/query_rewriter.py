"""
Query Rewriter - Reformulation contextuelle des requêtes

Reformule les requêtes utilisateur pour les rendre auto-suffisantes
en utilisant le contexte de conversation.

Cas d'usage:
- Résolution de références: "celles" → "les factures"
- Héritage de contexte: "Et février aussi" → "Factures de janvier et février"
- Enrichissement: "Seulement > 500€" → "Factures de plomberie > 500€"

Usage:
    rewriter = QueryRewriter(llm_service)
    rewritten = await rewriter.rewrite(message, context)
"""

from typing import List, Optional, Dict, Any
import structlog

from app.models.conversation import ConversationTurn
from app.services.llm_service import LLMService

logger = structlog.get_logger(__name__)


class QueryRewriter:
    """
    Reformule les requêtes en utilisant le contexte conversationnel

    Résout les références et rend les requêtes auto-suffisantes
    """

    # Mots de référence courants
    REFERENCE_WORDS = {
        "celles", "ceux", "celui", "celle",
        "il", "elle", "ils", "elles",
        "le", "la", "les",
        "ça", "cela", "celui-ci", "celle-ci",
        "premier", "première", "dernier", "dernière",
        "précédent", "précédente", "suivant", "suivante",
    }

    # Mots de continuation/ajout
    CONTINUATION_WORDS = {
        "aussi", "également", "en plus",
        "et", "ainsi que",
        "plus", "encore",
    }

    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Initialise le rewriter

        Args:
            llm_service: Service LLM pour reformulation intelligente
        """
        self.llm_service = llm_service
        self.logger = logger.bind(service="query_rewriter")

    def needs_rewriting(self, message: str) -> bool:
        """
        Détermine si la requête nécessite une reformulation

        Args:
            message: Message utilisateur

        Returns:
            True si la requête contient des références ou est incomplète
        """
        message_lower = message.lower()

        # Check for reference words
        has_reference = any(
            f" {word} " in f" {message_lower} " or message_lower.startswith(f"{word} ")
            for word in self.REFERENCE_WORDS
        )

        # Check for continuation words
        has_continuation = any(
            word in message_lower
            for word in self.CONTINUATION_WORDS
        )

        # Check if message is very short (likely incomplete)
        is_short = len(message.split()) <= 5

        return has_reference or (has_continuation and is_short)

    async def rewrite(
        self,
        message: str,
        context: Optional[List[ConversationTurn]] = None,
        extracted_entities: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Reformule la requête avec le contexte

        Args:
            message: Message original
            context: Historique de conversation
            extracted_entities: Entités extraites du message

        Returns:
            Message reformulé auto-suffisant
        """
        # Si pas de contexte, retourner le message original
        if not context or len(context) == 0:
            self.logger.debug("no_context_skipping_rewrite")
            return message

        # Si pas besoin de réécriture, retourner original
        if not self.needs_rewriting(message):
            self.logger.debug("no_rewrite_needed", message=message[:50])
            return message

        # Use LLM for intelligent rewriting
        if self.llm_service:
            try:
                rewritten = await self._rewrite_with_llm(message, context, extracted_entities)
                self.logger.info(
                    "query_rewritten",
                    original=message[:50],
                    rewritten=rewritten[:50]
                )
                return rewritten
            except Exception as e:
                self.logger.error("llm_rewrite_error", error=str(e), exc_info=True)
                # Fallback to pattern-based rewriting
                return self._rewrite_with_patterns(message, context)
        else:
            # Pattern-based rewriting as fallback
            return self._rewrite_with_patterns(message, context)

    async def _rewrite_with_llm(
        self,
        message: str,
        context: List[ConversationTurn],
        extracted_entities: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Reformule avec le LLM pour une compréhension avancée

        Args:
            message: Message original
            context: Contexte conversationnel
            extracted_entities: Entités extraites

        Returns:
            Message reformulé
        """
        # Format context for LLM
        context_text = self._format_context_for_llm(context)

        # Format entities if available
        entities_text = ""
        if extracted_entities:
            entities_text = self._format_entities_for_llm(extracted_entities)

        prompt = f"""Tu es un système de reformulation de requêtes pour un logiciel de gestion de copropriété.

Contexte de conversation récente:
{context_text}

{entities_text}

Message actuel (incomplet): "{message}"

Ta tâche: Reformule ce message pour le rendre auto-suffisant (self-contained) en utilisant le contexte.

Règles:
1. Remplace les références (il, elle, ça, celles, etc.) par les entités réelles du contexte
2. Hérite des filtres/contraintes du contexte si le message les sous-entend
3. Garde le même niveau de détail (ne pas sur-spécifier)
4. Si le message contient "aussi", "et", "en plus", ajoute au contexte précédent
5. Garde le français naturel et fluide
6. Réponds UNIQUEMENT avec la requête reformulée, sans explication

Exemples:
- Contexte: "Montre les factures de plomberie"
- Message: "Seulement celles > 500€"
- Reformulé: "Montre les factures de plomberie supérieures à 500€"

- Contexte: "Factures de janvier"
- Message: "Et février aussi"
- Reformulé: "Factures de janvier et février"

- Contexte: "Qui est le plombier actif?"
- Message: "Ses factures"
- Reformulé: "Factures du plombier actif"

Requête reformulée:"""

        # Call LLM
        response = await self.llm_service.generate_async(
            prompt=prompt,
            max_tokens=150,
            temperature=0.2  # Low temperature for consistent rewriting
        )

        # Clean response (remove quotes, extra whitespace)
        rewritten = response.strip().strip('"').strip("'")

        return rewritten

    def _rewrite_with_patterns(
        self,
        message: str,
        context: List[ConversationTurn]
    ) -> str:
        """
        Reformule avec des patterns simples (fallback)

        Args:
            message: Message original
            context: Contexte

        Returns:
            Message reformulé
        """
        # Get last turn
        if not context:
            return message

        last_turn = context[-1]
        last_user_message = last_turn.user_message.lower()

        rewritten = message

        # Simple reference resolution
        if any(ref in message.lower() for ref in ["celles", "ceux"]):
            # Extract noun from last message
            if "facture" in last_user_message:
                rewritten = message.lower().replace("celles", "les factures")
                rewritten = rewritten.replace("ceux", "les factures")
            elif "fournisseur" in last_user_message:
                rewritten = message.lower().replace("celles", "les fournisseurs")
                rewritten = rewritten.replace("ceux", "les fournisseurs")

        # Continuation: "et X aussi"
        if "aussi" in message.lower() or ("et" in message.lower() and len(message.split()) < 6):
            # Append to last query
            base = last_user_message.replace("montre", "").replace("liste", "").strip()
            rewritten = f"{base} {message}"

        return rewritten.capitalize()

    def _format_context_for_llm(self, context: List[ConversationTurn]) -> str:
        """
        Formate le contexte pour le LLM

        Args:
            context: Tours de conversation

        Returns:
            Contexte formaté
        """
        # Take last 3 turns
        recent = context[-3:] if len(context) > 3 else context

        lines = []
        for i, turn in enumerate(recent):
            lines.append(f"Tour {i+1}:")
            lines.append(f"  User: {turn.user_message}")
            lines.append(f"  Intent: {turn.detected_intent}")
            if turn.extracted_entities:
                lines.append(f"  Entities: {turn.extracted_entities}")
            lines.append("")

        return "\n".join(lines)

    def _format_entities_for_llm(self, entities: Dict[str, Any]) -> str:
        """
        Formate les entités extraites pour le LLM

        Args:
            entities: Dict d'entités

        Returns:
            Texte formaté
        """
        lines = ["Entités détectées dans le message actuel:"]

        if entities.get("amounts"):
            for amt in entities["amounts"]:
                if amt["type"] == "range":
                    lines.append(f"  - Montant: entre {amt['min']}€ et {amt['max']}€")
                elif amt["type"] == "comparison":
                    lines.append(f"  - Montant: {amt['operator']} {amt['value']}€")

        if entities.get("dates"):
            for date in entities["dates"]:
                lines.append(f"  - Date: {date['text']}")

        if entities.get("categories"):
            lines.append(f"  - Catégories: {', '.join(entities['categories'])}")

        if entities.get("statuses"):
            lines.append(f"  - Statuts: {', '.join(entities['statuses'])}")

        return "\n".join(lines) if len(lines) > 1 else ""

    def extract_refinement_intent(
        self,
        message: str,
        context: List[ConversationTurn]
    ) -> Optional[str]:
        """
        Détermine si le message est un raffinement du contexte précédent

        Args:
            message: Message utilisateur
            context: Contexte

        Returns:
            Type de raffinement: "filter", "expand", "clarify", None
        """
        if not context:
            return None

        message_lower = message.lower()

        # Filter refinement: "seulement", "uniquement", "juste"
        if any(word in message_lower for word in ["seulement", "uniquement", "juste", "que"]):
            return "filter"

        # Expansion: "aussi", "en plus", "et"
        if any(word in message_lower for word in ["aussi", "également", "en plus", "et"]):
            return "expand"

        # Clarification: "je veux dire", "plutôt", "en fait"
        if any(word in message_lower for word in ["je veux dire", "plutôt", "en fait", "non"]):
            return "clarify"

        return None


# Convenience function
async def rewrite_query(
    message: str,
    context: List[ConversationTurn],
    llm_service: Optional[LLMService] = None,
    entities: Optional[Dict[str, Any]] = None
) -> str:
    """
    Helper function pour réécrire rapidement

    Args:
        message: Message original
        context: Contexte
        llm_service: Service LLM optionnel
        entities: Entités extraites

    Returns:
        Message reformulé
    """
    rewriter = QueryRewriter(llm_service)
    return await rewriter.rewrite(message, context, entities)
