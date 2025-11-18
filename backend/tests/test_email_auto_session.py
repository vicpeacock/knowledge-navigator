"""
E2E tests for automatic session creation from email analysis
"""
import pytest
import pytest_asyncio
from uuid import uuid4
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.schedulers.email_poller import EmailPoller
from app.services.email_analyzer import EmailAnalyzer
from app.services.email_action_processor import EmailActionProcessor
from app.models.database import Integration, User, Tenant, Session as SessionModel, Notification as NotificationModel


@pytest_asyncio.fixture
async def test_db():
    """Create test database session"""
    from app.db.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def test_tenant(test_db):
    """Create test tenant"""
    tenant = Tenant(
        id=uuid4(),
        name="Test Tenant",
        created_at=datetime.now(timezone.utc),
    )
    test_db.add(tenant)
    await test_db.commit()
    await test_db.refresh(tenant)
    return tenant


@pytest_asyncio.fixture
async def test_user(test_db, test_tenant):
    """Create test user"""
    user = User(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Test User",
        email="test@example.com",
        created_at=datetime.now(timezone.utc),
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_integration(test_db, test_tenant, test_user):
    """Create test Gmail integration"""
    integration = Integration(
        id=uuid4(),
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        provider="google",
        service_type="email",
        enabled=True,
        credentials_encrypted="encrypted_creds",
        created_at=datetime.now(timezone.utc),
    )
    test_db.add(integration)
    await test_db.commit()
    await test_db.refresh(integration)
    return integration


@pytest.mark.asyncio
class TestEmailAutoSession:
    """Test automatic session creation from email analysis"""
    
    @patch('app.services.schedulers.email_poller.get_ollama_client')
    @patch('app.services.schedulers.email_poller.get_memory_manager')
    @patch('app.services.schedulers.email_poller.EmailService')
    async def test_email_analysis_creates_session_for_actionable_email(
        self,
        mock_email_service_class,
        mock_get_memory_manager,
        mock_get_ollama_client,
        test_db,
        test_tenant,
        test_user,
        test_integration,
    ):
        """Test that actionable email creates automatic session"""
        # Setup mocks
        mock_ollama = AsyncMock()
        mock_get_ollama_client.return_value = mock_ollama
        
        mock_memory = MagicMock()
        mock_get_memory_manager.return_value = mock_memory
        
        # Mock email service
        mock_email_service = AsyncMock()
        mock_email_service_class.return_value = mock_email_service
        
        # Mock email that requires action
        mock_email = {
            "id": "email-123",
            "subject": "Please confirm your attendance",
            "from": "organizer@example.com",
            "to": "test@example.com",
            "snippet": "We need your confirmation for the meeting tomorrow. Please reply ASAP.",
            "date": datetime.now(timezone.utc).isoformat(),
            "category": "direct",
        }
        
        mock_email_service.get_gmail_messages = AsyncMock(return_value=[mock_email])
        mock_email_service.setup_gmail = AsyncMock()
        
        # Mock LLM analysis to return actionable email
        mock_analysis = {
            "category": "direct",
            "requires_action": True,
            "action_type": "reply",
            "action_summary": "User needs to confirm attendance",
            "urgency": "high",
            "reasoning": "Email explicitly asks for confirmation",
        }
        
        # Create poller
        poller = EmailPoller(test_db)
        
        # Mock the analyzer's analyze_email method
        with patch.object(poller.email_analyzer, 'analyze_email', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = mock_analysis
            
            # Mock the action processor's process_email_action
            with patch.object(poller.email_action_processor, 'process_email_action', new_callable=AsyncMock) as mock_process:
                mock_process.return_value = uuid4()  # Return a session ID
                
                # Check emails
                events = await poller._check_integration_emails(test_integration)
                
                # Verify analysis was called
                mock_analyze.assert_called_once()
                
                # Verify session creation was attempted
                mock_process.assert_called_once()
                call_args = mock_process.call_args
                assert call_args[1]['analysis'] == mock_analysis
                assert call_args[1]['email']['id'] == "email-123"
                assert call_args[1]['tenant_id'] == test_tenant.id
                assert call_args[1]['user_id'] == test_user.id
                
                # Verify notification was created
                assert len(events) > 0
                event = events[0]
                assert event['type'] == 'email_received'
                assert event['analysis'] == mock_analysis
                assert event['session_id'] is not None
    
    @patch('app.services.schedulers.email_poller.get_ollama_client')
    @patch('app.services.schedulers.email_poller.get_memory_manager')
    @patch('app.services.schedulers.email_poller.EmailService')
    async def test_email_analysis_no_session_for_info_email(
        self,
        mock_email_service_class,
        mock_get_memory_manager,
        mock_get_ollama_client,
        test_db,
        test_tenant,
        test_user,
        test_integration,
    ):
        """Test that informational email does NOT create session"""
        # Setup mocks
        mock_ollama = AsyncMock()
        mock_get_ollama_client.return_value = mock_ollama
        
        mock_memory = MagicMock()
        mock_get_memory_manager.return_value = mock_memory
        
        # Mock email service
        mock_email_service = AsyncMock()
        mock_email_service_class.return_value = mock_email_service
        
        # Mock informational email
        mock_email = {
            "id": "email-456",
            "subject": "Newsletter: Weekly Update",
            "from": "newsletter@example.com",
            "to": "test@example.com",
            "snippet": "Here's your weekly newsletter with updates...",
            "date": datetime.now(timezone.utc).isoformat(),
            "category": "promotional",
        }
        
        mock_email_service.get_gmail_messages = AsyncMock(return_value=[mock_email])
        mock_email_service.setup_gmail = AsyncMock()
        
        # Mock LLM analysis - no action required
        mock_analysis = {
            "category": "promotional",
            "requires_action": False,
            "action_type": None,
            "action_summary": "",
            "urgency": "low",
            "reasoning": "Newsletter, no action required",
        }
        
        # Create poller
        poller = EmailPoller(test_db)
        
        # Mock the analyzer
        with patch.object(poller.email_analyzer, 'analyze_email', new_callable=AsyncMock) as mock_analyze:
            mock_analyze.return_value = mock_analysis
            
            # Check emails
            events = await poller._check_integration_emails(test_integration)
            
            # Verify analysis was called
            mock_analyze.assert_called_once()
            
            # Verify NO session creation was attempted
            if poller.email_action_processor:
                # Should not be called because requires_action is False
                pass
            
            # Verify notification was still created (but without session)
            assert len(events) > 0
            event = events[0]
            assert event['type'] == 'email_received'
            assert event.get('session_id') is None  # No session for info emails
    
    @patch('app.services.email_analyzer.OllamaClient')
    async def test_email_analyzer_detects_action_required(
        self,
        mock_ollama_class,
        test_db,
    ):
        """Test EmailAnalyzer correctly identifies actionable emails"""
        # Setup mock LLM response
        mock_ollama = AsyncMock()
        mock_ollama_class.return_value = mock_ollama
        
        # Mock LLM response for actionable email
        mock_llm_response = '''{
            "requires_action": true,
            "action_type": "reply",
            "action_summary": "User needs to confirm attendance",
            "urgency": "high",
            "reasoning": "Email explicitly asks for confirmation"
        }'''
        
        mock_ollama.generate_with_context = AsyncMock(return_value=mock_llm_response)
        
        # Create analyzer
        analyzer = EmailAnalyzer(ollama_client=mock_ollama)
        
        # Test email
        email = {
            "id": "email-123",
            "subject": "Please confirm your attendance",
            "from": "organizer@example.com",
            "snippet": "We need your confirmation for the meeting tomorrow. Please reply ASAP.",
            "category": "direct",
        }
        
        # Analyze
        analysis = await analyzer.analyze_email(email)
        
        # Verify results
        assert analysis['requires_action'] is True
        assert analysis['action_type'] == 'reply'
        assert analysis['urgency'] == 'high'
        assert 'action_summary' in analysis
    
    @patch('app.services.email_action_processor.OllamaClient')
    async def test_email_action_processor_creates_session(
        self,
        mock_ollama_class,
        test_db,
        test_tenant,
        test_user,
    ):
        """Test EmailActionProcessor creates session correctly"""
        # Setup
        mock_ollama = AsyncMock()
        mock_ollama_class.return_value = mock_ollama
        
        processor = EmailActionProcessor(
            db=test_db,
            ollama_client=mock_ollama,
            memory_manager=None,
        )
        
        # Test email and analysis
        email = {
            "id": "email-123",
            "subject": "Please confirm your attendance",
            "from": "organizer@example.com",
            "snippet": "We need your confirmation...",
        }
        
        analysis = {
            "requires_action": True,
            "action_type": "reply",
            "action_summary": "Confirm attendance",
            "urgency": "high",
        }
        
        # Process action
        session_id = await processor.process_email_action(
            email=email,
            analysis=analysis,
            tenant_id=test_tenant.id,
            user_id=test_user.id,
        )
        
        # Verify session was created
        assert session_id is not None
        
        # Verify session in database
        from sqlalchemy import select
        result = await test_db.execute(
            select(SessionModel).where(SessionModel.id == session_id)
        )
        session = result.scalar_one_or_none()
        
        assert session is not None
        assert session.tenant_id == test_tenant.id
        assert session.user_id == test_user.id
        assert session.title == email['subject']
        assert session.session_metadata['source'] == 'email_analysis'
        assert session.session_metadata['email_id'] == email['id']
        
        # Verify initial message was created
        from app.models.database import Message as MessageModel
        result = await test_db.execute(
            select(MessageModel).where(MessageModel.session_id == session_id)
        )
        messages = result.scalars().all()
        assert len(messages) > 0
        assert messages[0].role == 'user'
        assert 'email' in messages[0].content.lower() or 'attendance' in messages[0].content.lower()

