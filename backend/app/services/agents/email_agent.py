"""
Email Agent - Intelligent email generation
Generates personalized emails for property management
"""

import structlog
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.llm_service import LLMService
from app.models.coproprietaire import Coproprietaire

logger = structlog.get_logger()


class EmailAgent:
    """
    Email Agent - Generates personalized emails

    Capabilities:
    - Generate email content from user request
    - Personalize for specific recipients
    - Adapt tone (urgent, professional, friendly)
    - Support templates and variables
    """

    def __init__(self):
        self.llm_service = LLMService()
        logger.info("email_agent_initialized")

    async def generate_email(
        self,
        user_request: str,
        db: AsyncSession,
        recipients: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate email draft from user request

        Args:
            user_request: User's email request (ex: "Envoyer email pour dégât des eaux")
            db: Database session
            recipients: Optional list of recipients

        Returns:
            Dict with success, message, email draft data
        """
        try:
            # Step 1: Extract email purpose and context
            email_context = await self._extract_context(user_request)

            # Step 2: Get recipients if not provided
            if not recipients:
                recipients = await self._get_recipients(user_request, email_context, db)

            # Step 3: Generate email content
            email_draft = await self._generate_content(
                user_request=user_request,
                context=email_context,
                recipients=recipients
            )

            return {
                "success": True,
                "message": f"J'ai généré un brouillon d'email pour {len(recipients)} destinataire(s).",
                "data": {
                    "subject": email_draft["subject"],
                    "body": email_draft["body"],
                    "recipients": recipients,
                    "tone": email_draft["tone"],
                    "urgency": email_draft["urgency"]
                }
            }

        except Exception as e:
            logger.error("email_generation_failed", error=str(e), exc_info=True)
            return {
                "success": False,
                "message": f"Erreur lors de la génération de l'email: {str(e)}"
            }

    async def _extract_context(self, user_request: str) -> Dict[str, Any]:
        """Extract email purpose, tone, urgency from user request"""
        prompt = f"""
Analyse cette demande d'email et extrait les informations clés.

DEMANDE:
{user_request}

Réponds en JSON avec:
{{
    "purpose": "Objectif de l'email (1 phrase)",
    "tone": "professional" ou "urgent" ou "friendly",
    "urgency": "high" ou "medium" ou "low",
    "key_points": ["Point 1", "Point 2", ...]
}}

JSON:
"""

        try:
            response = await self.llm_service.generate_response(
                prompt=prompt,
                max_tokens=300,
                temperature=0.3
            )

            # Parse JSON response
            import json
            context = json.loads(response.strip())

            return context

        except Exception as e:
            logger.error("context_extraction_failed", error=str(e))
            return {
                "purpose": user_request,
                "tone": "professional",
                "urgency": "medium",
                "key_points": []
            }

    async def _get_recipients(
        self,
        user_request: str,
        context: Dict[str, Any],
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Get email recipients from database based on request"""
        # Check if request mentions specific copropriété
        user_request_lower = user_request.lower()

        try:
            # If "tous" or "all" mentioned, get all coproprietaires
            if any(word in user_request_lower for word in ["tous", "tout", "all"]):
                result = await db.execute(select(Coproprietaire))
                coproprietaires = result.scalars().all()

                return [
                    {
                        "name": f"{c.prenom} {c.nom}",
                        "email": c.email,
                        "id": c.id
                    }
                    for c in coproprietaires
                ]

            # Otherwise return empty (will be filled by user or workflow)
            return []

        except Exception as e:
            logger.error("recipients_fetch_failed", error=str(e))
            return []

    async def _generate_content(
        self,
        user_request: str,
        context: Dict[str, Any],
        recipients: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate email subject and body"""
        tone_instructions = {
            "professional": "Ton professionnel et formel",
            "urgent": "Ton urgent mais poli, marquer clairement l'urgence",
            "friendly": "Ton amical et chaleureux"
        }

        prompt = f"""
Génère un email professionnel pour un syndic de copropriété.

CONTEXTE:
- Demande: {user_request}
- Objectif: {context.get('purpose', 'Information')}
- Ton: {tone_instructions.get(context.get('tone', 'professional'))}
- Urgence: {context.get('urgency', 'medium')}
- Points clés: {', '.join(context.get('key_points', []))}
- Nombre de destinataires: {len(recipients)}

RÈGLES CRITIQUES:
⚠️ N'INVENTE AUCUNE INFORMATION qui n'est pas explicitement fournie ci-dessus
⚠️ Si des détails manquent (ampleur des dégâts, cause, solutions, etc.), NE PAS les inventer
⚠️ Utilise des formulations prudentes : "nous évaluons", "nous vous tiendrons informés", "des détails suivront"
⚠️ Ne mentionne PAS d'actions déjà prises si elles ne sont pas explicitement mentionnées dans la demande

Génère:
1. Un SUJET court et clair (max 60 caractères)
2. Un CORPS d'email structuré avec:
   - Formule de politesse adaptée
   - Corps du message clair et professionnel basé UNIQUEMENT sur les informations fournies
   - Points clés bien organisés
   - Signature "Le Syndic"

Format de réponse:
SUJET: [sujet ici]

CORPS:
[corps ici]

Ne pas inclure les adresses emails dans le corps.
"""

        try:
            response = await self.llm_service.generate_response(
                prompt=prompt,
                max_tokens=800,
                temperature=0.6
            )

            # Parse response
            lines = response.strip().split('\n')
            subject = ""
            body_lines = []
            in_body = False

            for line in lines:
                if line.startswith("SUJET:"):
                    subject = line.replace("SUJET:", "").strip()
                elif line.startswith("CORPS:"):
                    in_body = True
                elif in_body:
                    body_lines.append(line)

            body = "\n".join(body_lines).strip()

            return {
                "subject": subject or "Information Copropriété",
                "body": body or response,
                "tone": context.get("tone", "professional"),
                "urgency": context.get("urgency", "medium")
            }

        except Exception as e:
            logger.error("content_generation_failed", error=str(e))
            return {
                "subject": "Information Copropriété",
                "body": f"Madame, Monsieur,\n\n{user_request}\n\nCordialement,\nLe Syndic",
                "tone": "professional",
                "urgency": "medium"
            }
