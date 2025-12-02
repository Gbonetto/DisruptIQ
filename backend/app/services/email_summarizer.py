"""
Email Summarizer Service - Phase 4 MailDigest Pro

Generates intelligent summaries and suggested actions for emails
using LLM analysis. Optimized for batch processing.

Author: Claude Code - Phase 4 MailDigest Pro
"""

import structlog
import asyncio
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from datetime import datetime, timezone

from app.services.llm_service import LLMService

logger = structlog.get_logger()


# Category badges for visual categorization
CATEGORY_BADGES = {
    "fuite": "[FUITE]",
    "water": "[FUITE]",
    "eau": "[FUITE]",
    "inondation": "[FUITE]",
    "dégât des eaux": "[FUITE]",
    "devis": "[DEVIS]",
    "quote": "[DEVIS]",
    "proposition": "[DEVIS]",
    "offre": "[DEVIS]",
    "facture": "[FACTURE]",
    "invoice": "[FACTURE]",
    "paiement": "[FACTURE]",
    "travaux": "[TRAVAUX]",
    "rénovation": "[TRAVAUX]",
    "réfection": "[TRAVAUX]",
    "toiture": "[TRAVAUX]",
    "plomberie": "[TRAVAUX]",
    "électricité": "[TRAVAUX]",
    "ascenseur": "[TRAVAUX]",
    "assemblée": "[AG]",
    "ag ": "[AG]",
    "convocation": "[AG]",
    "charges": "[CHARGES]",
    "appel de fonds": "[CHARGES]",
    "trimestre": "[CHARGES]",
    "réclamation": "[RÉCLAMATION]",
    "plainte": "[RÉCLAMATION]",
    "nuisance": "[RÉCLAMATION]",
    "bruit": "[RÉCLAMATION]",
    "sinistre": "[SINISTRE]",
    "assurance": "[SINISTRE]",
    "dommage": "[SINISTRE]",
}


def format_relative_time(dt: Union[str, datetime, None]) -> str:
    """
    Convert a datetime to a human-readable relative time in French.

    Args:
        dt: datetime object, ISO string, or None

    Returns:
        str like "il y a 2h", "il y a 15min", "hier", etc.
    """
    if dt is None:
        return ""

    # Parse string to datetime if needed
    if isinstance(dt, str):
        try:
            # Try ISO format
            if 'T' in dt:
                dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
            else:
                dt = datetime.fromisoformat(dt)
        except (ValueError, AttributeError):
            return dt  # Return original string if parsing fails

    # Ensure datetime is timezone-aware
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    diff = now - dt
    seconds = diff.total_seconds()

    if seconds < 0:
        return "à l'instant"
    elif seconds < 60:
        return "à l'instant"
    elif seconds < 3600:  # Less than 1 hour
        minutes = int(seconds / 60)
        return f"il y a {minutes}min"
    elif seconds < 86400:  # Less than 24 hours
        hours = int(seconds / 3600)
        return f"il y a {hours}h"
    elif seconds < 172800:  # Less than 48 hours
        return "hier"
    elif seconds < 604800:  # Less than 7 days
        days = int(seconds / 86400)
        return f"il y a {days}j"
    else:
        # Format as date for older emails
        return dt.strftime("%d/%m")


def detect_category_badge(subject: str, body: str = "") -> str:
    """
    Detect email category and return appropriate badge.

    Args:
        subject: Email subject
        body: Email body (optional, first 200 chars used)

    Returns:
        Badge string like "[FUITE]" or empty string
    """
    text_to_check = (subject + " " + body[:200]).lower()

    for keyword, badge in CATEGORY_BADGES.items():
        if keyword in text_to_check:
            return badge

    return ""


@dataclass
class EmailEnrichment:
    """Enriched email data for digest display"""
    summary: str  # 1-2 sentence summary
    suggested_action: str  # What the syndic should do
    has_attachments: bool
    attachment_summary: str  # "2 PDFs, 1 image"


