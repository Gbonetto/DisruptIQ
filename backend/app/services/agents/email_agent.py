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
    AG_CONVOCATION = "ag_convocation"  # Convocation Assemblée Générale (Phase 3.5)
    AG_PV = "ag_pv"  # PV d'Assemblée Générale
    AG_REMINDER = "ag_reminder"  # Rappel AG


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
    },

    # ================================================================
    # TEMPLATES AG (ASSEMBLÉE GÉNÉRALE) - Phase 3.5 World-Class SMA
    # ================================================================

    EmailType.AG_CONVOCATION: {
        "subject_template": "CONVOCATION - Assemblée Générale {{ag_type}} - {{building_name}} - {{ag_date}}",
        "body_template": """Madame, Monsieur,

Conformément aux articles 9 et suivants du décret n°67-223 du 17 mars 1967, nous avons l'honneur de vous convoquer à l'ASSEMBLÉE GÉNÉRALE {{ag_type}} de la copropriété.

═══════════════════════════════════════════════════════════════
                    INFORMATIONS PRATIQUES
═══════════════════════════════════════════════════════════════

📅 **DATE:** {{ag_date}}
🕐 **HEURE:** {{ag_time}}
📍 **LIEU:** {{ag_location}}
   {{ag_address}}

{{#virtual_option}}
💻 **PARTICIPATION À DISTANCE:**
   Lien visioconférence: {{virtual_link}}
   Code d'accès: {{virtual_code}}
{{/virtual_option}}

═══════════════════════════════════════════════════════════════
                      ORDRE DU JOUR
═══════════════════════════════════════════════════════════════

{{order_du_jour}}

═══════════════════════════════════════════════════════════════
                   DOCUMENTS JOINTS
═══════════════════════════════════════════════════════════════

Les documents suivants sont joints à la présente convocation:
{{documents_list}}

{{#documents_online}}
📎 L'ensemble des documents est également disponible sur l'espace copropriétaire:
   {{documents_url}}
{{/documents_online}}

═══════════════════════════════════════════════════════════════
                   MODALITÉS DE VOTE
═══════════════════════════════════════════════════════════════

**Participation personnelle:**
Vous pouvez participer personnellement à l'assemblée. Merci de vous munir d'une pièce d'identité.

**Vote par pouvoir:**
Si vous ne pouvez pas assister à l'assemblée, vous pouvez vous faire représenter par un mandataire de votre choix (copropriétaire ou non).
Le formulaire de pouvoir est joint à la présente convocation.

{{#vote_correspondance}}
**Vote par correspondance:**
Conformément à l'article 17-1 A de la loi du 10 juillet 1965, vous pouvez voter par correspondance.
Le formulaire de vote par correspondance est joint à la présente.
Date limite de réception: {{vote_deadline}}
{{/vote_correspondance}}

═══════════════════════════════════════════════════════════════
                       RAPPELS
═══════════════════════════════════════════════════════════════

• Délai de convocation: 21 jours minimum avant l'AG (art. 9 décret 1967)
• Quorum 1ère convocation: {{quorum_1}}
{{#second_convocation}}• En cas de défaut de quorum, une seconde AG sera convoquée{{/second_convocation}}
• Vos tantièmes: {{tantiemes}} / {{total_tantiemes}}

═══════════════════════════════════════════════════════════════

Nous comptons sur votre présence ou représentation.

Veuillez agréer, Madame, Monsieur, l'expression de nos salutations distinguées.

{{syndic_name}}
Syndic de Copropriété
{{syndic_address}}
{{syndic_phone}}
{{syndic_email}}

---
Copropriété: {{building_name}}
Adresse: {{building_address}}
N° SIRET: {{siret}}""",
        "tone": "formal_legal",
        "priority": "high"
    },

    EmailType.AG_PV: {
        "subject_template": "Procès-Verbal - AG {{ag_type}} du {{ag_date}} - {{building_name}}",
        "body_template": """Madame, Monsieur,

Veuillez trouver ci-joint le procès-verbal de l'Assemblée Générale {{ag_type}} qui s'est tenue le {{ag_date}}.

═══════════════════════════════════════════════════════════════
                   RÉSUMÉ DES DÉCISIONS
═══════════════════════════════════════════════════════════════

{{resolutions_summary}}

═══════════════════════════════════════════════════════════════
                    STATISTIQUES DE VOTE
═══════════════════════════════════════════════════════════════

• Copropriétaires présents: {{nb_presents}}
• Copropriétaires représentés: {{nb_representes}}
• Total tantièmes représentés: {{tantiemes_representes}} / {{total_tantiemes}} ({{pourcentage_tantiemes}}%)

═══════════════════════════════════════════════════════════════

**Délai de contestation:**
Conformément à l'article 42 de la loi du 10 juillet 1965, vous disposez d'un délai de 2 mois à compter de la notification du présent procès-verbal pour contester les décisions de l'assemblée.

Le procès-verbal complet est joint à ce courrier.

Cordialement,

{{syndic_name}}
Syndic de Copropriété""",
        "tone": "formal_legal",
        "priority": "high"
    },

    EmailType.AG_REMINDER: {
        "subject_template": "RAPPEL - Assemblée Générale {{ag_type}} - {{building_name}} - {{ag_date}}",
        "body_template": """Madame, Monsieur,

Nous vous rappelons que l'Assemblée Générale {{ag_type}} de la copropriété {{building_name}} se tiendra:

📅 **{{ag_date}}** à **{{ag_time}}**
📍 **{{ag_location}}**

{{#days_remaining}}
⏰ **Plus que {{days_remaining}} jours avant l'AG**
{{/days_remaining}}

═══════════════════════════════════════════════════════════════
                    ACTIONS REQUISES
═══════════════════════════════════════════════════════════════

{{#need_confirmation}}
☐ **Confirmez votre participation** avant le {{confirmation_deadline}}
{{/need_confirmation}}

{{#need_pouvoir}}
☐ **Retournez votre pouvoir** si vous ne pouvez pas participer
{{/need_pouvoir}}

{{#vote_correspondance}}
☐ **Vote par correspondance:** à retourner avant le {{vote_deadline}}
{{/vote_correspondance}}

═══════════════════════════════════════════════════════════════
                   DOCUMENTS À CONSULTER
═══════════════════════════════════════════════════════════════

{{documents_reminder}}

{{#documents_url}}
📎 Accès documents: {{documents_url}}
{{/documents_url}}

═══════════════════════════════════════════════════════════════

Votre participation est importante pour les décisions de la copropriété.

Cordialement,

{{syndic_name}}
Syndic de Copropriété""",
        "tone": "professional",
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
                recipients = await self._get_recipients(
                    user_request, email_context, db, conversation_history
                )

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

        # Rule 2: INFORMATION email to copropriétaires (check BEFORE urgent intervention)
        # "informer des travaux" / "prévenir les copropriétaires" = INFORMATION
        info_to_copro_keywords = ["informer", "prévenir", "avertir", "notifier"]
        copro_keywords = ["les copropriétaires", "aux copropriétaires", "copropriétaires de"]

        is_info_request = any(kw in user_request_lower for kw in info_to_copro_keywords)
        is_to_copro = any(kw in user_request_lower for kw in copro_keywords)

        if is_info_request and is_to_copro:
            logger.info("email_type_detected_from_keywords", type="information", reason="info_to_copro")
            return EmailType.INFORMATION

        # Rule 3: Keywords urgence - for prestataire intervention (NOT copro info)
        urgent_intervention_keywords = ["intervention urgente", "fuite", "panne", "sinistre", "dégât des eaux", "immédiat"]

        if any(kw in user_request_lower for kw in urgent_intervention_keywords) and not is_to_copro:
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
        "building_name": "nom du bâtiment/résidence/copropriété si disponible",
        "building_address": "adresse complète si disponible",
        "apartment_number": "numéro d'appartement si disponible",
        "owner_name": "nom propriétaire si disponible",
        "incident_type": "type d'incident/travaux si disponible (ex: plomberie, fuite, travaux)",
        "incident_description": "description détaillée de l'incident",
        "severity": "gravité si disponible (high/medium/low)",
        "professional_name": "nom du prestataire/entreprise si mentionné",
        "professional_type": "type de professionnel (plombier, électricien, etc.)",
        "amount": "montant en euros si mentionné (ex: 587,40€)",
        "date": "date d'intervention si mentionnée",
        "article_loi": "articles de loi cités si applicable"
    }}
}}

