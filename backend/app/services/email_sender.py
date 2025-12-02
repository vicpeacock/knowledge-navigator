"""Service for sending emails (invitations, password reset, etc.)"""
from typing import Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailSender:
    """Service for sending transactional emails"""
    
    def __init__(self):
        self.enabled = settings.smtp_enabled
        self.host = settings.smtp_host
        self.port = settings.smtp_port
        self.use_tls = settings.smtp_use_tls
        self.username = settings.smtp_username
        self.password = settings.smtp_password
        self.from_email = settings.smtp_from_email or settings.smtp_username
        self.from_name = settings.smtp_from_name or "Knowledge Navigator"
    
    def is_configured(self) -> bool:
        """Check if email sending is properly configured"""
        if not self.enabled:
            return False
        if not all([self.host, self.username, self.password, self.from_email]):
            return False
        return True
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: Optional[str] = None,
        text_body: Optional[str] = None,
    ) -> bool:
        """
        Send an email
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML email body (optional)
            text_body: Plain text email body (optional, required if html_body not provided)
        
        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.is_configured():
            logger.warning(
                f"Email sending not configured. Skipping email to {to_email}. "
                f"Enable SMTP in settings to send emails."
            )
            return False
        
        if not html_body and not text_body:
            logger.error("Either html_body or text_body must be provided")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = Header(subject, 'utf-8')
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            
            # Add text and HTML parts
            if text_body:
                text_part = MIMEText(text_body, 'plain', 'utf-8')
                msg.attach(text_part)
            
            if html_body:
                html_part = MIMEText(html_body, 'html', 'utf-8')
                msg.attach(html_part)
            
            # Send email
            if self.use_tls:
                server = smtplib.SMTP(self.host, self.port)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.host, self.port)
            
            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}", exc_info=True)
            return False
    
    async def send_invitation_email(
        self,
        to_email: str,
        user_name: Optional[str],
        verification_token: str,
        admin_name: Optional[str] = None,
    ) -> bool:
        """
        Send user invitation email with verification link
        
        Args:
            to_email: Recipient email address
            user_name: Name of the user being invited
            verification_token: Email verification token
            admin_name: Name of the admin who sent the invitation
        
        Returns:
            True if email sent successfully, False otherwise
        """
        # Use FRONTEND_URL env var if available, otherwise use settings.frontend_url
        import os
        frontend_url = os.getenv("FRONTEND_URL") or settings.frontend_url or "http://localhost:3003"
        verification_url = f"{frontend_url}/auth/verify-email?token={verification_token}"
        
        # HTML email body
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #2563eb; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
                .content {{ background-color: #f9fafb; padding: 30px; border-radius: 0 0 5px 5px; }}
                .button {{ display: inline-block; padding: 12px 24px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; margin-top: 20px; color: #6b7280; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to Knowledge Navigator</h1>
                </div>
                <div class="content">
                    <p>Hello {user_name or 'there'},</p>
                    <p>
                        {'You have been invited by ' + admin_name + ' to join Knowledge Navigator.' if admin_name else 'You have been invited to join Knowledge Navigator.'}
                        Click the button below to verify your email and set up your account.
                    </p>
                    <p style="text-align: center;">
                        <a href="{verification_url}" class="button">Verify Email & Set Password</a>
                    </p>
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; color: #2563eb;">{verification_url}</p>
                    <p>This link will expire in 7 days.</p>
                </div>
                <div class="footer">
                    <p>If you didn't expect this email, you can safely ignore it.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text email body
        text_body = f"""
Welcome to Knowledge Navigator

Hello {user_name or 'there'},

{'You have been invited by ' + admin_name + ' to join Knowledge Navigator.' if admin_name else 'You have been invited to join Knowledge Navigator.'}
Click the link below to verify your email and set up your account:

{verification_url}

This link will expire in 7 days.

If you didn't expect this email, you can safely ignore it.
        """
        
        return await self.send_email(
            to_email=to_email,
            subject="Welcome to Knowledge Navigator - Verify Your Email",
            html_body=html_body,
            text_body=text_body,
        )


# Global instance
_email_sender = EmailSender()


def get_email_sender() -> EmailSender:
    """Get the global email sender instance"""
    return _email_sender

