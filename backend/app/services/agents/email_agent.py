"""
Email Agent V3 - Type-Aware Intelligent Email Generation

Capabilities:
- Auto-detection email type (urgent, devis, info, followup, reminder)
- Template-based generation adapted to type
- Full contextual awareness (conversation + workflow)
- Metadata-aware (recipient profession, urgency level)
"""

import structlog
from typing import Dict, Any, List, Optional
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.llm_service import LLMService
from app.models.coproprietaire import Coproprietaire

logger = structlog.get_logger()


class EmailType(Enum):
    """Types of emails with specific templates and tones"""
    URGENT_INTERVENTION = "urgent_intervention"  # Urgence: fuite, panne, sinistre
    REQUEST_QUOTE = "request_quote"  # Demande de devis
    INFORMATION = "information"  # Information générale
    FOLLOWUP = "followup"  # Suivi intervention
    REMINDER = "reminder"  # Relance (paiement, documents)
    NOTIFICATION = "notification"  # Notification simple


# Email templates by type
EMAIL_TEMPLATES = {
    EmailType.URGENT_INTERVENTION: {
        "subject_template": "🚨 URGENT - Intervention {{professional_type}} - {{building_name}}",
        "body_template": """Madame, Monsieur,

Nous faisons appel à vos services pour une intervention URGENTE concernant {{incident_type}}.

**Détails de l'incident:**
- Bâtiment: {{building_name}}
- Adresse: {{building_address}}
- Appartement: {{apartment_number}}
- Étage: {{floor}}
- Propriétaire: {{owner_name}}{{#owner_phone}} - Tél: {{owner_phone}}{{/owner_phone}}
- Nature: {{incident_description}}
- Gravité: {{severity_label}}

**Action requise:**
{{action_required}}

**Contact sur place:**
{{contact_name}}{{#contact_phone}} - {{contact_phone}}{{/contact_phone}}

Merci de nous confirmer votre disponibilité dans les plus brefs délais.

Cordialement,
Le Syndic""",
        "tone": "urgent",
        "priority": "high"
    },

    EmailType.REQUEST_QUOTE: {
        "subject_template": "Demande de devis - {{service_type}} - {{building_name}}",
        "body_template": """Madame, Monsieur,

Nous souhaitons obtenir un devis pour le service suivant:

**SERVICE DEMANDÉ:**
{{service_description}}

**LOCALISATION:**
- Bâtiment: {{building_name}}
- Adresse: {{building_address}}
{{#apartment_number}}- Appartement: {{apartment_number}}{{/apartment_number}}

**SPÉCIFICATIONS:**
{{specifications}}

{{#deadline}}**DÉLAI DE RÉPONSE SOUHAITÉ:**
{{deadline}}{{/deadline}}

{{#additional_info}}**INFORMATIONS COMPLÉMENTAIRES:**
{{additional_info}}{{/additional_info}}

Merci de nous faire parvenir votre proposition dans les meilleurs délais.

Cordialement,
Le Syndic""",
        "tone": "professional",
        "priority": "medium"
    },

    EmailType.INFORMATION: {
        "subject_template": "{{subject}} - {{building_name}}",
        "body_template": """Madame, Monsieur,

{{message_body}}

{{#action_required}}**Action requise de votre part:**
{{action_required}}{{/action_required}}

{{#deadline}}**Échéance:** {{deadline}}{{/deadline}}

{{#contact_info}}Pour toute question, vous pouvez nous contacter:
{{contact_info}}{{/contact_info}}

Cordialement,
Le Syndic""",
        "tone": "professional",
        "priority": "medium"
    },

    EmailType.FOLLOWUP: {
        "subject_template": "Suivi - {{subject}} - {{building_name}}",
        "body_template": """Madame, Monsieur,

Nous faisons suite à {{reference}}.

**Statut actuel:**
{{status_description}}

{{#next_steps}}**Prochaines étapes:**
{{next_steps}}{{/next_steps}}

{{#questions}}**Points à clarifier:**
{{questions}}{{/questions}}

Merci de nous tenir informés de l'avancement.

Cordialement,
Le Syndic""",
        "tone": "professional",
        "priority": "medium"
    },

    EmailType.REMINDER: {
        "subject_template": "Rappel - {{subject}}",
        "body_template": """Madame, Monsieur,

Nous vous rappelons {{reminder_subject}}.

{{#details}}**Détails:**
{{details}}{{/details}}

{{#deadline}}**Échéance:** {{deadline}}{{/deadline}}

{{#consequences}}**Important:** {{consequences}}{{/consequences}}

Merci de régulariser votre situation dans les plus brefs délais.

Cordialement,
Le Syndic""",
        "tone": "firm_but_polite",
        "priority": "medium"
    }
}


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
            # Step 0: AUTO-DETECT EMAIL TYPE (V3)
            email_type = await self._detect_email_type(
                user_request=user_request,
                conversation_history=conversation_history,
                workflow_context=workflow_context
            )

            logger.info("email_type_detected",
                       type=email_type.value,
                       user_request=user_request[:100])

            # Step 1: Extract email purpose and context (with conversation history)
            email_context = await self._extract_context(
                user_request=user_request,
                conversation_history=conversation_history,
                workflow_context=workflow_context
            )

            # Step 2: Get recipients if not provided
            if not recipients:
                recipients = await self._get_recipients(user_request, email_context, db)

            # Step 3: Generate email content with TYPE-SPECIFIC template (V3)
            email_draft = await self._generate_content_v3(
                email_type=email_type,
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

    async def _detect_email_type(
        self,
        user_request: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        workflow_context: Optional[Dict[str, Any]] = None
    ) -> EmailType:
        """
        V3: Intelligent auto-detection of email type

        Analyzes:
        - User request keywords
        - Conversation history context
        - Workflow context (if emergency workflow active)
        - Recipient metadata

        Returns:
            EmailType enum
        """
        # Quick rules (fast path)
        user_request_lower = user_request.lower()

        # Rule 1: Workflow context = urgence → URGENT_INTERVENTION
        if workflow_context:
            workflow_type = workflow_context.get("workflow_type", "")
            if "emergency" in workflow_type or workflow_context.get("context_data", {}).get("severity") in ["high", "critical"]:
                logger.info("email_type_detected_from_workflow", type="urgent_intervention")
                return EmailType.URGENT_INTERVENTION

        # Rule 2: Keywords urgence
        urgent_keywords = ["urgent", "urgence", "intervention", "fuite", "panne", "sinistre", "dégât", "immédiat"]
        if any(kw in user_request_lower for kw in urgent_keywords):
            logger.info("email_type_detected_from_keywords", type="urgent_intervention")
            return EmailType.URGENT_INTERVENTION

        # Rule 3: Keywords devis
        quote_keywords = ["devis", "tarif", "prix", "cotation", "proposition commerciale"]
        if any(kw in user_request_lower for kw in quote_keywords):
            logger.info("email_type_detected_from_keywords", type="request_quote")
            return EmailType.REQUEST_QUOTE

        # Rule 4: Keywords relance
        reminder_keywords = ["rappel", "relance", "n'a pas payé", "échéance dépassée"]
        if any(kw in user_request_lower for kw in reminder_keywords):
            logger.info("email_type_detected_from_keywords", type="reminder")
            return EmailType.REMINDER

        # Rule 5: Keywords suivi
        followup_keywords = ["suivi", "avancement", "statut", "où en est"]
        if any(kw in user_request_lower for kw in followup_keywords):
            logger.info("email_type_detected_from_keywords", type="followup")
            return EmailType.FOLLOWUP

        # Fallback: LLM classification
        return await self._llm_detect_email_type(
            user_request,
            conversation_history,
            workflow_context
        )

    async def _llm_detect_email_type(
        self,
        user_request: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        workflow_context: Optional[Dict[str, Any]] = None
    ) -> EmailType:
        """LLM-based email type detection for ambiguous cases"""

        # Build context
        context_str = ""
        if conversation_history:
            recent = conversation_history[-3:] if len(conversation_history) > 3 else conversation_history
            context_str += "HISTORIQUE RÉCENT:\n"
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")[:200]
                context_str += f"- {role}: {content}\n"

        if workflow_context:
            context_str += "\nCONTEXTE WORKFLOW:\n"
            context_str += f"- Type: {workflow_context.get('workflow_type', 'N/A')}\n"
            if workflow_context.get("context_data"):
                ctx = workflow_context["context_data"]
                if ctx.get("incident_type"):
                    context_str += f"- Incident: {ctx['incident_type']}\n"
                if ctx.get("severity"):
                    context_str += f"- Gravité: {ctx['severity']}\n"

        prompt = f"""Détermine le type d'email à générer.

TYPES DISPONIBLES:
1. urgent_intervention: Urgence (fuite, panne, sinistre, intervention immédiate)
2. request_quote: Demande de devis / tarif
3. information: Information générale
4. followup: Suivi intervention / projet
5. reminder: Relance (paiement, documents)

{context_str}

DEMANDE UTILISATEUR:
"{user_request}"

Réponds avec UN SEUL MOT parmi: urgent_intervention, request_quote, information, followup, reminder

TYPE:"""

        try:
            response = await self.llm_service.generate_response(
                prompt=prompt,
                max_tokens=50,
                temperature=0.1
            )

            response_clean = response.strip().lower()

            # Map response to EmailType
            type_mapping = {
                "urgent_intervention": EmailType.URGENT_INTERVENTION,
                "request_quote": EmailType.REQUEST_QUOTE,
                "information": EmailType.INFORMATION,
                "followup": EmailType.FOLLOWUP,
                "reminder": EmailType.REMINDER
            }

            detected_type = type_mapping.get(response_clean, EmailType.INFORMATION)

            logger.info("email_type_detected_by_llm",
                       type=detected_type.value,
                       llm_response=response_clean)

            return detected_type

        except Exception as e:
            logger.error("llm_email_type_detection_failed", error=str(e))
            return EmailType.INFORMATION  # Safe fallback

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

    async def _generate_content_v3(
        self,
        email_type: EmailType,
        user_request: str,
        context: Dict[str, Any],
        recipients: List[Dict[str, Any]],
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        workflow_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        V3: Template-based email generation with type-specific logic

        Uses EMAIL_TEMPLATES based on detected email_type
        """
        # Get template for this type
        template = EMAIL_TEMPLATES.get(email_type)
        if not template:
            # Fallback to old method
            return await self._generate_content(
                user_request,
                context,
                recipients,
                conversation_history,
                workflow_context
            )

        # Build template variables from context
        template_vars = self._build_template_variables(
            email_type,
            context,
            workflow_context,
            recipients
        )

        # Fill template with LLM (smart variable filling)
        filled_email = await self._fill_template_with_llm(
            template,
            template_vars,
            user_request,
            context
        )

        logger.info("email_generated_v3",
                   email_type=email_type.value,
                   has_workflow_context=bool(workflow_context),
                   vars_count=len(template_vars))

        return filled_email

    def _build_template_variables(
        self,
        email_type: EmailType,
        context: Dict[str, Any],
        workflow_context: Optional[Dict[str, Any]],
        recipients: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Build variables dict from available context"""
        vars = {}

        # Extract from workflow_context
        if workflow_context and workflow_context.get("context_data"):
            ctx_data = workflow_context["context_data"]
            vars.update({
                "building_name": ctx_data.get("building_name", ""),
                "building_address": ctx_data.get("building_address", ""),
                "apartment_number": ctx_data.get("apartment_number", ""),
                "floor": ctx_data.get("floor", ""),
                "owner_name": ctx_data.get("owner_name", ""),
                "owner_phone": ctx_data.get("owner_phone", ""),
                "incident_type": ctx_data.get("incident_type", ""),
                "incident_description": ctx_data.get("incident_description", ""),
                "severity": ctx_data.get("severity", ""),
            })

            # Severity label
            severity_map = {
                "high": "CRITIQUE",
                "medium": "Modérée",
                "low": "Faible"
            }
            vars["severity_label"] = severity_map.get(vars.get("severity", "medium"), "Modérée")

        # Extract from email context
        extracted_data = context.get("extracted_data", {})
        if extracted_data:
            vars.update({
                k: v for k, v in extracted_data.items()
                if k not in vars or not vars[k]  # Don't override workflow data
            })

        # Type-specific defaults
        if email_type == EmailType.URGENT_INTERVENTION:
            if not vars.get("professional_type"):
                # Infer from incident type
                incident = vars.get("incident_type", "").lower()
                if "eau" in incident or "fuite" in incident:
                    vars["professional_type"] = "Plomberie"
                elif "électr" in incident:
                    vars["professional_type"] = "Électricité"
                else:
                    vars["professional_type"] = "Intervention"

            if not vars.get("action_required"):
                vars["action_required"] = f"Intervention immédiate pour {vars.get('incident_type', 'résoudre le problème')}"

            if not vars.get("contact_name"):
                vars["contact_name"] = vars.get("owner_name", "Le syndic")
                vars["contact_phone"] = vars.get("owner_phone", "")

        elif email_type == EmailType.REQUEST_QUOTE:
            if not vars.get("service_type"):
                vars["service_type"] = "Service de copropriété"
            if not vars.get("service_description"):
                vars["service_description"] = "[À préciser]"
            if not vars.get("specifications"):
                vars["specifications"] = "[À compléter selon votre expertise]"

        return vars

    async def _fill_template_with_llm(
        self,
        template: Dict[str, Any],
        template_vars: Dict[str, Any],
        user_request: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use LLM to intelligently fill template variables

        For missing variables, LLM infers reasonable values from context
        """
        subject_template = template["subject_template"]
        body_template = template["body_template"]

        # Simple variable replacement (Mustache-style)
        subject = subject_template
        body = body_template

        for key, value in template_vars.items():
            if value:  # Only replace if value exists
                subject = subject.replace(f"{{{{{key}}}}}", str(value))
                body = body.replace(f"{{{{{key}}}}}", str(value))

        # Remove unreplaced variables
        import re
        subject = re.sub(r'\{\{[^}]+\}\}', '[À compléter]', subject)
        body = re.sub(r'\{\{#[^}]+\}\}.*?\{\{/[^}]+\}\}', '', body, flags=re.DOTALL)  # Remove conditional blocks
        body = re.sub(r'\{\{[^}]+\}\}', '[À compléter]', body)

        return {
            "subject": subject,
            "body": body,
            "tone": template["tone"],
            "urgency": context.get("urgency", template.get("priority", "medium"))
        }

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
