#!/usr/bin/env python3
"""Test OAuth credentials retrieval"""
import asyncio
import sys
from pathlib import Path
from uuid import UUID

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.database import AsyncSessionLocal
from app.models.database import Integration, User
from sqlalchemy import select
from app.core.config import settings
from app.api.integrations.mcp import _get_mcp_client_for_integration, _decrypt_credentials

async def test_retrieval():
    """Test OAuth credentials retrieval"""
    async with AsyncSessionLocal() as db:
        integration_id = UUID("67465695-76d2-4036-94a4-9c8db7047d6a")
        user_id = UUID("5e54d258-7127-42e8-ae9b-7cb65f9fb01e")
        
        # Get integration
        result = await db.execute(
            select(Integration)
            .where(Integration.id == integration_id)
        )
        integration = result.scalar_one_or_none()
        
        if not integration:
            print("❌ Integration not found")
            return
        
        # Get user
        user_result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            print("❌ User not found")
            return
        
        print(f"✅ Found integration: {integration.id}")
        print(f"✅ Found user: {user.email}")
        
        # Check credentials in metadata
        session_metadata = integration.session_metadata or {}
        oauth_credentials = session_metadata.get("oauth_credentials", {})
        user_id_str = str(user.id)
        
        print(f"\n🔍 Checking OAuth credentials...")
        print(f"   User ID string: {user_id_str}")
        print(f"   Available OAuth keys: {list(oauth_credentials.keys())}")
        
        if user_id_str in oauth_credentials:
            print(f"✅ Credentials found!")
            try:
                encrypted = oauth_credentials[user_id_str]
                decrypted = _decrypt_credentials(encrypted, settings.credentials_encryption_key)
                print(f"✅ Credentials decrypted successfully")
                print(f"   Token: {decrypted.get('token', '')[:30]}...")
                print(f"   Has refresh_token: {bool(decrypted.get('refresh_token'))}")
            except Exception as e:
                print(f"❌ Error decrypting: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"❌ No credentials found for user {user_id_str}")
        
        # Test _get_mcp_client_for_integration
        print(f"\n🔍 Testing _get_mcp_client_for_integration...")
        try:
            client = _get_mcp_client_for_integration(integration, current_user=user)
            print(f"✅ Client created successfully")
            print(f"   Base URL: {client.base_url}")
            print(f"   Headers: {list(client.headers.keys())}")
            if "Authorization" in client.headers:
                print(f"   Has OAuth token: Yes (length: {len(client.headers['Authorization'])})")
            else:
                print(f"   Has OAuth token: No")
        except Exception as e:
            print(f"❌ Error creating client: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_retrieval())

