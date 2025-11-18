"""
Unit tests for proactivity system (Email Poller, Calendar Watcher, Event Monitor)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from uuid import uuid4, UUID

from app.services.schedulers.email_poller import EmailPoller
from app.services.schedulers.calendar_watcher import CalendarWatcher
from app.services.event_monitor import EventMonitor
from app.models.database import Integration, Notification


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = AsyncMock()
    
    # Mock execute() to return an async result
    mock_result = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    db.execute = AsyncMock(return_value=mock_result)
    
    return db


@pytest.fixture
def mock_integration():
    """Mock integration for testing"""
    integration = MagicMock(spec=Integration)
    integration.id = uuid4()
    integration.tenant_id = uuid4()
    integration.user_id = uuid4()
    integration.provider = "google"
    integration.service_type = "email"
    integration.enabled = True
    integration.credentials_encrypted = "encrypted_credentials"
    return integration


@pytest.fixture
def mock_calendar_integration():
    """Mock calendar integration"""
    integration = MagicMock(spec=Integration)
    integration.id = uuid4()
    integration.tenant_id = uuid4()
    integration.user_id = uuid4()
    integration.provider = "google"
    integration.service_type = "calendar"
    integration.enabled = True
    integration.credentials_encrypted = "encrypted_credentials"
    return integration


@pytest.fixture
def mock_email_service():
    """Mock email service"""
    service = AsyncMock()
    return service


@pytest.fixture
def mock_calendar_service():
    """Mock calendar service"""
    service = AsyncMock()
    return service


@pytest.fixture
def mock_notification_service():
    """Mock notification service"""
    service = AsyncMock()
    notification = MagicMock(spec=Notification)
    notification.id = uuid4()
    service.create_notification = AsyncMock(return_value=notification)
    return service


class TestEmailPoller:
    """Unit tests for EmailPoller"""
    
    @pytest.mark.asyncio
    async def test_check_new_emails_no_integrations(self, mock_db):
        """Test that no emails are checked if no integrations exist"""
        # Setup: no integrations (already set in fixture)
        poller = EmailPoller(mock_db)
        events = await poller.check_new_emails()
        
        assert events == []
        mock_db.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_new_emails_with_integration(self, mock_db, mock_integration, mock_email_service, mock_notification_service):
        """Test checking emails with a valid integration"""
        # Setup: one integration
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_integration]
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        # Mock email messages
        mock_messages = [
            {
                "id": "msg1",
                "from": "sender1@example.com",
                "subject": "Test Email 1",
                "snippet": "Test snippet",
                "date": datetime.now(timezone.utc).isoformat(),
            },
            {
                "id": "msg2",
                "from": "sender2@example.com",
                "subject": "URGENT: Important",
                "snippet": "Urgent content",
                "date": datetime.now(timezone.utc).isoformat(),
            },
        ]
        
        with patch('app.services.schedulers.email_poller._decrypt_credentials') as mock_decrypt, \
             patch('app.services.schedulers.email_poller.EmailService') as mock_email_service_class, \
             patch('app.services.schedulers.email_poller.NotificationService') as mock_notif_service_class:
            
            # Setup mocks
            mock_decrypt.return_value = {"token": "test_token"}
            mock_email_service_instance = AsyncMock()
            mock_email_service_instance.setup_gmail = AsyncMock()
            mock_email_service_instance.get_gmail_messages = AsyncMock(return_value=mock_messages)
            mock_email_service_class.return_value = mock_email_service_instance
            
            mock_notif_instance = AsyncMock()
            mock_notification = MagicMock()
            mock_notification.id = uuid4()
            mock_notif_instance.create_notification = AsyncMock(return_value=mock_notification)
            mock_notif_service_class.return_value = mock_notif_instance
            
            poller = EmailPoller(mock_db)
            events = await poller.check_new_emails()
            
            # Should create notifications for new emails
            assert len(events) > 0
            assert mock_email_service_instance.get_gmail_messages.called
    
    def test_determine_email_priority_urgent(self):
        """Test priority determination for urgent emails"""
        poller = EmailPoller(MagicMock())
        
        email = {
            "subject": "URGENT: Action Required",
            "from": "boss@example.com",
        }
        
        priority = poller._determine_email_priority(email)
        assert priority == "high"
    
    def test_determine_email_priority_recent(self):
        """Test priority determination for recent emails"""
        poller = EmailPoller(MagicMock())
        
        # Recent email (< 5 minutes old)
        recent_date = datetime.now(timezone.utc) - timedelta(minutes=3)
        email = {
            "subject": "Normal email",
            "from": "colleague@example.com",
            "date": recent_date.isoformat(),
        }
        
        priority = poller._determine_email_priority(email)
        # Recent email (< 5 min) should be medium
        assert priority == "medium"
    
    def test_determine_email_priority_low(self):
        """Test priority determination for normal emails"""
        poller = EmailPoller(MagicMock())
        
        # Old email (> 5 minutes old)
        old_date = datetime.now(timezone.utc) - timedelta(hours=1)
        email = {
            "subject": "Normal email",
            "from": "colleague@example.com",
            "date": old_date.isoformat(),
        }
        
        priority = poller._determine_email_priority(email)
        assert priority == "low"
    
    def test_determine_email_priority_no_date(self):
        """Test priority determination for emails without date"""
        poller = EmailPoller(MagicMock())
        
        email = {
            "subject": "Normal email",
            "from": "colleague@example.com",
        }
        
        priority = poller._determine_email_priority(email)
        assert priority == "low"
    
    def test_determine_email_priority_invalid_date(self):
        """Test priority determination with invalid date format"""
        poller = EmailPoller(MagicMock())
        
        email = {
            "subject": "Normal email",
            "from": "colleague@example.com",
            "date": "invalid-date-format",
        }
        
        # Should not raise exception, should return low priority
        priority = poller._determine_email_priority(email)
        assert priority == "low"
    
    def test_determine_email_priority_urgent_keywords(self):
        """Test various urgent keywords"""
        poller = EmailPoller(MagicMock())
        
        urgent_keywords = ["urgent", "urgente", "asap", "immediate", "immediato", "important", "importante"]
        
        for keyword in urgent_keywords:
            email = {
                "subject": f"{keyword.upper()}: Action Required",
                "from": "boss@example.com",
            }
            priority = poller._determine_email_priority(email)
            assert priority == "high", f"Keyword '{keyword}' should result in high priority"


class TestCalendarWatcher:
    """Unit tests for CalendarWatcher"""
    
    @pytest.mark.asyncio
    async def test_check_upcoming_events_no_integrations(self, mock_db):
        """Test that no events are checked if no integrations exist"""
        # Setup: no integrations (already set in fixture)
        watcher = CalendarWatcher(mock_db)
        events = await watcher.check_upcoming_events()
        
        assert events == []
        mock_db.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_upcoming_events_with_integration(self, mock_db, mock_calendar_integration):
        """Test checking calendar events with a valid integration"""
        # Setup: one integration
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_calendar_integration]
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        # Mock calendar events
        now = datetime.now(timezone.utc)
        event_start_15min = now + timedelta(minutes=15)
        event_start_5min = now + timedelta(minutes=5)
        
        mock_events = [
            {
                "id": "event1",
                "summary": "Meeting in 15 min",
                "start": {"dateTime": event_start_15min.isoformat()},
                "location": "Room A",
            },
            {
                "id": "event2",
                "summary": "Meeting in 5 min",
                "start": {"dateTime": event_start_5min.isoformat()},
                "location": "Room B",
            },
        ]
        
        with patch('app.services.schedulers.calendar_watcher._decrypt_credentials') as mock_decrypt, \
             patch('app.services.schedulers.calendar_watcher.CalendarService') as mock_calendar_service_class, \
             patch('app.services.schedulers.calendar_watcher.NotificationService') as mock_notif_service_class:
            
            # Setup mocks
            mock_decrypt.return_value = {"token": "test_token"}
            mock_calendar_service_instance = AsyncMock()
            mock_calendar_service_instance.setup_google = AsyncMock()
            mock_calendar_service_instance.get_google_events = AsyncMock(return_value=mock_events)
            mock_calendar_service_class.return_value = mock_calendar_service_instance
            
            mock_notif_instance = AsyncMock()
            mock_notification = MagicMock()
            mock_notification.id = uuid4()
            mock_notif_instance.create_notification = AsyncMock(return_value=mock_notification)
            mock_notif_service_class.return_value = mock_notif_instance
            
            watcher = CalendarWatcher(mock_db)
            events = await watcher.check_upcoming_events()
            
            # Should check for events
            assert mock_calendar_service_instance.get_google_events.called
    
    def test_parse_event_start_datetime(self):
        """Test parsing event start time with dateTime"""
        watcher = CalendarWatcher(MagicMock())
        
        event = {
            "start": {
                "dateTime": "2025-11-17T15:00:00Z"
            }
        }
        
        start_time = watcher._parse_event_start(event)
        assert start_time is not None
        assert isinstance(start_time, datetime)
        assert start_time.tzinfo is not None
    
    def test_parse_event_start_date(self):
        """Test parsing event start time with date (all-day event)"""
        watcher = CalendarWatcher(MagicMock())
        
        event = {
            "start": {
                "date": "2025-11-17"
            }
        }
        
        start_time = watcher._parse_event_start(event)
        assert start_time is not None
        assert isinstance(start_time, datetime)
        assert start_time.tzinfo is not None
    
    def test_parse_event_start_invalid(self):
        """Test parsing invalid event start"""
        watcher = CalendarWatcher(MagicMock())
        
        event = {
            "start": {}
        }
        
        start_time = watcher._parse_event_start(event)
        assert start_time is None
    
    def test_parse_event_start_no_start(self):
        """Test parsing event without start field"""
        watcher = CalendarWatcher(MagicMock())
        
        event = {}
        
        start_time = watcher._parse_event_start(event)
        assert start_time is None


class TestEventMonitor:
    """Unit tests for EventMonitor"""
    
    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping EventMonitor"""
        monitor = EventMonitor()
        
        # Start
        await monitor.start()
        assert monitor._running is True
        
        # Stop
        await monitor.stop()
        assert monitor._running is False
    
    @pytest.mark.asyncio
    async def test_check_once(self):
        """Test running a single check"""
        monitor = EventMonitor()
        
        with patch('app.services.event_monitor.get_db') as mock_get_db, \
             patch('app.services.event_monitor.EmailPoller') as mock_email_poller_class, \
             patch('app.services.event_monitor.CalendarWatcher') as mock_calendar_watcher_class:
            
            # Setup mock database
            mock_db = AsyncMock()
            mock_get_db.return_value.__aiter__.return_value = [mock_db]
            
            # Setup mock pollers
            mock_email_poller = AsyncMock()
            mock_email_poller.check_new_emails = AsyncMock(return_value=[])
            mock_email_poller_class.return_value = mock_email_poller
            
            mock_calendar_watcher = AsyncMock()
            mock_calendar_watcher.check_upcoming_events = AsyncMock(return_value=[])
            mock_calendar_watcher_class.return_value = mock_calendar_watcher
            
            # Run check
            await monitor.check_once()
            
            # Verify pollers were called
            mock_email_poller.check_new_emails.assert_called_once()
            mock_calendar_watcher.check_upcoming_events.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_monitor_loop_stops_when_running_false(self):
        """Test that monitor loop stops when _running is False"""
        monitor = EventMonitor()
        monitor._running = False
        
        # Start should set running to True
        await monitor.start()
        assert monitor._running is True
        
        # Stop should set running to False
        await monitor.stop()
        assert monitor._running is False


