from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
try:
    import caldav
except ImportError:
    caldav = None  # Optional for Apple Calendar
try:
    from msal import ConfidentialClientApplication
except ImportError:
    ConfidentialClientApplication = None  # Optional for Microsoft
import httpx
import json
from app.core.config import settings


class CalendarService:
    """Service for managing calendar integrations (Google, Apple, Microsoft)"""
    
    def __init__(self):
        # Store services per integration (keyed by integration_id)
        self._services: Dict[str, Any] = {}
    
    def _get_service_key(self, provider: str, integration_id: Optional[str] = None) -> str:
        """Generate a key for service storage"""
        return f"{provider}_{integration_id or 'default'}"
    
    # Google Calendar
    def create_google_oauth_flow(self, state: Optional[str] = None) -> Flow:
        """Create OAuth2 flow for Google Calendar"""
        if not settings.google_client_id or not settings.google_client_secret:
            raise ValueError("Google OAuth credentials not configured")
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [settings.google_redirect_uri_calendar],
                }
            },
            scopes=[
                "https://www.googleapis.com/auth/calendar.readonly",
                "https://www.googleapis.com/auth/calendar.events",
            ],
            redirect_uri=settings.google_redirect_uri_calendar,
        )
        
        if state:
            flow.state = state
        
        return flow
    
    async def setup_google(
        self,
        token_dict: Dict[str, Any],
        integration_id: Optional[str] = None,
    ):
        """Setup Google Calendar integration with token"""
        creds = Credentials.from_authorized_user_info(token_dict)
        
        # Refresh token if needed
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        
        service = build("calendar", "v3", credentials=creds)
        self._services[self._get_service_key("google", integration_id)] = service
        
        return service
    
    async def get_google_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        max_results: int = 50,
        integration_id: Optional[str] = None,
        calendar_id: str = "primary",
    ) -> List[Dict[str, Any]]:
        """Get events from Google Calendar"""
        service_key = self._get_service_key("google", integration_id)
        service = self._services.get(service_key)
        
        if not service:
            raise ValueError(f"Google Calendar not configured for integration {integration_id}")
        
        # Default: next 7 days if no time specified
        if not start_time:
            start_time = datetime.now(timezone.utc)
        if not end_time:
            end_time = start_time + timedelta(days=7)
        
        # Ensure timezone-aware
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        
        try:
            events_result = (
                service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=start_time.isoformat(),
                    timeMax=end_time.isoformat(),
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            
            items = events_result.get("items", [])
            
            # Format events for easier consumption
            formatted_events = []
            for event in items:
                formatted = self._format_google_event(event)
                formatted_events.append(formatted)
            
            return formatted_events
        except Exception as e:
            raise ValueError(f"Error fetching Google Calendar events: {str(e)}")
    
    def _format_google_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Format Google Calendar event to a more readable format"""
        start = event.get("start", {})
        end = event.get("end", {})
        
        # Parse datetime
        start_datetime_str = start.get("dateTime") or start.get("date")
        end_datetime_str = end.get("dateTime") or end.get("date")
        
        try:
            if "T" in start_datetime_str:
                start_dt = datetime.fromisoformat(start_datetime_str.replace("Z", "+00:00"))
            else:
                start_dt = datetime.strptime(start_datetime_str, "%Y-%m-%d")
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            
            if "T" in end_datetime_str:
                end_dt = datetime.fromisoformat(end_datetime_str.replace("Z", "+00:00"))
            else:
                end_dt = datetime.strptime(end_datetime_str, "%Y-%m-%d")
                end_dt = end_dt.replace(tzinfo=timezone.utc)
        except:
            start_dt = None
            end_dt = None
        
        return {
            "id": event.get("id"),
            "summary": event.get("summary", "Senza titolo"),
            "description": event.get("description", ""),
            "location": event.get("location", ""),
            "start": start_dt.isoformat() if start_dt else start_datetime_str,
            "end": end_dt.isoformat() if end_dt else end_datetime_str,
            "start_datetime": start_dt,
            "end_datetime": end_dt,
            "attendees": [att.get("email") for att in event.get("attendees", [])],
            "organizer": event.get("organizer", {}).get("email"),
            "html_link": event.get("htmlLink"),
            "status": event.get("status", "confirmed"),
        }
    
    # Apple Calendar (CalDAV)
    async def setup_apple(
        self,
        url: str,
        username: str,
        password: str,
    ):
        """Setup Apple Calendar (CalDAV) integration"""
        if caldav is None:
            raise ValueError("caldav library not installed. Install it with: pip install caldav")
        self.apple_client = caldav.DAVClient(url, username=username, password=password)
    
    async def get_apple_events(
        self,
        calendar_name: str = "personal",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Get events from Apple Calendar"""
        if not self.apple_client:
            raise ValueError("Apple Calendar not configured")
        
        principal = self.apple_client.principal()
        calendars = principal.calendars()
        
        calendar = next((c for c in calendars if calendar_name in c.name.lower()), None)
        if not calendar:
            return []
        
        events = calendar.date_search(start_time or datetime.now(), end_time)
        
        return [
            {
                "summary": event.icalendar_component.get("summary", ""),
                "start": event.icalendar_component.get("dtstart").dt,
                "end": event.icalendar_component.get("dtend").dt,
            }
            for event in events
        ]
    
    # Microsoft Outlook
    async def setup_microsoft(
        self,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        access_token: Optional[str] = None,
    ):
        """Setup Microsoft Outlook integration"""
        if ConfidentialClientApplication is None:
            raise ValueError("msal library not installed. Install it with: pip install msal")
        self.microsoft_app = ConfidentialClientApplication(
            client_id,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
            client_credential=client_secret,
        )
        
        if access_token:
            self.microsoft_token = access_token
        else:
            # Would need authentication flow
            raise NotImplementedError("OAuth flow not implemented")
    
    async def get_microsoft_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        max_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get events from Microsoft Outlook"""
        if not hasattr(self, "microsoft_token"):
            raise ValueError("Microsoft Outlook not configured")
        
        headers = {"Authorization": f"Bearer {self.microsoft_token}"}
        params = {
            "$top": max_results,
            "$orderby": "start/dateTime",
        }
        
        if start_time:
            params["$filter"] = f"start/dateTime ge '{start_time.isoformat()}'"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://graph.microsoft.com/v1.0/me/events",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            return response.json().get("value", [])

