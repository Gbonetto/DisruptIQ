"""
Conversation Title Generation Service
Generates concise, descriptive titles for conversations using LLM
"""

import structlog
from typing import List, Dict
from app.services.llm_service import LLMService

logger = structlog.get_logger()


class ConversationTitleService:
    """
    Service for generating conversation titles using LLM

    Analyzes first 2-3 message exchanges to create:
    - Concise titles (3-6 words max)
    - Descriptive of conversation topic
    - User-friendly and clear
    """

    def __init__(self):
        self.llm_service = LLMService()
        logger.info("conversation_title_service_initialized")

    async def generate_title(self, messages: List[Dict[str, str]], max_length: int = 50) -> str:
        """
        Generate conversation title from first few messages

        Args:
            messages: List of conversation messages (dicts with role, content)
            max_length: Maximum title length in characters

        Returns:
            Generated title (concise, descriptive)
        """
        try:
            if not messages:
                return "Nouvelle conversation"

            # Use first 3 exchanges (6 messages: 3 user + 3 assistant)
            first_messages = messages[:6]

            # If only 1 message, use simple truncation
            if len(first_messages) <= 1:
                first_content = first_messages[0].get("content", "")
                title = first_content[:max_length]
                if len(first_content) > max_length:
                    title += "..."
                return title

            # Build context from messages
            conversation_context = []
            for msg in first_messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                # Truncate long messages for context
                truncated = content[:200] if len(content) > 200 else content
                conversation_context.append(f"{role.upper()}: {truncated}")

            context_str = "\n".join(conversation_context)

            # LLM prompt for title generation
            prompt = f"""
Génère un titre court et descriptif pour cette conversation.

CONVERSATION:
{context_str}

RÈGLES POUR LE TITRE:
1. Maximum 50 caractères (idéalement 3-6 mots)
2. Résume le sujet principal de la conversation
3. Utilise un langage naturel et clair
4. Évite les articles inutiles ("le", "la", "un", "une") au début
5. Commence par une majuscule
6. Pas de guillemets ni de ponctuation finale
7. Sois spécifique et informatif

EXEMPLES DE BONS TITRES:
- "Recherche de plombiers à Lyon"
- "Copropriétaires des Mimosas"
- "Analyse du contrat de maintenance"
- "Demande devis travaux électriques"
- "Emails urgents du 15 janvier"
- "Contact copropriétaires pour AG"
- "Tarifs et conditions syndic"
- "Procédure dégât des eaux"

EXEMPLES DE MAUVAIS TITRES:
- "L'utilisateur demande..." (trop descriptif)
- "Conversation sur les plombiers à Lyon en France" (trop long)
- "plombiers" (pas assez descriptif)
- "Une question sur le prix du plombier ?" (ponctuation, article)

GÉNÈRE LE TITRE (réponds UNIQUEMENT avec le titre, rien d'autre):
"""

            # Call LLM
            title = await self.llm_service.generate_response(
                prompt=prompt,
                max_tokens=30,  # Short response
                temperature=0.3  # Somewhat creative but controlled
            )

            # Clean up response
            title = title.strip()

            # Remove quotes if present
            if title.startswith('"') and title.endswith('"'):
                title = title[1:-1]
            if title.startswith("'") and title.endswith("'"):
                title = title[1:-1]

            # Remove trailing punctuation
            title = title.rstrip(".!?;:,")

            # Capitalize first letter
            if title:
                title = title[0].upper() + title[1:]

            # Enforce max length
            if len(title) > max_length:
                title = title[:max_length].rsplit(' ', 1)[0] + "..."

            # Fallback to simple title if empty or too short
            if not title or len(title) < 5:
                logger.warning("title_generation_invalid", generated=title)
                first_content = first_messages[0].get("content", "")
                title = first_content[:max_length]
                if len(first_content) > max_length:
                    title += "..."

            logger.info("title_generated", title=title, message_count=len(first_messages))
            return title

        except Exception as e:
            logger.error("title_generation_failed", error=str(e), exc_info=True)
            # Fallback to simple truncation
            if messages:
                first_content = messages[0].get("content", "Nouvelle conversation")
                return first_content[:max_length] + ("..." if len(first_content) > max_length else "")
            return "Nouvelle conversation"


# Singleton instance
_title_service: ConversationTitleService = None


def get_title_service() -> ConversationTitleService:
    """Get or create singleton title service instance"""
    global _title_service
    if _title_service is None:
        _title_service = ConversationTitleService()
    return _title_service