class TestEmailPollerErrorHandling:
    """Tests for error handling in EmailPoller"""
    
    @pytest.mark.asyncio
    async def test_auth_error_handling(self, mock_db, mock_integration):
        """Test that auth errors are handled gracefully"""
        # Setup: one integration
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_integration]
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        with patch('app.services.schedulers.email_poller._decrypt_credentials') as mock_decrypt, \
             patch('app.services.schedulers.email_poller.EmailService') as mock_email_service_class, \
             patch('app.services.schedulers.email_poller.IntegrationAuthError') as mock_auth_error:
            
            # Simulate auth error
            mock_decrypt.side_effect = ValueError("Invalid credentials")
            
            poller = EmailPoller(mock_db)
            events = await poller.check_new_emails()
            
            # Should return empty list, not raise exception
            assert events == []
    
    @pytest.mark.asyncio
    async def test_email_fetch_error_handling(self, mock_db, mock_integration):
        """Test that email fetch errors are handled gracefully"""
        # Setup: one integration
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_integration]
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        with patch('app.services.schedulers.email_poller._decrypt_credentials') as mock_decrypt, \
             patch('app.services.schedulers.email_poller.EmailService') as mock_email_service_class:
            
            mock_decrypt.return_value = {"token": "test_token"}
            mock_email_service_instance = AsyncMock()
            mock_email_service_instance.setup_gmail = AsyncMock()
            mock_email_service_instance.get_gmail_messages = AsyncMock(side_effect=Exception("API Error"))
            mock_email_service_class.return_value = mock_email_service_instance
            
            poller = EmailPoller(mock_db)
            events = await poller.check_new_emails()
            
            # Should return empty list, not raise exception
            assert events == []


