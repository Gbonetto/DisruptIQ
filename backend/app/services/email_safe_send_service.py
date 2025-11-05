"""
Email Safe-Send Service - Preview et Checklist Obligatoire

Gère l'envoi sécurisé d'emails avec:
- Génération brouillon avec contexte SQL + RAG
- Preview obligatoire avant envoi
- Checklist de validation
- Evidence tracking (sources)
- Protection contre envois accidentels
"""

import structlog
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, EmailStr, validator
from enum import Enum
from datetime import datetime
import uuid
import hashlib

logger = structlog.get_logger()


class EmailPriority(str, Enum):
    """Priorité email"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class EvidenceType(str, Enum):
    """Type d'evidence (source)"""
    SQL = "sql"  # Résultat query SQL
    RAG = "rag"  # Document RAG
    MANUAL = "manual"  # Saisie manuelle


class Evidence(BaseModel):
    """Evidence/source pour email"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: EvidenceType
    title: str
    content: str
    reference: Optional[str] = None  # doc_id, query, URL, etc.
    confidence: Optional[float] = None


class Recipient(BaseModel):
    """Destinataire email"""
    email: EmailStr
    name: Optional[str] = None
    type: str = "to"  # to, cc, bcc
    metadata: Dict[str, Any] = Field(default_factory=dict)  # coproprietaire_id, etc.


class EmailDraft(BaseModel):
    """Brouillon d'email"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: Optional[str] = None
    user_id: Optional[int] = None

    # Contenu
    subject: str
    body: str  # HTML ou plain text
    recipients: List[Recipient] = []
    priority: EmailPriority = EmailPriority.NORMAL

    # Context & Evidence
    context: Dict[str, Any] = Field(default_factory=dict)
    evidence: List[Evidence] = []

    # Métadonnées
    created_at: datetime = Field(default_factory=datetime.utcnow)
    preview_shown: bool = False
    checklist_validated: bool = False
    sent_at: Optional[datetime] = None

    # Hash pour détection modifications
    content_hash: Optional[str] = None

    def generate_content_hash(self) -> str:
        """Génère hash du contenu (subject + body + recipients)"""
        content = f"{self.subject}|{self.body}|{'|'.join([r.email for r in self.recipients])}"
        return hashlib.sha256(content.encode()).hexdigest()

    def has_been_modified(self) -> bool:
        """Vérifie si le brouillon a été modifié depuis le hash"""
        if not self.content_hash:
            return True
        return self.generate_content_hash() != self.content_hash


class EmailChecklist(BaseModel):
    """Checklist de validation avant envoi"""
    items: List[Dict[str, Any]] = []
    all_checked: bool = False

    @staticmethod
    def default_checklist() -> "EmailChecklist":
        """Checklist par défaut"""
        return EmailChecklist(
            items=[
                {
                    "id": "recipients_correct",
                    "label": "Destinataires vérifiés et corrects",
                    "checked": False,
                    "required": True
                },
                {
                    "id": "evidence_attached",
                    "label": "Sources/evidence attachées",
                    "checked": False,
                    "required": True
                },
                {
                    "id": "tone_appropriate",
                    "label": "Ton approprié et professionnel",
                    "checked": False,
                    "required": True
                },
                {
                    "id": "no_sensitive_info",
                    "label": "Pas d'informations sensibles (mots de passe, IBAN, etc.)",
                    "checked": False,
                    "required": True
                },
                {
                    "id": "spelling_checked",
                    "label": "Orthographe et grammaire vérifiées",
                    "checked": False,
                    "required": False
                },
                {
                    "id": "attachments_valid",
                    "label": "Pièces jointes valides (si applicable)",
                    "checked": False,
                    "required": False
                }
            ]
        )