class EmailSummarizer:
    """
    Email Summarizer Service

    Generates summaries and suggested actions for emails.
    Optimized for batch processing to minimize LLM calls.
    """

    def __init__(self):
        self.llm_service = LLMService()
        logger.info("email_summarizer_initialized")

    async def enrich_email(
        self,
        subject: str,
        body: str,
        sender: str,
        attachments: List[Dict[str, Any]] = None,
        urgency: str = "routine"
    ) -> EmailEnrichment:
        """
        Enrich a single email with summary and action

        Args:
            subject: Email subject
            body: Email body text
            sender: Sender email/name
            attachments: List of attachment info dicts
            urgency: urgent/important/routine

        Returns:
            EmailEnrichment with summary and action
        """
        attachments = attachments or []

        # Process attachments
        has_attachments = len(attachments) > 0
        attachment_summary = self._format_attachment_summary(attachments)

        # Generate summary and action via LLM
        summary, action = await self._generate_summary_and_action(
            subject=subject,
            body=body,
            sender=sender,
            urgency=urgency,
            has_attachments=has_attachments
        )

        return EmailEnrichment(
            summary=summary,
            suggested_action=action,
            has_attachments=has_attachments,
            attachment_summary=attachment_summary
        )

    async def enrich_emails_batch(
        self,
        emails: List[Dict[str, Any]],
        batch_size: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Enrich multiple emails in batch for efficiency

        Args:
            emails: List of email dicts with subject, body, sender, attachments, urgency
            batch_size: Number of emails to process concurrently

        Returns:
            List of email dicts with added summary, suggested_action, etc.
        """
        enriched = []

        for i in range(0, len(emails), batch_size):
            batch = emails[i:i + batch_size]

            # Process batch concurrently
            tasks = [
                self.enrich_email(
                    subject=email.get('subject', 'Sans objet'),
                    body=email.get('body', ''),
                    sender=email.get('sender', 'Inconnu'),
                    attachments=email.get('attachments', []),
                    urgency=email.get('urgency', 'routine')
                )
                for email in batch
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for email, result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.warning("email_enrichment_failed",
                                 subject=email.get('subject'),
                                 error=str(result))
                    # Fallback values
                    email['summary'] = self._generate_fallback_summary(email)
                    email['suggested_action'] = "Consulter le message"
                    email['has_attachments'] = len(email.get('attachments', [])) > 0
                    email['attachment_summary'] = self._format_attachment_summary(
                        email.get('attachments', [])
                    )
                else:
                    email['summary'] = result.summary
                    email['suggested_action'] = result.suggested_action
                    email['has_attachments'] = result.has_attachments
                    email['attachment_summary'] = result.attachment_summary

                enriched.append(email)

        logger.info("emails_enriched_batch", count=len(enriched))
        return enriched

    async def _generate_summary_and_action(
        self,
        subject: str,
        body: str,
        sender: str,
        urgency: str,
        has_attachments: bool
    ) -> tuple[str, str]:
        """Generate summary and action using LLM"""

        # Truncate body for context efficiency
        body_truncated = body[:1500] if len(body) > 1500 else body

        prompt = f"""Tu es un assistant pour syndic de copropriété. Analyse cet email et fournis:
1. Un RESUME en 1-2 phrases maximum (concis, informatif)
2. Une ACTION SUGGEREE (ce que le syndic devrait faire)

EMAIL:
De: {sender}
Objet: {subject}
Urgence: {urgency}
Pièces jointes: {"Oui" if has_attachments else "Non"}

Contenu:
{body_truncated}

Réponds UNIQUEMENT dans ce format exact:
RESUME: [résumé concis]
ACTION: [action suggérée courte]"""

        try:
            response = await self.llm_service.generate_response(
                prompt,
                max_tokens=200,
                temperature=0.3
            )

            return self._parse_llm_response(response, subject)

        except Exception as e:
            logger.warning("llm_summary_failed", error=str(e))
            return (
                self._generate_fallback_summary({'subject': subject, 'sender': sender}),
                "Consulter le message"
            )

    def _parse_llm_response(self, response: str, subject: str) -> tuple[str, str]:
        """Parse LLM response to extract summary and action"""
        summary = ""
        action = "Consulter le message"

        lines = response.strip().split('\n')
        for line in lines:
            line_clean = line.strip()
            if line_clean.upper().startswith('RESUME:'):
                summary = line_clean[7:].strip()
            elif line_clean.upper().startswith('RÉSUMÉ:'):
                summary = line_clean[7:].strip()
            elif line_clean.upper().startswith('ACTION:'):
                action = line_clean[7:].strip()

        # Fallback if parsing failed
        if not summary:
            summary = f"Email concernant: {subject[:100]}"

        return summary, action

    def _generate_fallback_summary(self, email: Dict[str, Any]) -> str:
        """Generate a basic summary without LLM"""
        subject = email.get('subject', 'Sans objet')
        sender = email.get('sender', 'Inconnu')

        # Extract sender name if email format
        sender_name = sender.split('@')[0] if '@' in sender else sender
        sender_name = sender_name.replace('.', ' ').replace('_', ' ').title()

        return f"Message de {sender_name} concernant: {subject[:80]}"

    def _format_attachment_summary(self, attachments: List[Dict[str, Any]]) -> str:
        """Format attachment list into readable summary"""
        if not attachments:
            return ""

        count = len(attachments)
        if count == 1:
            attachment = attachments[0]
            filename = attachment.get('filename', 'fichier')
            return f"1 pièce jointe ({filename})"

        # Group by type
        types = {}
        for att in attachments:
            mime = att.get('mime_type', 'application/octet-stream')
            filename = att.get('filename', '')

            if 'pdf' in mime.lower() or filename.lower().endswith('.pdf'):
                types['PDF'] = types.get('PDF', 0) + 1
            elif 'image' in mime.lower() or any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
                types['image'] = types.get('image', 0) + 1
            elif 'word' in mime.lower() or filename.lower().endswith('.docx') or filename.lower().endswith('.doc'):
                types['Word'] = types.get('Word', 0) + 1
            elif 'excel' in mime.lower() or filename.lower().endswith('.xlsx') or filename.lower().endswith('.xls'):
                types['Excel'] = types.get('Excel', 0) + 1
            else:
                types['fichier'] = types.get('fichier', 0) + 1

        parts = []
        for type_name, type_count in types.items():
            if type_count == 1:
                parts.append(f"1 {type_name}")
            else:
                parts.append(f"{type_count} {type_name}s")

        return f"{count} pièces jointes ({', '.join(parts)})"


# Singleton instance
_email_summarizer: Optional[EmailSummarizer] = None


def get_email_summarizer() -> EmailSummarizer:
    """Get or create singleton email summarizer"""
    global _email_summarizer
    if _email_summarizer is None:
        _email_summarizer = EmailSummarizer()
    return _email_summarizer