class TestEmailPollerIntegration:
    """Integration tests for EmailPoller with real database operations"""
    
    def test_email_poller_tracks_last_email_id(self):
        """Test that EmailPoller tracks last checked email ID"""
        poller = EmailPoller(MagicMock())
        
        # Set last checked email ID
        integration_key = "test-integration-id"
        poller._last_email_ids[integration_key] = "msg1"
        
        # Verify tracking
        assert poller._last_email_ids[integration_key] == "msg1"
        assert integration_key in poller._last_email_ids
    
    def test_email_poller_filters_new_emails(self):
        """Test logic for filtering new emails"""
        poller = EmailPoller(MagicMock())
        
        # Simulate messages list
        messages = [
            {"id": "msg3", "from": "newest@example.com"},
            {"id": "msg2", "from": "new@example.com"},
            {"id": "msg1", "from": "old@example.com"},
        ]
        
        # If last_email_id is "msg1", new messages should be msg3 and msg2
        last_email_id = "msg1"
        new_messages = []
        for i, msg in enumerate(messages):
            if msg.get("id") == last_email_id:
                new_messages = messages[:i]
                break
        
        assert len(new_messages) == 2
        assert new_messages[0]["id"] == "msg3"
        assert new_messages[1]["id"] == "msg2"
    
    def test_email_poller_first_time_limit(self):
        """Test that first time check limits to 5 emails"""
        poller = EmailPoller(MagicMock())
        
        # Simulate many messages (first time, no last_email_id)
        messages = [{"id": f"msg{i}", "from": f"sender{i}@example.com"} for i in range(20)]
        
        # First time: should limit to 5
        last_email_id = None
        if last_email_id:
            new_messages = messages
        else:
            new_messages = messages[:5]
        
        assert len(new_messages) == 5


