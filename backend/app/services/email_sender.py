"""
Email Sender Service - Sends digest emails via SMTP
"""

import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
import structlog

logger = structlog.get_logger()


class EmailSenderService:
    """Service for sending emails via SMTP"""

    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "localhost")  # Défaut MailHog
        self.smtp_port = int(os.getenv("SMTP_PORT", "1025"))  # Port MailHog
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.use_tls = os.getenv("SMTP_USE_TLS", "false").lower() == "true"
        self.from_email = os.getenv("SMTP_FROM_EMAIL", self.smtp_user or "noreply@disruptiq.local")
        self.from_name = os.getenv("SMTP_FROM_NAME", "DisruptIQ")

    def send_digest_email(
        self,
        to_emails: List[str],
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send digest email to recipients

        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            html_content: HTML content of email
            text_content: Plain text fallback (optional)

        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            # Validate configuration - credentials optional for MailHog
            if not to_emails:
                logger.error("no_recipients", message="No recipients specified")
                return False

            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = ", ".join(to_emails)

            # Add plain text version (fallback)
            if text_content:
                part1 = MIMEText(text_content, "plain", "utf-8")
                msg.attach(part1)

            # Add HTML version
            part2 = MIMEText(html_content, "html", "utf-8")
            msg.attach(part2)

            logger.info(
                "sending_email",
                recipients=len(to_emails),
                subject=subject,
                smtp_host=self.smtp_host
            )

            # Connect to SMTP server and send
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                # TLS only if configured (not needed for MailHog)
                if self.use_tls:
                    server.starttls()
                # Login only if credentials provided (not needed for MailHog)
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info("email_sent_successfully", recipients=len(to_emails))
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error("smtp_authentication_failed", error=str(e))
            return False
        except smtplib.SMTPException as e:
            logger.error("smtp_error", error=str(e))
            return False
        except Exception as e:
            logger.error("email_send_failed", error=str(e))
            return False

    def format_digest_html(self, digest_data: dict) -> str:
        """
        Format digest data as HTML email

        Args:
            digest_data: Digest data from API

        Returns:
            HTML string
        """
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                .header h1 {{ margin: 0; font-size: 28px; }}
                .header p {{ margin: 10px 0 0 0; opacity: 0.9; }}
                .content {{ background: #f8f9fa; padding: 20px; }}
                .stats {{ display: flex; justify-content: space-around; margin: 20px 0; }}
                .stat {{ text-align: center; padding: 15px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); flex: 1; margin: 0 5px; }}
                .stat-number {{ font-size: 32px; font-weight: bold; margin: 0; }}
                .stat-label {{ color: #666; margin: 5px 0 0 0; font-size: 14px; }}
                .urgent .stat-number {{ color: #ef4444; }}
                .important .stat-number {{ color: #f59e0b; }}
                .routine .stat-number {{ color: #10b981; }}
                .section {{ background: white; margin: 20px 0; padding: 20px; border-radius: 8px; border-left: 4px solid #667eea; }}
                .section-title {{ font-size: 20px; font-weight: bold; margin: 0 0 15px 0; display: flex; align-items: center; gap: 8px; }}
                .email-item {{ background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 6px; border-left: 3px solid #ccc; }}
                .email-item.urgent {{ border-left-color: #ef4444; }}
                .email-item.important {{ border-left-color: #f59e0b; }}
                .email-subject {{ font-weight: bold; margin: 0 0 5px 0; }}
                .email-sender {{ color: #666; font-size: 14px; margin: 0 0 8px 0; }}
                .email-snippet {{ color: #333; font-size: 14px; margin: 0; }}
                .footer {{ background: #333; color: white; padding: 20px; text-align: center; border-radius: 0 0 10px 10px; font-size: 14px; }}
                .footer a {{ color: #667eea; text-decoration: none; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📧 Digest Quotidien</h1>
                <p>{digest_data.get('date', '')}</p>
            </div>

            <div class="content">
                <div class="stats">
                    <div class="stat urgent">
                        <p class="stat-number">{digest_data.get('urgent', {}).get('count', 0)}</p>
                        <p class="stat-label">🔴 Urgents</p>
                    </div>
                    <div class="stat important">
                        <p class="stat-number">{digest_data.get('important', {}).get('count', 0)}</p>
                        <p class="stat-label">🟠 Importants</p>
                    </div>
                    <div class="stat routine">
                        <p class="stat-number">{digest_data.get('routine', {}).get('count', 0)}</p>
                        <p class="stat-label">🟢 Routine</p>
                    </div>
                </div>
        """

        # Add urgent emails
        urgent_emails = digest_data.get("urgent", {}).get("emails", [])
        if urgent_emails:
            html += """
                <div class="section">
                    <h2 class="section-title">🔴 Emails Urgents</h2>
            """
            for email in urgent_emails[:5]:  # Limit to 5
                html += f"""
                    <div class="email-item urgent">
                        <p class="email-subject">{email.get('subject', 'Sans objet')}</p>
                        <p class="email-sender">De: {email.get('sender', 'Inconnu')}</p>
                        <p class="email-snippet">{email.get('snippet', email.get('body', ''))[:150]}...</p>
                    </div>
                """
            html += "</div>"

        # Add important emails
        important_emails = digest_data.get("important", {}).get("emails", [])
        if important_emails:
            html += """
                <div class="section">
                    <h2 class="section-title">🟠 Emails Importants</h2>
            """
            for email in important_emails[:5]:  # Limit to 5
                html += f"""
                    <div class="email-item important">
                        <p class="email-subject">{email.get('subject', 'Sans objet')}</p>
                        <p class="email-sender">De: {email.get('sender', 'Inconnu')}</p>
                        <p class="email-snippet">{email.get('snippet', email.get('body', ''))[:150]}...</p>
                    </div>
                """
            html += "</div>"

        html += """
            </div>

            <div class="footer">
                <p>DisruptIQ - Assistant IA pour Syndics</p>
                <p><a href="http://localhost:3000">Voir le dashboard complet →</a></p>
            </div>
        </body>
        </html>
        """

        return html

    def format_digest_text(self, digest_data: dict) -> str:
        """
        Format digest data as plain text (fallback)

        Args:
            digest_data: Digest data from API

        Returns:
            Plain text string
        """
        text = f"DisruptIQ - Digest Quotidien\n"
        text += f"Date: {digest_data.get('date', '')}\n\n"
        text += f"=== Résumé ===\n"
        text += f"🔴 Urgents: {digest_data.get('urgent', {}).get('count', 0)}\n"
        text += f"🟠 Importants: {digest_data.get('important', {}).get('count', 0)}\n"
        text += f"🟢 Routine: {digest_data.get('routine', {}).get('count', 0)}\n\n"

        # Add urgent emails
        urgent_emails = digest_data.get("urgent", {}).get("emails", [])
        if urgent_emails:
            text += "=== Emails Urgents ===\n"
            for email in urgent_emails[:5]:
                text += f"\n- {email.get('subject', 'Sans objet')}\n"
                text += f"  De: {email.get('sender', 'Inconnu')}\n"
                text += f"  {email.get('snippet', email.get('body', ''))[:100]}...\n"

        # Add important emails
        important_emails = digest_data.get("important", {}).get("emails", [])
        if important_emails:
            text += "\n=== Emails Importants ===\n"
            for email in important_emails[:5]:
                text += f"\n- {email.get('subject', 'Sans objet')}\n"
                text += f"  De: {email.get('sender', 'Inconnu')}\n"
                text += f"  {email.get('snippet', email.get('body', ''))[:100]}...\n"

        text += "\n\nVoir le dashboard complet: http://localhost:3000"

        return text
