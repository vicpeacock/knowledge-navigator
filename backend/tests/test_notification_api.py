"""
Integration tests for Notification API endpoints - Delete functionality
"""
import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app
from app.api.notifications import get_db, get_tenant_id
from app.models.database import Notification as NotificationModel, Tenant


@pytest.fixture
def client():
    """Create test client"""
    # Clear any existing overrides
    app.dependency_overrides.clear()
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
    
    async def test_delete_notification_success(
        self,
        client,
        mock_tenant_id,
        mock_notification_id
    ):
        """Test successful deletion via API"""
        # Setup mocks
        mock_db = AsyncMock()
        
        # Mock NotificationService
        from app.services.notification_service import NotificationService
        mock_service = AsyncMock(spec=NotificationService)
        mock_service.delete_notification = AsyncMock(return_value=True)
        
        # Override dependencies
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_tenant_id] = lambda: mock_tenant_id
        
        # Patch NotificationService instantiation
        with patch('app.api.notifications.NotificationService', return_value=mock_service):
            # Make request
            response = client.delete(f"/api/notifications/{mock_notification_id}")
            
            # Assertions
            assert response.status_code == 200
            assert response.json()["message"] == "Notification deleted"
            assert response.json()["notification_id"] == str(mock_notification_id)
            mock_service.delete_notification.assert_called_once_with(mock_notification_id, tenant_id=mock_tenant_id)
        
        # Clean up
        app.dependency_overrides.clear()
    
    async def test_delete_notification_not_found(
        self,
        client,
        mock_tenant_id,
        mock_notification_id
    ):
        """Test deletion when notification doesn't exist"""
        # Setup mocks
        mock_db = AsyncMock()
        
        # Mock NotificationService
        from app.services.notification_service import NotificationService
        mock_service = AsyncMock(spec=NotificationService)
        mock_service.delete_notification = AsyncMock(return_value=False)  # Not found
        
        # Override dependencies
        app.dependency_overrides[get_db] = lambda: mock_db
        app.dependency_overrides[get_tenant_id] = lambda: mock_tenant_id
        
        # Patch NotificationService instantiation
        with patch('app.api.notifications.NotificationService', return_value=mock_service):
            # Make request
            response = client.delete(f"/api/notifications/{mock_notification_id}")
            
            # Assertions
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
            mock_service.delete_notification.assert_called_once_with(mock_notification_id, tenant_id=mock_tenant_id)
        
        # Clean up
        app.dependency_overrides.clear()
    
    async def test_delete_notification_invalid_uuid(
        self,
        client,
        mock_tenant_id
    ):
        """Test deletion with invalid UUID format"""
        # Make request with invalid UUID
        response = client.delete("/api/notifications/invalid-uuid")
        
        # Should return 422 (validation error)
        assert response.status_code == 422