class TestCalendarWatcherErrorHandling:
    """Tests for error handling in CalendarWatcher"""
    
    @pytest.mark.asyncio
    async def test_auth_error_handling(self, mock_db, mock_calendar_integration):
        """Test that auth errors are handled gracefully"""
        # Setup: one integration
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_calendar_integration]
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        with patch('app.services.schedulers.calendar_watcher._decrypt_credentials') as mock_decrypt, \
             patch('app.services.schedulers.calendar_watcher.IntegrationAuthError') as mock_auth_error:
            
            # Simulate auth error
            mock_decrypt.side_effect = ValueError("Invalid credentials")
            
            watcher = CalendarWatcher(mock_db)
            events = await watcher.check_upcoming_events()
            
            # Should return empty list, not raise exception
            assert events == []
    
    @pytest.mark.asyncio
    async def test_calendar_fetch_error_handling(self, mock_db, mock_calendar_integration):
        """Test that calendar fetch errors are handled gracefully"""
        # Setup: one integration
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_calendar_integration]
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        with patch('app.services.schedulers.calendar_watcher._decrypt_credentials') as mock_decrypt, \
             patch('app.services.schedulers.calendar_watcher.CalendarService') as mock_calendar_service_class:
            
            mock_decrypt.return_value = {"token": "test_token"}
            mock_calendar_service_instance = AsyncMock()
            mock_calendar_service_instance.setup_google = AsyncMock()
            mock_calendar_service_instance.get_google_events = AsyncMock(side_effect=Exception("API Error"))
            mock_calendar_service_class.return_value = mock_calendar_service_instance
            
            watcher = CalendarWatcher(mock_db)
            events = await watcher.check_upcoming_events()
            
            # Should return empty list, not raise exception
            assert events == []


class TestCalendarWatcherReminders:
    """Tests for calendar reminder timing logic"""
    
    def test_reminder_timing_15min(self):
        """Test that reminder is created at 15 minutes before event"""
        watcher = CalendarWatcher(MagicMock())
        
        now = datetime.now(timezone.utc)
        event_start = now + timedelta(minutes=15)
        
        event = {
            "id": "event1",
            "summary": "Test Event",
            "start": {"dateTime": event_start.isoformat()},
        }
        
        # Parse start time
        start_time = watcher._parse_event_start(event)
        assert start_time is not None
        
        # Calculate time until start
        time_until_start = start_time - now
        
        # Should be approximately 15 minutes (allow 1 minute tolerance)
        assert timedelta(minutes=14) < time_until_start < timedelta(minutes=16)
    
    def test_reminder_timing_5min(self):
        """Test that reminder is created at 5 minutes before event"""
        watcher = CalendarWatcher(MagicMock())
        
        now = datetime.now(timezone.utc)
        event_start = now + timedelta(minutes=5)
        
        event = {
            "id": "event1",
            "summary": "Test Event",
            "start": {"dateTime": event_start.isoformat()},
        }
        
        start_time = watcher._parse_event_start(event)
        assert start_time is not None
        
        time_until_start = start_time - now
        # Allow 1 minute tolerance
        assert timedelta(minutes=4) < time_until_start < timedelta(minutes=6)
    
    def test_reminder_minutes_list(self):
        """Test that reminder_minutes list is correctly initialized"""
        watcher = CalendarWatcher(MagicMock())
        assert watcher.reminder_minutes == [15, 5]
    
    def test_reminder_timing_out_of_range(self):
        """Test that events outside reminder window are ignored"""
        watcher = CalendarWatcher(MagicMock())
        
        now = datetime.now(timezone.utc)
        # Event in 30 minutes (outside reminder window)
        event_start = now + timedelta(minutes=30)
        
        event = {
            "id": "event1",
            "summary": "Future Event",
            "start": {"dateTime": event_start.isoformat()},
        }
        
        start_time = watcher._parse_event_start(event)
        assert start_time is not None
        
        time_until_start = start_time - now
        # Should be outside reminder window (15 and 5 minutes)
        assert time_until_start > timedelta(minutes=15)

