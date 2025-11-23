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
        recipients: List[Dict[str, Any]] = None,
        conversation_history: List[Dict[str, Any]] = None,
        workflow_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Generate email draft from user request with full conversational context

        Args:
            user_request: User's email request (ex: "Envoyer email pour dégât des eaux")
            db: Database session
            recipients: Optional list of recipients
            conversation_history: Recent conversation messages for context
            workflow_context: Workflow data (from WorkflowAgent) if available

        Returns:
            Dict with success, message, email draft data
        """
        try:
            # Step 1: Extract email purpose and context (with conversation history)
            email_context = await self._extract_context(
                user_request=user_request,
                conversation_history=conversation_history,
                workflow_context=workflow_context
            )

            # Step 2: Get recipients if not provided
            if not recipients:
                recipients = await self._get_recipients(user_request, email_context, db)

            # Step 3: Generate email content (with enriched context)
            email_draft = await self._generate_content(
                user_request=user_request,
                context=email_context,
                recipients=recipients,
                conversation_history=conversation_history,
                workflow_context=workflow_context
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

    async def _extract_context(
        self,
        user_request: str,
        conversation_history: List[Dict[str, Any]] = None,
        workflow_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Extract email purpose, tone, urgency from user request AND conversation history

        V2: Now captures full context from recent messages and workflow data
        """
        # Build conversation context string
        conversation_context = ""
        if conversation_history and len(conversation_history) > 0:
            # Take last 5 messages for context
            recent_messages = conversation_history[-5:] if len(conversation_history) > 5 else conversation_history
            conversation_context = "HISTORIQUE CONVERSATIONNEL RÉCENT:\n"
            for msg in recent_messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                # Truncate long messages
                if len(content) > 500:
                    content = content[:500] + "..."
                conversation_context += f"- {role.upper()}: {content}\n"
            conversation_context += "\n"

        # Build workflow context string
        workflow_context_str = ""
        if workflow_context:
            workflow_context_str = "CONTEXTE DU WORKFLOW:\n"
            if workflow_context.get("context_data"):
                ctx_data = workflow_context["context_data"]
                if ctx_data.get("building_name"):
                    workflow_context_str += f"- Bâtiment: {ctx_data['building_name']}\n"
                if ctx_data.get("building_address"):
                    workflow_context_str += f"- Adresse: {ctx_data['building_address']}\n"
                if ctx_data.get("apartment_number"):
                    workflow_context_str += f"- Appartement: {ctx_data['apartment_number']}\n"
                if ctx_data.get("floor"):
                    workflow_context_str += f"- Étage: {ctx_data['floor']}\n"
                if ctx_data.get("owner_name"):
                    workflow_context_str += f"- Propriétaire: {ctx_data['owner_name']}\n"
                if ctx_data.get("incident_type"):
                    workflow_context_str += f"- Type d'incident: {ctx_data['incident_type']}\n"
                if ctx_data.get("incident_description"):
                    workflow_context_str += f"- Description: {ctx_data['incident_description']}\n"
                if ctx_data.get("severity"):
                    workflow_context_str += f"- Gravité: {ctx_data['severity']}\n"
            workflow_context_str += "\n"

        prompt = f"""
Analyse cette demande d'email en prenant en compte TOUT le contexte disponible.

{conversation_context}{workflow_context_str}DEMANDE ACTUELLE:
{user_request}

INSTRUCTIONS:
1. Extrais TOUTES les informations pertinentes depuis l'historique ET le workflow
2. Identifie le type d'email (urgence, information, relance, etc.)
3. Détermine le ton et l'urgence appropriés
4. Liste TOUS les points clés à inclure dans l'email

Réponds en JSON avec:
{{
    "purpose": "Objectif précis de l'email",
    "tone": "professional" | "urgent" | "friendly",
    "urgency": "high" | "medium" | "low",
    "key_points": ["Point 1", "Point 2", ...],
    "context_summary": "Résumé du contexte en 1-2 phrases",
    "extracted_data": {{
        "building": "nom du bâtiment si disponible",
        "address": "adresse si disponible",
        "apartment": "numéro d'appartement si disponible",
        "owner": "nom propriétaire si disponible",
        "incident_type": "type d'incident si disponible",
        "severity": "gravité si disponible"
    }}
}}

JSON:
"""

        try:
            response = await self.llm_service.generate_response(
                prompt=prompt,
                max_tokens=800,
                temperature=0.3
            )

            # Parse JSON response
            import json
            context = json.loads(response.strip())

            logger.info("context_extracted_with_history",
                       purpose=context.get("purpose"),
                       urgency=context.get("urgency"),
                       has_conversation_history=bool(conversation_history),
                       has_workflow_context=bool(workflow_context))

            return context

        except Exception as e:
            logger.error("context_extraction_failed", error=str(e))
            return {
                "purpose": user_request,
                "tone": "professional",
                "urgency": "medium",
                "key_points": [],
                "context_summary": "",
                "extracted_data": {}
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
        recipients: List[Dict[str, Any]],
        conversation_history: List[Dict[str, Any]] = None,
        workflow_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Generate email subject and body with FULL contextual awareness

        V2: Uses conversation history and workflow context for rich, detailed emails
        """
        tone_instructions = {
            "professional": "Ton professionnel et formel",
            "urgent": "Ton urgent mais poli, marquer clairement l'urgence avec emojis (🚨, ⚠️)",
            "friendly": "Ton amical et chaleureux"
        }

        # Build detailed context section
        context_section = ""
        extracted_data = context.get("extracted_data", {})
        if extracted_data:
            context_section += "\nDÉTAILS DU CONTEXTE:\n"
            if extracted_data.get("building"):
                context_section += f"- Bâtiment: {extracted_data['building']}\n"
            if extracted_data.get("address"):
                context_section += f"- Adresse: {extracted_data['address']}\n"
            if extracted_data.get("apartment"):
                context_section += f"- Appartement: {extracted_data['apartment']}\n"
            if extracted_data.get("owner"):
                context_section += f"- Propriétaire: {extracted_data['owner']}\n"
            if extracted_data.get("incident_type"):
                context_section += f"- Type d'incident: {extracted_data['incident_type']}\n"
            if extracted_data.get("severity"):
                context_section += f"- Gravité: {extracted_data['severity']}\n"

        # Add workflow context if available
        if workflow_context and workflow_context.get("context_data"):
            ctx_data = workflow_context["context_data"]
            context_section += "\nCONTEXTE DU WORKFLOW:\n"
            for key, value in ctx_data.items():
                if value and key not in ["actions_taken", "affected_floors"]:
                    context_section += f"- {key}: {value}\n"

        # Build key points section
        key_points_section = ""
        if context.get("key_points"):
            key_points_section = "\nPOINTS CLÉS À INCLURE:\n"
            for point in context["key_points"]:
                key_points_section += f"- {point}\n"

        # Determine urgency markers
        urgency_marker = ""
        if context.get("urgency") == "high":
            urgency_marker = "🚨 URGENT 🚨"
        elif context.get("urgency") == "medium":
            urgency_marker = "⚠️"

        prompt = f"""
Tu es un assistant intelligent pour un syndic de copropriété. Tu dois générer un EMAIL RICHE ET CONTEXTUEL.

DEMANDE UTILISATEUR:
{user_request}

OBJECTIF DE L'EMAIL:
{context.get('purpose', 'Information')}

TON: {tone_instructions.get(context.get('tone', 'professional'))}
URGENCE: {context.get('urgency', 'medium')} {urgency_marker}
{context_section}{key_points_section}
CONTEXTE ADDITIONNEL:
{context.get('context_summary', '')}

NOMBRE DE DESTINATAIRES: {len(recipients)}

RÈGLES CRITIQUES POUR UN EMAIL DE QUALITÉ:
✅ UTILISE TOUTES les informations de contexte disponibles ci-dessus
✅ Sois PRÉCIS et DÉTAILLÉ (adresses, noms, numéros d'appartement, etc.)
✅ Pour les urgences: utilise des emojis 🚨 et marque clairement la gravité
✅ Structure l'email de manière professionnelle mais complète
✅ Inclus TOUS les détails pertinents (bâtiment, adresse, contact, nature du problème)
✅ Si c'est une demande d'intervention: sois très clair sur ce qui est attendu
✅ Si des coordonnées sont disponibles: inclus-les pour faciliter le contact
⚠️ N'invente PAS d'informations qui ne sont pas dans le contexte
⚠️ Si un détail manque, ne pas l'inventer mais rester factuel

EXEMPLE DE STRUCTURE POUR UNE URGENCE:
SUJET: 🚨 URGENT - [Type d'intervention] - [Bâtiment]

CORPS:
Madame, Monsieur,

Nous faisons appel à vos services pour une intervention urgente concernant [incident précis].

**Détails de l'incident:**
- Bâtiment: [nom]
- Adresse: [adresse complète]
- Appartement: [numéro]
- Propriétaire: [nom + coordonnées si disponibles]
- Nature: [description détaillée]

**Action requise:**
[Description claire de ce qui est attendu]

**Contact sur place:**
[Coordonnées si disponibles]

Merci de nous confirmer votre disponibilité dans les plus brefs délais.

Cordialement,
Le Syndic

---

GÉNÈRE MAINTENANT L'EMAIL COMPLET en suivant ces règles:

Format de réponse:
SUJET: [sujet ici]

CORPS:
[corps ici]
"""

        try:
            response = await self.llm_service.generate_response(
                prompt=prompt,
                max_tokens=1500,  # Increased for richer emails
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

            logger.info("email_content_generated",
                       subject=subject,
                       body_length=len(body),
                       urgency=context.get("urgency"),
                       has_context=bool(context_section))

            return {
                "subject": subject or f"{urgency_marker} Information Copropriété",
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