IMPORTANT: Extrait TOUTES les données spécifiques de l'historique:
- Montants (ex: "587,40€ TTC") → amount
- Noms d'entreprises (ex: "Plomberie Azur") → professional_name
- Dates (ex: "15 novembre 2024") → date
- Articles de loi (ex: "article 18 de la loi de 1965") → article_loi

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
        db: AsyncSession,
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get email recipients from database based on request and context.

        PRIORITY ORDER:
        1. Explicit emails in request
        2. Recipients from context (SQL query results)
        3. Determine recipient TYPE from request (prestataire vs copropriétaires)
        4. Filter by copropriété if mentioned in conversation
        """
        import re
        from sqlalchemy import select
        from app.models.professionnel import Professionnel
        from app.models.copropriete import Copropriete

        user_request_lower = user_request.lower()
        recipients = []

        try:
            # ================================================================
            # PRIORITY 1: Extract email addresses directly from user request
            # ================================================================
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            found_emails = re.findall(email_pattern, user_request)

            if found_emails:
                logger.info("emails_extracted_from_text", count=len(found_emails))
                for email in found_emails:
                    name = email.split('@')[0]
                    recipients.append({"name": name, "email": email, "id": None})
                return recipients

            # ================================================================
            # PRIORITY 2: Check context for emails_available (from SQL results)
            # ================================================================
            if context and "emails_available" in context:
                emails_from_context = context["emails_available"]
                logger.info("emails_from_context", count=len(emails_from_context))

                for item in emails_from_context:
                    if isinstance(item, dict):
                        recipients.append({
                            "name": item.get("name", item.get("email", "")),
                            "email": item.get("email", ""),
                            "id": item.get("id")
                        })
                    elif isinstance(item, str):
                        recipients.append({"name": item.split('@')[0], "email": item, "id": None})

                if recipients:
                    return recipients

            # ================================================================
            # PRIORITY 2b: Check resolved_references from context (SQL query results)
            # ================================================================
            if context:
                resolved_refs = context.get("resolved_references")
                if resolved_refs and isinstance(resolved_refs, dict):
                    for ref_name, ref_data in resolved_refs.items():
                        if isinstance(ref_data, dict) and ref_data.get("email"):
                            logger.info("email_from_resolved_references",
                                       name=ref_data.get("name", ref_name),
                                       email=ref_data.get("email"))
                            recipients.append({
                                "name": ref_data.get("name", ref_name),
                                "email": ref_data["email"],
                                "id": ref_data.get("id"),
                                "type": ref_data.get("type", "professionnel")
                            })
                    if recipients:
                        return recipients

            # ================================================================
            # PRIORITY 3: DETECT RECIPIENT TYPE - prestataire vs copropriétaires
            # ================================================================
            # Check if we're emailing a PRESTATAIRE (not copropriétaires)
            prestataire_keywords = ["lui", "prestataire", "artisan", "fournisseur", "entreprise",
                                    "plombier", "électricien", "devis", "facture détaillée",
                                    "rapport d'intervention", "rapport intervention", "maintenance"]
            is_prestataire_target = any(kw in user_request_lower for kw in prestataire_keywords)

            if is_prestataire_target:
                logger.info("recipient_type_prestataire_detected")

                # Try to find prestataire from multiple sources
                prestataire_name = None
                prestataire_email = None

                # Source 0: CRITICAL - Extract from user_request FIRST (most reliable)
                # Pattern: "pour le prestataire X" / "pour X" / "à X" where X is company name
                user_request_patterns = [
                    # "pour le prestataire Plomberie Azur Côte d'Azur"
                    r"(?:pour\s+(?:le\s+)?prestataire|prestataire)\s+([A-ZÀ-Üa-zà-ü][A-ZÀ-Üa-zà-ü\'\-\s]+?)(?:\s+pour|\s+leur|\s+demander|$)",
                    # "Plomberie Azur Côte d'Azur" directly in request (capitalized company name)
                    r"((?:Plomberie|Électricité|Menuiserie|Chauffage|Ascenseurs|Jardins?|Ravalement)\s+[A-ZÀ-Üa-zà-ü][A-ZÀ-Üa-zà-ü\'\-\s]+?)(?:\s+pour|\s+leur|\s+demander|,|$)",
                    # Known company names (explicit list)
                    r"(Plomberie Azur Côte d'Azur|Plomberie Azur|Électricité Méditerranée|Ravalement Pro|Ascenseurs Riviera|Jardins Azuréens)",
                ]
                for pattern in user_request_patterns:
                    match = re.search(pattern, user_request, re.IGNORECASE)
                    if match:
                        prestataire_name = match.group(1).strip()
                        logger.info("prestataire_name_from_request", name=prestataire_name, pattern=pattern[:50])
                        break

                # Source 1: Check in resolved_references from context
                if not prestataire_name and context:
                    resolved_refs = context.get("resolved_references")
                    if resolved_refs and isinstance(resolved_refs, dict):
                        for ref, data in resolved_refs.items():
                            if isinstance(data, dict) and data.get("type") == "professionnel":
                                prestataire_name = data.get("name")
                                prestataire_email = data.get("email")
                                break

                # Source 2: Check in context extracted_data (from RAG or previous queries)
                if not prestataire_name and context:
                    extracted = context.get("extracted_data")
                    if extracted and isinstance(extracted, dict):
                        prestataire_name = extracted.get("prestataire") or extracted.get("vendor")
                        if not prestataire_name:
                            # Check for company patterns in extracted data
                            for key, value in extracted.items():
                                if isinstance(value, str) and any(kw in key.lower() for kw in ["prestataire", "entreprise", "fournisseur"]):
                                    prestataire_name = value
                                    break

                # Source 3: Extract from conversation history with improved patterns
                if not prestataire_name and conversation_history:
                    # Improved patterns for company names
                    company_patterns = [
                        # Pattern for "Prestataire : Company Name"
                        r"[Pp]restataire\s*[:=]\s*([A-ZÀ-Üa-zà-ü][^\n\[\]]{3,50}?)(?:\[|\.|$|\n)",
                        # Pattern for company names with business suffixes
                        r"((?:[A-ZÀ-Ü][a-zà-ü\-]+\s*)+(?:SARL|SAS|EURL|Pro|Express|Services?))",
                        # Pattern for "Plomberie/Électricité + Name"
                        r"((?:Plomberie|Électricité|Menuiserie|Chauffage|Climatisation)\s+[A-ZÀ-Üa-zà-ü\'\-\s]+?)(?:\[|\.|$|\n)",
                        # Pattern for generic capitalized company names (with location)
                        r"((?:[A-ZÀ-Ü][a-zà-ü]+\s+){1,4}(?:Côte d'Azur|Nice|Paris|Lyon|Marseille)?)",
                    ]

                    for msg in reversed(conversation_history[-10:]):
                        content = msg.get("content", "")
                        for pattern in company_patterns:
                            match = re.search(pattern, content)
                            if match:
                                candidate = match.group(1).strip()
                                # Validate: min length and not generic words
                                generic_words = ["le", "la", "les", "un", "une", "de", "du", "des", "et", "ou"]
                                if len(candidate) > 5 and candidate.lower() not in generic_words:
                                    prestataire_name = candidate
                                    logger.info("prestataire_name_extracted", name=prestataire_name, pattern=pattern[:30])
                                    break
                        if prestataire_name:
                            break

                # Search in professionnels table if we have a name
                if prestataire_name:
                    # Clean the name for search
                    search_name = prestataire_name.strip().rstrip('.')

                    result = await db.execute(
                        select(Professionnel).where(
                            Professionnel.name.ilike(f"%{search_name}%") |
                            Professionnel.company_name.ilike(f"%{search_name}%")
                        )
                    )
                    pro = result.scalar_one_or_none()
                    if pro and pro.email:
                        logger.info("prestataire_found", name=pro.name, email=pro.email)
                        return [{
                            "name": pro.name or pro.company_name,
                            "email": pro.email,
                            "id": pro.id,
                            "type": "professionnel"
                        }]

                    # Try partial search with first word only
                    first_word = search_name.split()[0] if search_name else ""
                    if first_word and len(first_word) > 3:
                        result = await db.execute(
                            select(Professionnel).where(
                                Professionnel.name.ilike(f"%{first_word}%") |
                                Professionnel.company_name.ilike(f"%{first_word}%")
                            )
                        )
                        pros = result.scalars().all()
                        if len(pros) == 1 and pros[0].email:
                            logger.info("prestataire_found_partial", name=pros[0].name, email=pros[0].email, search=first_word)
                            return [{
                                "name": pros[0].name or pros[0].company_name,
                                "email": pros[0].email,
                                "id": pros[0].id,
                                "type": "professionnel"
                            }]

                # If we have an email directly from context
                if prestataire_email:
                    logger.info("prestataire_email_from_context", email=prestataire_email)
                    return [{
                        "name": prestataire_name or "Prestataire",
                        "email": prestataire_email,
                        "id": None,
                        "type": "professionnel"
                    }]

                # If no prestataire found, return empty (don't fallback to all copros!)
                logger.warning("prestataire_not_found", searched_name=prestataire_name)
                return []

            # ================================================================
            # PRIORITY 4: FILTER COPROPRIETAIRES by copropriété
            # ================================================================
            # Find copropriété from request or conversation
            copropriete_id = None
            copropriete_name = None

            # Check in extracted_data
            if context and context.get("extracted_data"):
                copropriete_name = context["extracted_data"].get("building") or \
                                   context["extracted_data"].get("copropriete")

            # CRITICAL: Check in current user request FIRST
            if not copropriete_name:
                copro_patterns = [
                    # Try explicit known names first (most reliable)
                    r"(Arc-en-Ciel|Jardins de Provence|Parc des Étoiles|Les Mimosas|Arc en Ciel)",
                    # Then try generic pattern with boundary - stop at "pour", "avec", "de la", etc.
                    r"(?:résidence|copropriété|immeuble)\s+(?:de\s+la\s+|de\s+)?([A-ZÀ-Üa-zà-ü][A-ZÀ-Üa-zà-ü\-\']+(?:\s+[A-ZÀ-Üa-zà-ü\-\']+)?)\s*(?:pour|avec|de\s+la|,|$)"
                ]
                for pattern in copro_patterns:
                    match = re.search(pattern, user_request, re.IGNORECASE)
                    if match:
                        copropriete_name = match.group(1).strip()
                        logger.info("copropriete_found_in_request", name=copropriete_name)
                        break

            # Check in conversation for copropriété mentions (fallback)
            if not copropriete_name and conversation_history:
                for msg in reversed(conversation_history[-10:]):
                    content = msg.get("content", "")
                    for pattern in copro_patterns:
                        match = re.search(pattern, content, re.IGNORECASE)
                        if match:
                            copropriete_name = match.group(1).strip()
                            logger.info("copropriete_found_in_history", name=copropriete_name)
                            break
                    if copropriete_name:
                        break

            # If we found a copropriété name, get its ID
            if copropriete_name:
                result = await db.execute(
                    select(Copropriete).where(Copropriete.nom.ilike(f"%{copropriete_name}%"))
                )
                copro = result.scalar_one_or_none()
                if copro:
                    copropriete_id = copro.id
                    logger.info("copropriete_identified", name=copro.nom, id=copro.id)

            # Get copropriétaires (filtered by copropriété if found)
            if copropriete_id:
                result = await db.execute(
                    select(Coproprietaire).where(Coproprietaire.copropriete_id == copropriete_id)
                )
            else:
                # Only if explicitly "tous les copropriétaires" mentioned
                if any(word in user_request_lower for word in ["tous les copropriétaires", "all"]):
                    result = await db.execute(select(Coproprietaire))
                else:
                    logger.info("no_specific_recipients_found")
                    return []

            coproprietaires = result.scalars().all()

            recipients = [
                {
                    "name": f"{c.prenom} {c.nom}",
                    "email": c.email,
                    "id": c.id,
                    "type": "coproprietaire"
                }
                for c in coproprietaires
                if c.email  # Only include those with email
            ]

            logger.info("recipients_found",
                       count=len(recipients),
                       copropriete_filter=copropriete_name or "none")

            return recipients

        except Exception as e:
            logger.error("recipients_fetch_failed", error=str(e), exc_info=True)
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
            context,
            conversation_history
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

        # Extract from email context - map extracted_data keys to template vars
        extracted_data = context.get("extracted_data", {})
        if extracted_data:
            # Direct mapping for matching keys
            vars.update({
                k: v for k, v in extracted_data.items()
                if v and (k not in vars or not vars[k])  # Don't override workflow data
            })

            # Additional mappings for template compatibility
            if extracted_data.get("amount") and not vars.get("amount"):
                vars["amount"] = extracted_data["amount"]
            if extracted_data.get("date") and not vars.get("intervention_date"):
                vars["intervention_date"] = extracted_data["date"]
            if extracted_data.get("professional_name") and not vars.get("prestataire_name"):
                vars["prestataire_name"] = extracted_data["professional_name"]
            if extracted_data.get("article_loi") and not vars.get("article_loi"):
                vars["article_loi"] = extracted_data["article_loi"]

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
        context: Dict[str, Any],
        conversation_history: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Use LLM to intelligently fill template variables

        For missing variables, LLM infers reasonable values from context
        """
        import re

        # CRITICAL: Extract ALL data from user_request FIRST
        # This is where dates, amounts, names are typically mentioned
        extracted_from_request = self._extract_email_data_from_text(user_request)

        # Merge with template_vars (user_request data takes priority)
        for key, value in extracted_from_request.items():
            if value and (key not in template_vars or not template_vars.get(key)):
                template_vars[key] = value

        logger.info("template_vars_after_extraction",
                   vars_count=len(template_vars),
                   has_date=bool(template_vars.get("intervention_date") or template_vars.get("date")),
                   has_amount=bool(template_vars.get("amount")),
                   has_building=bool(template_vars.get("building_name")))

        subject_template = template["subject_template"]
        body_template = template["body_template"]

        # Simple variable replacement (Mustache-style)
        subject = subject_template
        body = body_template

        for key, value in template_vars.items():
            if value:  # Only replace if value exists
                subject = subject.replace(f"{{{{{key}}}}}", str(value))
                body = body.replace(f"{{{{{key}}}}}", str(value))

        # Check if there are still unreplaced variables
        unreplaced_vars = re.findall(r'\{\{([^}]+)\}\}', subject + body)

        # Build conversation context for richer emails
        conversation_context_str = ""
        if conversation_history and len(conversation_history) > 0:
            recent = conversation_history[-5:] if len(conversation_history) > 5 else conversation_history
            conversation_context_str = "\nCONTEXTE CONVERSATION RÉCENTE:\n"
            for msg in recent:
                role = "Utilisateur" if msg.get("role") == "user" else "Assistant"
                content = msg.get("content", "")[:300]
                conversation_context_str += f"- {role}: {content}\n"

        # Build key points from context
        key_points_str = ""
        if context.get("key_points"):
            key_points_str = "\nPOINTS CLÉS À INCLURE:\n" + "\n".join(f"- {p}" for p in context["key_points"])

        # ALWAYS generate with LLM for professional quality (even if no unreplaced vars)
        logger.info("generating_email_with_llm",
                   unreplaced_count=len(unreplaced_vars) if unreplaced_vars else 0,
                   user_request_preview=user_request[:100])

        # Build comprehensive data section from template_vars
        data_section = "\nDONNÉES EXTRAITES DE LA DEMANDE:\n"
        important_keys = ["date", "intervention_date", "amount", "montant", "building_name",
                         "prestataire_name", "professional_name", "service_type", "incident_type"]
        for key in important_keys:
            if template_vars.get(key):
                data_section += f"- {key}: {template_vars[key]}\n"

        # Add all other non-empty vars
        for k, v in template_vars.items():
            if v and k not in important_keys:
                data_section += f"- {k}: {v}\n"

        prompt = f"""Tu es un assistant expert pour un syndic de copropriété. Génère un email COMPLET et PROFESSIONNEL.

=== DEMANDE UTILISATEUR (CRITIQUE - UTILISE CES INFORMATIONS) ===
"{user_request}"
{data_section}
{conversation_context_str}
CONTEXTE EXTRAIT:
- Résumé: {context.get('context_summary', 'Information à communiquer')}
- Objectif: {context.get('purpose', user_request)}
- Ton requis: {template.get("tone", "professional")}
- Urgence: {context.get("urgency", "medium")}
{key_points_str}

=== RÈGLES STRICTES ET ABSOLUES ===
1. L'objet DOIT être concret: mentionner la date, le montant, ou l'objet spécifique
2. Le corps NE DOIT PAS répéter l'objet - commence directement par "Madame, Monsieur,"
3. Si une info est disponible (date, montant, nom) → UTILISE-LA dans le texte
4. Si une info N'EST PAS disponible → NE LA MENTIONNE PAS, ne mets JAMAIS de placeholder
5. TEXTE BRUT UNIQUEMENT: pas de markdown, pas de **, pas de formatage HTML
6. Structure: Salutation → Corps informatif → Signature "Le Syndic"

=== INTERDICTIONS ABSOLUES (violations = email rejeté) ===
❌ JAMAIS de "[À compléter]", "[date]", "[nom]", ou toute balise entre crochets
❌ JAMAIS de "si disponible", "le cas échéant", "[préciser]"
❌ JAMAIS répéter l'objet dans le corps du message
❌ JAMAIS de mise en forme markdown (**, ##, -, etc.)
❌ JAMAIS de texte générique comme "dans les prochains jours" si la date est connue

=== FORMAT DE RÉPONSE ===
Réponds EXACTEMENT dans ce format (2 lignes séparées par SUBJECT_BODY_SEPARATOR):

SUBJECT: [objet précis - sans répétition dans le body]
SUBJECT_BODY_SEPARATOR
BODY: [corps email en texte brut, commence par "Madame, Monsieur,"]"""

        try:
            response = await self.llm_service.generate_response(
                prompt=prompt,
                max_tokens=1000,
                temperature=0.3
            )

            import json

            response_text = response.strip()
            logger.info("llm_raw_response_preview", response=response_text[:300])

            generated = None

            # Method 1: Try new format with SUBJECT_BODY_SEPARATOR
            if "SUBJECT_BODY_SEPARATOR" in response_text:
                parts = response_text.split("SUBJECT_BODY_SEPARATOR")
                if len(parts) >= 2:
                    subject_part = parts[0].strip()
                    body_part = parts[1].strip()

                    # Extract subject
                    if subject_part.startswith("SUBJECT:"):
                        subject_text = subject_part.replace("SUBJECT:", "").strip()
                    else:
                        subject_text = subject_part

                    # Extract body
                    if body_part.startswith("BODY:"):
                        body_text = body_part.replace("BODY:", "").strip()
                    else:
                        body_text = body_part

                    if subject_text and body_text:
                        generated = {"subject": subject_text, "body": body_text}
                        logger.info("email_parsed_separator_format")

            # Method 2: Try SUJET/CORPS format (French)
            if not generated and ("SUJET:" in response_text or "OBJET:" in response_text):
                lines = response_text.split('\n')
                subject_text = ""
                body_lines = []
                in_body = False

                for line in lines:
                    line_upper = line.upper().strip()
                    if line_upper.startswith("SUJET:") or line_upper.startswith("OBJET:"):
                        subject_text = line.split(":", 1)[1].strip() if ":" in line else ""
                    elif line_upper.startswith("CORPS:") or line_upper.startswith("BODY:"):
                        in_body = True
                    elif in_body:
                        body_lines.append(line)

                if subject_text and body_lines:
                    generated = {"subject": subject_text, "body": "\n".join(body_lines).strip()}
                    logger.info("email_parsed_french_format")

            # Method 3: Try JSON format
            if not generated:
                try:
                    generated = json.loads(response_text)
                except json.JSONDecodeError:
                    # Try to extract JSON block from markdown
                    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response_text, re.DOTALL)
                    if json_match:
                        try:
                            generated = json.loads(json_match.group(1).strip())
                        except json.JSONDecodeError:
                            pass

                    # Try to find JSON object with subject and body
                    if not generated:
                        # More permissive regex for multiline JSON
                        json_match = re.search(r'\{\s*"subject"\s*:\s*"([^"]+)"\s*,\s*"body"\s*:\s*"((?:[^"\\]|\\.)*)"\s*\}', response_text, re.DOTALL)
                        if json_match:
                            generated = {
                                "subject": json_match.group(1),
                                "body": json_match.group(2).replace('\\n', '\n').replace('\\"', '"')
                            }

            # Method 4: Fallback - extract any structured content
            if not generated:
                # Look for "Subject:" or "Objet:" anywhere
                subject_match = re.search(r'(?:Subject|Objet|SUBJECT|OBJET)\s*:\s*(.+?)(?:\n|$)', response_text, re.IGNORECASE)
                if subject_match:
                    subject_text = subject_match.group(1).strip()
                    # Body is everything after subject line
                    body_start = subject_match.end()
                    body_text = response_text[body_start:].strip()
                    # Remove "Body:" or "Corps:" prefix if present
                    body_text = re.sub(r'^(?:Body|Corps|BODY|CORPS)\s*:\s*', '', body_text, flags=re.IGNORECASE)

                    if subject_text and body_text:
                        generated = {"subject": subject_text, "body": body_text}
                        logger.info("email_parsed_fallback_format")

            if generated and generated.get("subject") and generated.get("body"):
                # POST-PROCESSING: Clean up any remaining issues
                subject_clean = self._sanitize_email_content(generated["subject"])
                body_clean = self._sanitize_email_content(generated["body"])

                # Remove subject repetition at start of body
                body_clean = self._remove_subject_from_body(subject_clean, body_clean)

                logger.info("email_generated_by_llm",
                           subject_preview=subject_clean[:50],
                           body_length=len(body_clean))

                return {
                    "subject": subject_clean,
                    "body": body_clean,
                    "tone": template["tone"],
                    "urgency": context.get("urgency", template.get("priority", "medium"))
                }
            else:
                logger.warning("llm_no_valid_content", response_preview=response_text[:200])

        except Exception as e:
            logger.error("llm_generation_failed", error=str(e), exc_info=True)

        # Last resort: Generate simple email from user request directly
        logger.warning("using_fallback_email_generation")
        return await self._generate_fallback_email(user_request, template_vars, template, context)

    def _extract_email_data_from_text(self, text: str) -> Dict[str, Any]:
        """Extract dates, amounts, names from user request text"""
        import re
        extracted = {}

        # Extract date patterns (French)
        date_patterns = [
            r'(\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4})',
            r'(\d{1,2}/\d{1,2}/\d{4})',
            r'(\d{1,2}-\d{1,2}-\d{4})',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted["intervention_date"] = match.group(1)
                extracted["date"] = match.group(1)
                break

        # Extract amount (euros)
        amount_patterns = [
            r'(\d+[\s,.]?\d*\s*€)',
            r'(\d+[\s,.]?\d*\s*euros?)',
            r'facture\s+(?:de\s+)?(\d+[\s,.]?\d*)',
        ]
        for pattern in amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted["amount"] = match.group(1)
                break

        # Extract residence/building name
        building_patterns = [
            r'résidence\s+([A-ZÀ-Ü][a-zà-ü\-]+(?:\s+[A-ZÀ-Ü]?[a-zà-ü\-]+)*)',
            r'copropriété\s+([A-ZÀ-Ü][a-zà-ü\-]+(?:\s+[A-ZÀ-Ü]?[a-zà-ü\-]+)*)',
            r'(Arc-en-Ciel|Jardins de Provence|Les Mimosas)',
        ]
        for pattern in building_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted["building_name"] = match.group(1)
                break

        # Extract prestataire name
        prestataire_patterns = [
            r'prestataire\s+([A-ZÀ-Ü][^\s,\.]+(?:\s+[A-ZÀ-Ü]?[^\s,\.]+)*)',
            r'(Plomberie\s+[A-ZÀ-Ü][^\s,\.]+(?:\s+[^\s,\.]+)*)',
            r'(Électricité\s+[A-ZÀ-Ü][^\s,\.]+(?:\s+[^\s,\.]+)*)',
        ]
        for pattern in prestataire_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                extracted["prestataire_name"] = match.group(1).strip()
                extracted["professional_name"] = match.group(1).strip()
                break

        # Detect service type from keywords
        if "maintenance" in text.lower():
            extracted["service_type"] = "Maintenance préventive"
        elif "devis" in text.lower():
            extracted["service_type"] = "Demande de devis"
        elif "rapport" in text.lower():
            extracted["service_type"] = "Rapport d'intervention"

        return extracted

    def _sanitize_email_content(self, text: str) -> str:
        """
        Remove all placeholders, markdown formatting, and problematic content from email text.

        This is a CRITICAL safety function to prevent embarrassing placeholders from being sent.
        """
        import re

        if not text:
            return text

        # 1. Remove markdown bold/italic
        text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # **bold** → bold
        text = re.sub(r'\*([^*]+)\*', r'\1', text)       # *italic* → italic
        text = re.sub(r'__([^_]+)__', r'\1', text)       # __bold__ → bold
        text = re.sub(r'_([^_]+)_', r'\1', text)         # _italic_ → italic

        # 2. Remove markdown headers
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)  # ## Header → Header

        # 3. Remove markdown lists (but keep content)
        text = re.sub(r'^[\-\*]\s+', '', text, flags=re.MULTILINE)  # - item → item

        # 4. CRITICAL: Remove ALL placeholder patterns
        placeholder_patterns = [
            r'\[À compléter[^\]]*\]',
            r'\[à compléter[^\]]*\]',
            r'\[À préciser[^\]]*\]',
            r'\[à préciser[^\]]*\]',
            r'\[date[^\]]*\]',
            r'\[Date[^\]]*\]',
            r'\[DATE[^\]]*\]',
            r'\[nom[^\]]*\]',
            r'\[Nom[^\]]*\]',
            r'\[NOM[^\]]*\]',
            r'\[montant[^\]]*\]',
            r'\[Montant[^\]]*\]',
            r'\[adresse[^\]]*\]',
            r'\[préciser[^\]]*\]',
            r'\[Préciser[^\]]*\]',
            r'\[[^\]]*si disponible[^\]]*\]',
            r'\[[^\]]*le cas échéant[^\]]*\]',
            r'\{\{[^}]+\}\}',  # Mustache variables
        ]
        for pattern in placeholder_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        # 5. Remove problematic phrases (but not inside brackets - already removed)
        problematic_phrases = [
            r'\s*\(si disponible[^)]*\)',
            r'\s*\(le cas échéant[^)]*\)',
            r'\s*\(à préciser[^)]*\)',
        ]
        for pattern in problematic_phrases:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        # 6. Clean up multiple spaces and empty lines
        text = re.sub(r'  +', ' ', text)  # Multiple spaces → single space
        text = re.sub(r'\n{3,}', '\n\n', text)  # Multiple newlines → double newline
        text = text.strip()

        return text

    def _remove_subject_from_body(self, subject: str, body: str) -> str:
        """
        Remove the subject line if it appears at the start of the body.

        Common LLM issue: repeating "Objet: xxx" at start of email body.
        """
        import re

        if not body or not subject:
            return body

        # Pattern 1: "Objet : [subject text]" at start
        body = re.sub(
            r'^Objet\s*:\s*' + re.escape(subject) + r'\s*\n+',
            '',
            body,
            flags=re.IGNORECASE
        )

        # Pattern 2: Just the subject text at start (without "Objet:")
        # Only if it's the exact subject at the very beginning
        body_lines = body.split('\n')
        if body_lines and body_lines[0].strip().lower() == subject.lower().strip():
            body = '\n'.join(body_lines[1:]).strip()

        # Pattern 3: "Objet : xxx" anywhere at start (generic removal)
        body = re.sub(r'^Objet\s*:\s*[^\n]+\n+', '', body, flags=re.IGNORECASE)

        return body.strip()

    async def _generate_fallback_email(
        self,
        user_request: str,
        template_vars: Dict[str, Any],
        template: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate a simple email when LLM parsing fails"""
        # Build subject from available data
        subject_parts = []
        if template_vars.get("service_type"):
            subject_parts.append(template_vars["service_type"])
        elif "devis" in user_request.lower():
            subject_parts.append("Demande de devis")
        elif "rapport" in user_request.lower():
            subject_parts.append("Demande de rapport")
        else:
            subject_parts.append("Demande")

        if template_vars.get("building_name"):
            subject_parts.append(f"- {template_vars['building_name']}")
        if template_vars.get("intervention_date"):
            subject_parts.append(f"- {template_vars['intervention_date']}")

        subject = " ".join(subject_parts)

        # Build body from user request
        body = "Madame, Monsieur,\n\n"
        body += f"Suite à notre échange, je me permets de vous contacter concernant:\n\n"
        body += f"{user_request}\n\n"

        if template_vars.get("amount"):
            body += f"Montant concerné: {template_vars['amount']}\n"
        if template_vars.get("intervention_date"):
            body += f"Date d'intervention: {template_vars['intervention_date']}\n"

        body += "\nMerci de nous faire parvenir votre retour dans les meilleurs délais.\n\n"
        body += "Cordialement,\nLe Syndic"

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
