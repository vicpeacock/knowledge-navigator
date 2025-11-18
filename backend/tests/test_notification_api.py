"""
Integration tests for Notification API endpoints - Delete functionality
"""
import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app
from app.models.database import Notification as NotificationModel, Tenant


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_tenant_id():
    """Mock tenant ID"""
    return uuid4()


@pytest.fixture
def mock_notification_id():
    """Mock notification ID"""
    return uuid4()


@pytest.mark.asyncio
class TestNotificationDeleteAPI:
    """Test DELETE /api/notifications/{notification_id} endpoint"""
    
    @patch('app.api.notifications.get_db')
    @patch('app.api.notifications.get_tenant_id')
    @patch('app.services.notification_service.NotificationService.delete_notification')
    async def test_delete_notification_success(
        self,
        mock_delete,
        mock_get_tenant_id,
        mock_get_db,
        client,
        mock_tenant_id,
        mock_notification_id
    ):
        """Test successful deletion via API"""
        # Setup mocks
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db
        mock_get_tenant_id.return_value = mock_tenant_id
        mock_delete.return_value = True
        
        # Make request
        response = client.delete(f"/api/notifications/{mock_notification_id}")
        
        # Assertions
        assert response.status_code == 200
        assert response.json()["message"] == "Notification deleted"
        assert response.json()["notification_id"] == str(mock_notification_id)
        mock_delete.assert_called_once_with(mock_notification_id, tenant_id=mock_tenant_id)
    
    @patch('app.api.notifications.get_db')
    @patch('app.api.notifications.get_tenant_id')
    @patch('app.services.notification_service.NotificationService.delete_notification')
    async def test_delete_notification_not_found(
        self,
        mock_delete,
        mock_get_tenant_id,
        mock_get_db,
        client,
        mock_tenant_id,
        mock_notification_id
    ):
        """Test deletion when notification doesn't exist"""
        # Setup mocks
        mock_db = AsyncMock()
        mock_get_db.return_value = mock_db
        mock_get_tenant_id.return_value = mock_tenant_id
        mock_delete.return_value = False  # Not found
        
        # Make request
        response = client.delete(f"/api/notifications/{mock_notification_id}")
        
        # Assertions
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
        mock_delete.assert_called_once_with(mock_notification_id, tenant_id=mock_tenant_id)
    
    @patch('app.api.notifications.get_db')
    @patch('app.api.notifications.get_tenant_id')
    @patch('app.services.notification_service.NotificationService.delete_notification')
    async def test_delete_notification_invalid_uuid(
        self,
        mock_delete,
        mock_get_tenant_id,
        mock_get_db,
        client,
        mock_tenant_id
    ):
        """Test deletion with invalid UUID format"""
        # Make request with invalid UUID
        response = client.delete("/api/notifications/invalid-uuid")
        
        # Should return 422 (validation error)
        assert response.status_code == 422
        mock_delete.assert_not_called()