class EmailPreview(BaseModel):
    """Preview complet d'un email avant envoi"""
    draft_id: str
    subject: str
    body: str
    recipients_count: int
    recipients_preview: List[str] = []  # Premiers emails pour preview
    evidence_count: int
    evidence_summary: List[str] = []
    warnings: List[str] = []
    blocking_issues: List[str] = []
    checklist: EmailChecklist
    can_send: bool = True
    preview_text: str = ""


class EmailSendRequest(BaseModel):
    """Requête d'envoi email"""
    draft_id: str
    checklist_confirmed: bool = False
    force_send: bool = False  # Override warnings (admin only)
    correlation_id: Optional[str] = None


class EmailSendResult(BaseModel):
    """Résultat d'envoi email"""
    draft_id: str
    success: bool
    sent_count: int = 0
    failed_count: int = 0
    errors: List[str] = []
    correlation_id: Optional[str] = None
    sent_at: Optional[datetime] = None


class EmailSafeSendService:
    """
    Service d'envoi sécurisé d'emails.

    Workflow:
    1. generate_draft() - Créer brouillon avec contexte SQL+RAG
    2. generate_preview() - Afficher preview + checklist
    3. User validates checklist
    4. send_email() - Envoyer si checklist validée

    Règles:
    - Preview obligatoire si ≥1 destinataire
    - Checklist obligatoire si evidence < 2
    - Blocage si modifications détectées après preview
    """

    def __init__(self):
        self.drafts: Dict[str, EmailDraft] = {}  # In-memory pour l'instant
        # TODO: Persister dans BDD (table email_drafts)

        logger.info("email_safe_send_service_initialized")

    async def generate_draft(
        self,
        subject: str,
        body: str,
        recipients: List[Recipient],
        evidence: List[Evidence],
        context: Optional[Dict[str, Any]] = None,
        conversation_id: Optional[str] = None,
        user_id: Optional[int] = None,
        priority: EmailPriority = EmailPriority.NORMAL
    ) -> EmailDraft:
        """
        Génère un brouillon d'email avec evidence.

        Args:
            subject: Sujet de l'email
            body: Corps de l'email (HTML ou texte)
            recipients: Liste des destinataires
            evidence: Sources/evidence
            context: Contexte additionnel
            conversation_id: ID de conversation
            user_id: ID utilisateur
            priority: Priorité

        Returns:
            EmailDraft créé
        """
        draft = EmailDraft(
            conversation_id=conversation_id,
            user_id=user_id,
            subject=subject,
            body=body,
            recipients=recipients,
            evidence=evidence,
            context=context or {},
            priority=priority
        )

        # Générer hash initial
        draft.content_hash = draft.generate_content_hash()

        # Sauvegarder
        self.drafts[draft.id] = draft

        logger.info(
            "email_draft_created",
            draft_id=draft.id,
            recipients_count=len(recipients),
            evidence_count=len(evidence),
            conversation_id=conversation_id
        )

        return draft

    async def get_draft(self, draft_id: str) -> Optional[EmailDraft]:
        """Récupère un brouillon par ID"""
        return self.drafts.get(draft_id)

    async def generate_preview(
        self,
        draft_id: str,
        regenerate_checklist: bool = False
    ) -> EmailPreview:
        """
        Génère preview d'un brouillon.

        Args:
            draft_id: ID du brouillon
            regenerate_checklist: Régénérer checklist (après modifications)

        Returns:
            EmailPreview avec warnings et checklist
        """
        draft = await self.get_draft(draft_id)
        if not draft:
            return EmailPreview(
                draft_id=draft_id,
                subject="",
                body="",
                recipients_count=0,
                evidence_count=0,
                checklist=EmailChecklist.default_checklist(),
                can_send=False,
                blocking_issues=["Brouillon non trouvé"]
            )

        logger.info(
            "email_generating_preview",
            draft_id=draft_id,
            recipients_count=len(draft.recipients)
        )

        # Marquer preview comme affiché
        draft.preview_shown = True

        # Warnings
        warnings = []
        blocking_issues = []

        # Vérifier evidence
        if len(draft.evidence) == 0:
            blocking_issues.append("⚠️ Aucune evidence/source - Envoi bloqué")
        elif len(draft.evidence) < 2:
            warnings.append("⚠️ Moins de 2 sources - Vérifiez bien le contenu")

        # Vérifier destinataires
        if len(draft.recipients) == 0:
            blocking_issues.append("⚠️ Aucun destinataire spécifié")
        elif len(draft.recipients) > 50:
            warnings.append(f"⚠️ Envoi massif à {len(draft.recipients)} destinataires - Confirmez bien")

        # Vérifier modifications après preview
        if draft.content_hash and draft.has_been_modified():
            blocking_issues.append("⚠️ Brouillon modifié après preview - Régénérez preview")

        # Détection informations sensibles (simple heuristic)
        sensitive_patterns = ["mot de passe", "password", "iban", "secret", "credentials"]
        body_lower = draft.body.lower()
        for pattern in sensitive_patterns:
            if pattern in body_lower:
                warnings.append(f"⚠️ Potentiellement information sensible détectée: '{pattern}'")

        # Générer checklist
        if regenerate_checklist or not hasattr(draft, 'checklist'):
            checklist = EmailChecklist.default_checklist()
        else:
            checklist = getattr(draft, 'checklist', EmailChecklist.default_checklist())

        # Recipients preview (max 10)
        recipients_preview = [r.email for r in draft.recipients[:10]]
        if len(draft.recipients) > 10:
            recipients_preview.append(f"... et {len(draft.recipients) - 10} autres")

        # Evidence summary
        evidence_summary = [
            f"[{ev.type.value}] {ev.title}" for ev in draft.evidence[:5]
        ]
        if len(draft.evidence) > 5:
            evidence_summary.append(f"... et {len(draft.evidence) - 5} autres sources")

        # Texte preview
        preview_text = self._render_preview_text(draft, warnings, blocking_issues)

        # Peut envoyer ?
        can_send = len(blocking_issues) == 0

        preview = EmailPreview(
            draft_id=draft_id,
            subject=draft.subject,
            body=draft.body[:500] + ("..." if len(draft.body) > 500 else ""),
            recipients_count=len(draft.recipients),
            recipients_preview=recipients_preview,
            evidence_count=len(draft.evidence),
            evidence_summary=evidence_summary,
            warnings=warnings,
            blocking_issues=blocking_issues,
            checklist=checklist,
            can_send=can_send,
            preview_text=preview_text
        )

        logger.info(
            "email_preview_generated",
            draft_id=draft_id,
            can_send=can_send,
            warnings_count=len(warnings),
            blocking_issues_count=len(blocking_issues)
        )

        return preview

    def _render_preview_text(
        self,
        draft: EmailDraft,
        warnings: List[str],
        blocking_issues: List[str]
    ) -> str:
        """Génère le texte de preview"""
        lines = [
            "📧 PREVIEW EMAIL",
            "",
            f"De: {draft.context.get('from_email', 'assistant@disruptiq.com')}",
            f"À: {len(draft.recipients)} destinataire(s)",
            f"Objet: {draft.subject}",
            f"Priorité: {draft.priority.value}",
            "",
            "📋 Evidence:",
            f"  {len(draft.evidence)} source(s)",
        ]

        for ev in draft.evidence[:3]:
            lines.append(f"  • [{ev.type.value}] {ev.title}")

        if blocking_issues:
            lines.append("")
            lines.append("🚫 BLOCAGES:")
            for issue in blocking_issues:
                lines.append(f"  {issue}")

        if warnings:
            lines.append("")
            lines.append("⚠️ AVERTISSEMENTS:")
            for warning in warnings:
                lines.append(f"  {warning}")

        return "\n".join(lines)

    async def validate_checklist(
        self,
        draft_id: str,
        checklist: EmailChecklist
    ) -> bool:
        """
        Valide la checklist d'un brouillon.

        Returns:
            True si tous les items requis sont cochés
        """
        draft = await self.get_draft(draft_id)
        if not draft:
            return False

        # Vérifier que tous les items requis sont cochés
        all_required_checked = all(
            item["checked"]
            for item in checklist.items
            if item.get("required", False)
        )

        checklist.all_checked = all_required_checked

        # Sauvegarder
        draft.checklist_validated = all_required_checked

        logger.info(
            "email_checklist_validated",
            draft_id=draft_id,
            all_checked=all_required_checked
        )

        return all_required_checked

    async def send_email(
        self,
        request: EmailSendRequest,
        email_sender_service = None  # app.services.email_sender.EmailSenderService
    ) -> EmailSendResult:
        """
        Envoie un email après validation.

        Args:
            request: Requête d'envoi
            email_sender_service: Service d'envoi SMTP (injecté)

        Returns:
            EmailSendResult
        """
        draft = await self.get_draft(request.draft_id)
        if not draft:
            return EmailSendResult(
                draft_id=request.draft_id,
                success=False,
                errors=["Brouillon non trouvé"]
            )

        logger.info(
            "email_sending",
            draft_id=request.draft_id,
            recipients_count=len(draft.recipients),
            checklist_confirmed=request.checklist_confirmed
        )

        # Vérifications de sécurité
        errors = []

        # 1. Preview obligatoire
        if not draft.preview_shown:
            errors.append("Preview non affiché - Générez preview d'abord")

        # 2. Checklist obligatoire si evidence < 2
        if len(draft.evidence) < 2 and not draft.checklist_validated:
            errors.append("Checklist non validée - Evidence insuffisante")

        # 3. Checklist confirmée dans la requête
        if not request.checklist_confirmed and not request.force_send:
            errors.append("Checklist non confirmée dans la requête")

        # 4. Modifications détectées
        if draft.has_been_modified():
            errors.append("Brouillon modifié après preview - Régénérez preview")

        # Si erreurs et pas force_send
        if errors and not request.force_send:
            logger.warning(
                "email_send_blocked",
                draft_id=request.draft_id,
                errors=errors
            )
            return EmailSendResult(
                draft_id=request.draft_id,
                success=False,
                errors=errors
            )

        # Envoyer via email_sender_service
        sent_count = 0
        failed_count = 0
        send_errors = []

        if email_sender_service:
            try:
                # Appeler service d'envoi SMTP
                for recipient in draft.recipients:
                    try:
                        # TODO: Appeler vraie méthode SMTP
                        # await email_sender_service.send(
                        #     to=recipient.email,
                        #     subject=draft.subject,
                        #     body=draft.body
                        # )
                        sent_count += 1
                    except Exception as e:
                        failed_count += 1
                        send_errors.append(f"{recipient.email}: {str(e)}")
                        logger.error(
                            "email_send_recipient_error",
                            recipient=recipient.email,
                            error=str(e)
                        )

            except Exception as e:
                logger.error(
                    "email_send_service_error",
                    draft_id=request.draft_id,
                    error=str(e),
                    exc_info=True
                )
                send_errors.append(str(e))
        else:
            # Mode simulation (pas de vrai service)
            sent_count = len(draft.recipients)
            logger.warning(
                "email_sent_simulation_mode",
                draft_id=request.draft_id,
                recipients_count=sent_count
            )

        # Marquer comme envoyé
        if sent_count > 0:
            draft.sent_at = datetime.utcnow()

        success = failed_count == 0

        logger.info(
            "email_send_completed",
            draft_id=request.draft_id,
            sent_count=sent_count,
            failed_count=failed_count,
            success=success
        )

        return EmailSendResult(
            draft_id=request.draft_id,
            success=success,
            sent_count=sent_count,
            failed_count=failed_count,
            errors=send_errors,
            correlation_id=request.correlation_id,
            sent_at=draft.sent_at
        )
