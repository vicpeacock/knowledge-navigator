"""
Unit tests for NotificationService - Delete functionality
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4, UUID
from datetime import datetime, timezone

from app.services.notification_service import NotificationService
from app.models.database import Notification as NotificationModel


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.delete = AsyncMock()
    return db


@pytest.fixture
def mock_notification():
    """Mock notification for testing"""
    notification = MagicMock(spec=NotificationModel)
    notification.id = uuid4()
    notification.tenant_id = uuid4()
    notification.read = False
    return notification


@pytest.mark.asyncio
class TestNotificationServiceDelete:
    """Test delete_notification method"""
    
    async def test_delete_notification_success(self, mock_db, mock_notification):
        """Test successful deletion of notification"""
        tenant_id = mock_notification.tenant_id
        
        # Mock execute: first call returns notification (for existence check), second call returns delete result
        mock_result_check = MagicMock()
        mock_result_check.scalar_one_or_none.return_value = mock_notification
        
        mock_result_delete = MagicMock()
        mock_result_delete.rowcount = 1  # One row deleted
        
        async def mock_execute_side_effect(query):
            # First call: check existence (SELECT query)
            # Check if it's a SELECT query by looking for 'select' in the string representation
            query_str = str(query).lower()
            if 'select' in query_str and 'notification' in query_str:
                return mock_result_check
            # Second call: delete statement (DELETE query)
            return mock_result_delete
        
        mock_db.execute = AsyncMock(side_effect=mock_execute_side_effect)
        
        service = NotificationService(mock_db)
        result = await service.delete_notification(mock_notification.id, tenant_id=tenant_id)
        
        assert result is True
        assert mock_db.execute.call_count == 2  # One for check, one for delete
        mock_db.commit.assert_called_once()
    
    async def test_delete_notification_not_found(self, mock_db):
        """Test deletion when notification doesn't exist"""
        notification_id = uuid4()
        tenant_id = uuid4()
        
        # Mock execute to return None (not found)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        service = NotificationService(mock_db)
        result = await service.delete_notification(notification_id, tenant_id=tenant_id)
        
        assert result is False
        mock_db.execute.assert_called_once()
        mock_db.delete.assert_not_called()
        mock_db.commit.assert_not_called()
    
    async def test_delete_notification_wrong_tenant(self, mock_db, mock_notification):
        """Test deletion fails when notification belongs to different tenant"""
        notification_id = mock_notification.id
        wrong_tenant_id = uuid4()  # Different tenant
        
        # Mock execute to return None (filtered out by tenant)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        service = NotificationService(mock_db)
        result = await service.delete_notification(notification_id, tenant_id=wrong_tenant_id)
        
        assert result is False
        mock_db.execute.assert_called_once()
        mock_db.delete.assert_not_called()
        mock_db.commit.assert_not_called()
    
    async def test_delete_notification_without_tenant_filter(self, mock_db, mock_notification):
        """Test deletion without tenant filter (admin scenario)"""
        # Mock execute: first call returns notification (for existence check), second call returns delete result
        mock_result_check = MagicMock()
        mock_result_check.scalar_one_or_none.return_value = mock_notification
        
        mock_result_delete = MagicMock()
        mock_result_delete.rowcount = 1  # One row deleted
        
        async def mock_execute_side_effect(query):
            # First call: check existence (SELECT query)
            # Check if it's a SELECT query by looking for 'select' in the string representation
            query_str = str(query).lower()
            if 'select' in query_str and 'notification' in query_str:
                return mock_result_check
            # Second call: delete statement (DELETE query)
            return mock_result_delete
        
        mock_db.execute = AsyncMock(side_effect=mock_execute_side_effect)
        
        service = NotificationService(mock_db)
        result = await service.delete_notification(mock_notification.id, tenant_id=None)
        
        assert result is True
        assert mock_db.execute.call_count == 2  # One for check, one for delete
        mock_db.commit.assert_called_once()

