from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import imaplib
import email
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
try:
    from msal import ConfidentialClientApplication
except ImportError:
    ConfidentialClientApplication = None
import httpx
import logging
from app.core.config import settings
from app.services.exceptions import IntegrationAuthError

logger = logging.getLogger(__name__)


class EmailService:
    """Service for managing email integrations (Gmail, iCloud, Outlook)"""
    
    def __init__(self):
        # Store services per integration (keyed by integration_id)
        self._services: Dict[str, Any] = {}
    
    def _get_service_key(self, provider: str, integration_id: Optional[str] = None) -> str:
        """Generate a key for service storage"""
        return f"{provider}_{integration_id or 'default'}"
    
    # Gmail
    def create_gmail_oauth_flow(self) -> Flow:
        """Create OAuth2 flow for Gmail"""
        if not settings.google_client_id or not settings.google_client_secret:
            raise ValueError("Google OAuth credentials not configured")
        
        # Use BASE_URL from environment if available, otherwise use settings
        import os
        base_url = os.getenv("BASE_URL") or getattr(settings, "base_url", None) or "http://localhost:8000"
        redirect_uri = f"{base_url}/api/integrations/emails/oauth/callback"
        
        # Log the redirect_uri being used for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"🔵 Email OAuth - Using redirect_uri: {redirect_uri}")
        print(f"🔵 Email OAuth - Using redirect_uri: {redirect_uri}", flush=True)
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [redirect_uri],
                }
            },
                scopes=[
                    "openid",  # Required for ID token with email
                    "email",  # Required for email in ID token
                    "https://www.googleapis.com/auth/gmail.readonly",
                    "https://www.googleapis.com/auth/gmail.modify",  # Per archiviare/modificare email
                    "https://www.googleapis.com/auth/gmail.send",  # Per inviare email
                ],
            redirect_uri=redirect_uri,
        )
        
        return flow
    
    async def setup_gmail(
        self,
        token_dict: Dict[str, Any],
        integration_id: Optional[str] = None,
    ):
        """Setup Gmail integration with token"""
        try:
            creds = Credentials.from_authorized_user_info(token_dict)
        except Exception as exc:
            raise IntegrationAuthError("gmail", "invalid_credentials", str(exc)) from exc

        try:
            if creds.expired:
                if creds.refresh_token:
                    creds.refresh(Request())
                else:
                    raise IntegrationAuthError("gmail", "refresh_token_missing")
        except RefreshError as exc:
            raise IntegrationAuthError("gmail", "token_refresh_failed", str(exc)) from exc

        try:
            service = build("gmail", "v1", credentials=creds)
        except HttpError as exc:
            raise IntegrationAuthError("gmail", "api_unavailable", str(exc)) from exc

        self._services[self._get_service_key("gmail", integration_id)] = service
        return service
    
    async def get_gmail_messages(
        self,
        max_results: int = 10,
        query: Optional[str] = None,
        integration_id: Optional[str] = None,
        include_body: bool = False,
    ) -> List[Dict[str, Any]]:
        """Get messages from Gmail"""
        import asyncio
        
        service_key = self._get_service_key("gmail", integration_id)
        service = self._services.get(service_key)
        
        if not service:
            raise IntegrationAuthError("gmail", "service_not_initialized")
        
        query_params = {"maxResults": max_results}
        if query:
            query_params["q"] = query
        
        try:
            # Wrap Gmail API calls in timeout to prevent hanging
            # Gmail API can be slow, especially with many emails
            async def _fetch_messages():
                loop = asyncio.get_event_loop()
                # Run blocking Gmail API call in thread pool
                messages_result = await loop.run_in_executor(
                    None,
                    lambda: service.users().messages().list(userId="me", **query_params).execute()
                )
                return messages_result
            
            # Set timeout to 60 seconds for Gmail API calls
            messages_result = await asyncio.wait_for(_fetch_messages(), timeout=60.0)
            
            messages = messages_result.get("messages", [])
            result = []
            
            # Process messages with timeout for each detail fetch
            async def _fetch_message_detail(msg_id: str):
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(
                    None,
                    lambda: service.users().messages().get(
                        userId="me", 
                        id=msg_id, 
                        format="full" if include_body else "metadata"
                    ).execute()
                )
            
            for msg in messages:
                try:
                    # Set timeout to 30 seconds per message detail
                    msg_detail = await asyncio.wait_for(
                        _fetch_message_detail(msg["id"]), 
                        timeout=30.0
                    )
                except asyncio.TimeoutError:
                    logger.error(f"Timeout fetching Gmail message detail for {msg['id']}")
                    # Skip this message and continue with others
                    continue
                except Exception as e:
                    logger.error(f"Error fetching Gmail message detail for {msg['id']}: {e}")
                    # Skip this message and continue with others
                    continue
                
                headers = {h["name"]: h["value"] for h in msg_detail["payload"].get("headers", [])}
                
                # Extract Gmail labels (categories)
                label_ids = msg_detail.get("labelIds", [])
                
                email_data = {
                    "id": msg_detail["id"],
                    "subject": headers.get("Subject", ""),
                    "from": headers.get("From", ""),
                    "to": headers.get("To", ""),
                    "date": headers.get("Date", ""),
                    "snippet": msg_detail.get("snippet", ""),
                    "thread_id": msg_detail.get("threadId", ""),
                    "labels": label_ids,
                    "category": self._extract_category(label_ids),
                }
                
                # Extract body if requested
                if include_body:
                    email_data["body"] = self._extract_email_body(msg_detail["payload"])
                
                result.append(email_data)
            
            return result
        except asyncio.TimeoutError:
            logger.error("Timeout fetching Gmail messages list")
            raise ValueError("Gmail API timeout: The request took too long. Please try again.")
        except HttpError as exc:
            if exc.resp.status in (401, 403):
                # Token revoked or scope insufficient
                raise IntegrationAuthError("gmail", "unauthorized", str(exc)) from exc
            raise ValueError(f"Error fetching Gmail messages: {str(exc)}") from exc
        except IntegrationAuthError:
            raise
    
    def _extract_category(self, label_ids: List[str]) -> str:
        """
        Extract Gmail category from labels.
        Returns: "direct" | "mailing_list" | "promotional" | "update" | "social" | "unknown"
        """
        category_mapping = {
            "CATEGORY_PERSONAL": "direct",
            "CATEGORY_SOCIAL": "social",
            "CATEGORY_PROMOTIONS": "promotional",
            "CATEGORY_UPDATES": "update",
            "CATEGORY_FORUMS": "mailing_list",
        }
        
        for label in label_ids:
            if label in category_mapping:
                return category_mapping[label]
        
        # Fallback: check if it looks like a mailing list based on common patterns
        # This is a simple heuristic - can be improved with LLM analysis
        return "unknown"
    
    def _extract_email_body(self, payload: Dict[str, Any]) -> str:
        """Extract text body from email payload"""
        body = ""
        
        if "parts" in payload:
            for part in payload["parts"]:
                mime_type = part.get("mimeType", "")
                if mime_type == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                        break
                elif mime_type == "text/html" and not body:
                    data = part.get("body", {}).get("data", "")
                    if data:
                        body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        else:
            # Simple email without multipart
            mime_type = payload.get("mimeType", "")
            if mime_type == "text/plain":
                data = payload.get("body", {}).get("data", "")
                if data:
                    body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        
        return body
    
    async def archive_email(
        self,
        email_id: str,
        integration_id: Optional[str] = None,
    ) -> bool:
        """
        Archive an email by removing the INBOX label.
        
        Args:
            email_id: Gmail message ID
            integration_id: Optional integration ID
            
        Returns:
            True if archived successfully, False otherwise
        """
        try:
            service_key = self._get_service_key("gmail", integration_id)
            service = self._services.get(service_key)
            
            if not service:
                raise IntegrationAuthError("gmail", "service_not_initialized")
            
            # Remove INBOX label to archive the email
            service.users().messages().modify(
                userId="me",
                id=email_id,
                body={"removeLabelIds": ["INBOX"]}
            ).execute()
            
            logger.info(f"Email {email_id} archived successfully")
            return True
        except HttpError as exc:
            if exc.resp.status in (401, 403):
                raise IntegrationAuthError("gmail", "unauthorized", str(exc)) from exc
            logger.error(f"Error archiving email {email_id}: {exc}")
            raise ValueError(f"Error archiving email: {str(exc)}") from exc
        except IntegrationAuthError:
            raise
        except Exception as exc:
            logger.error(f"Unexpected error archiving email {email_id}: {exc}", exc_info=True)
            raise ValueError(f"Error archiving email: {str(exc)}") from exc
    
    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        body_html: Optional[str] = None,
        integration_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send an email via Gmail API.
        
        Args:
            to: Recipient email address
            subject: Email subject
            body: Plain text email body
            body_html: Optional HTML email body
            integration_id: Optional integration ID
            
        Returns:
            Dict with message_id and thread_id if successful
        """
        try:
            service_key = self._get_service_key("gmail", integration_id)
            service = self._services.get(service_key)
            
            if not service:
                raise IntegrationAuthError("gmail", "service_not_initialized")
            
            # Create message
            message = MIMEMultipart('alternative')
            message['To'] = to
            message['Subject'] = subject
            
            # Add text and HTML parts
            if body:
                text_part = MIMEText(body, 'plain', 'utf-8')
                message.attach(text_part)
            
            if body_html:
                html_part = MIMEText(body_html, 'html', 'utf-8')
                message.attach(html_part)
            elif not body:
                # If no body provided, use empty text
                text_part = MIMEText("", 'plain', 'utf-8')
                message.attach(text_part)
            
            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            # Send message
            result = service.users().messages().send(
                userId="me",
                body={"raw": raw_message}
            ).execute()
            
            logger.info(f"Email sent successfully to {to}, message_id: {result.get('id')}")
            return {
                "message_id": result.get("id"),
                "thread_id": result.get("threadId"),
                "success": True
            }
        except HttpError as exc:
            if exc.resp.status in (401, 403):
                raise IntegrationAuthError("gmail", "unauthorized", str(exc)) from exc
            logger.error(f"Error sending email to {to}: {exc}")
            raise ValueError(f"Error sending email: {str(exc)}") from exc
        except IntegrationAuthError:
            raise
        except Exception as exc:
            logger.error(f"Unexpected error sending email to {to}: {exc}", exc_info=True)
            raise ValueError(f"Error sending email: {str(exc)}") from exc
    
    async def reply_to_email(
        self,
        email_id: str,
        body: str,
        body_html: Optional[str] = None,
        integration_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Reply to an email via Gmail API.
        
        Args:
            email_id: Gmail message ID to reply to
            body: Reply body (plain text)
            body_html: Optional HTML reply body
            integration_id: Optional integration ID
            
        Returns:
            Dict with message_id and thread_id if successful
        """
        try:
            service_key = self._get_service_key("gmail", integration_id)
            service = self._services.get(service_key)
            
            if not service:
                raise IntegrationAuthError("gmail", "service_not_initialized")
            
            # Get original message to extract headers
            original_msg = service.users().messages().get(
                userId="me",
                id=email_id,
                format="metadata",
                metadataHeaders=["From", "To", "Subject", "References", "In-Reply-To"]
            ).execute()
            
            headers = {h["name"]: h["value"] for h in original_msg["payload"].get("headers", [])}
            thread_id = original_msg.get("threadId")
            
            # Create reply message
            message = MIMEMultipart('alternative')
            message['To'] = headers.get("From", "")
            message['Subject'] = "Re: " + headers.get("Subject", "").replace("Re: ", "").replace("RE: ", "")
            
            # Set In-Reply-To and References for threading
            if "Message-ID" in headers:
                message['In-Reply-To'] = headers["Message-ID"]
                message['References'] = headers.get("References", "") + " " + headers["Message-ID"]
            
            # Add text and HTML parts
            if body:
                text_part = MIMEText(body, 'plain', 'utf-8')
                message.attach(text_part)
            
            if body_html:
                html_part = MIMEText(body_html, 'html', 'utf-8')
                message.attach(html_part)
            elif not body:
                # If no body provided, use empty text
                text_part = MIMEText("", 'plain', 'utf-8')
                message.attach(text_part)
            
            # Encode message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            # Send reply
            result = service.users().messages().send(
                userId="me",
                body={
                    "raw": raw_message,
                    "threadId": thread_id  # Maintain thread
                }
            ).execute()
            
            logger.info(f"Reply sent successfully, message_id: {result.get('id')}, thread_id: {thread_id}")
            return {
                "message_id": result.get("id"),
                "thread_id": result.get("threadId"),
                "success": True
            }
        except HttpError as exc:
            if exc.resp.status in (401, 403):
                raise IntegrationAuthError("gmail", "unauthorized", str(exc)) from exc
            logger.error(f"Error replying to email {email_id}: {exc}")
            raise ValueError(f"Error replying to email: {str(exc)}") from exc
        except IntegrationAuthError:
            raise
        except Exception as exc:
            logger.error(f"Unexpected error replying to email {email_id}: {exc}", exc_info=True)
            raise ValueError(f"Error replying to email: {str(exc)}") from exc
    
    # iCloud Mail (IMAP)
    async def setup_icloud(
        self,
        email: str,
        password: str,
        imap_server: str = "imap.mail.me.com",
        imap_port: int = 993,
    ):
        """Setup iCloud Mail integration via IMAP"""
        self.imap_client = imaplib.IMAP4_SSL(imap_server, imap_port)
        self.imap_client.login(email, password)
    
    async def get_icloud_messages(
        self,
        folder: str = "INBOX",
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get messages from iCloud Mail"""
        if not self.imap_client:
            raise ValueError("iCloud Mail not configured")
        
        self.imap_client.select(folder)
        status, messages = self.imap_client.search(None, "ALL")
        
        if status != "OK":
            return []
        
        email_ids = messages[0].split()
        email_ids = email_ids[-max_results:]  # Get most recent
        
        result = []
        for email_id in email_ids:
            status, msg_data = self.imap_client.fetch(email_id, "(RFC822)")
            
            if status == "OK":
                msg = email.message_from_bytes(msg_data[0][1])
                
                subject = decode_header(msg["Subject"])[0][0]
                if isinstance(subject, bytes):
                    subject = subject.decode()
                
                result.append({
                    "id": email_id.decode(),
                    "subject": subject,
                    "from": msg["From"],
                    "date": msg["Date"],
                })
        
        return result
    
    # Microsoft Outlook
    async def setup_outlook(
        self,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        access_token: Optional[str] = None,
    ):
        """Setup Microsoft Outlook integration"""
        self.microsoft_app = ConfidentialClientApplication(
            client_id,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
            client_credential=client_secret,
        )
        
        if access_token:
            self.microsoft_token = access_token
        else:
            raise NotImplementedError("OAuth flow not implemented")
    
    async def get_outlook_messages(
        self,
        max_results: int = 10,
        folder: str = "Inbox",
    ) -> List[Dict[str, Any]]:
        """Get messages from Microsoft Outlook"""
        if not hasattr(self, "microsoft_token"):
            raise ValueError("Microsoft Outlook not configured")
        
        headers = {"Authorization": f"Bearer {self.microsoft_token}"}
        params = {
            "$top": max_results,
            "$orderby": "receivedDateTime desc",
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://graph.microsoft.com/v1.0/me/mailFolders/{folder}/messages",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            return response.json().get("value", [])

