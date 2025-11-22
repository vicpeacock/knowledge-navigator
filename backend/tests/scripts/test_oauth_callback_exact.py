#!/usr/bin/env python3
"""Test OAuth callback exact flow"""
import asyncio
import sys
from pathlib import Path
from uuid import UUID

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.database import AsyncSessionLocal
from app.models.database import Integration, User
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from app.core.config import settings
from app.api.integrations.mcp import _encrypt_credentials

async def test_exact_callback_flow():
    """Test exact OAuth callback flow"""
    async with AsyncSessionLocal() as db:
        integration_id = UUID("67465695-76d2-4036-94a4-9c8db7047d6a")
        user_id = UUID("5e54d258-7127-42e8-ae9b-7cb65f9fb01e")
        
        # Get integration (same as callback)
        result = await db.execute(
            select(Integration)
            .where(Integration.id == integration_id)
        )
        integration = result.scalar_one_or_none()
        
        if not integration:
            print("❌ Integration not found")
            return
        
        print(f"✅ Found integration: {integration.id}")
        
        # Create credentials (same as callback)
        credentials = {
            "token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "scopes": ["https://www.googleapis.com/auth/calendar"],
        }
        
        # Save credentials (EXACT same logic as callback)
        session_metadata = integration.session_metadata or {}
        print(f"\n📋 Current session_metadata keys: {list(session_metadata.keys())}")
        
        # Store OAuth credentials per user in session_metadata
        if "oauth_credentials" not in session_metadata:
            session_metadata["oauth_credentials"] = {}
            print(f"   Created oauth_credentials dict")
        
        user_id_str = str(user_id) if user_id else "default"
        print(f"\n🔐 Encrypting credentials for user_id_str: {user_id_str}")
        
        try:
            encrypted_credentials = _encrypt_credentials(credentials, settings.credentials_encryption_key)
            print(f"✅ Credentials encrypted (length: {len(encrypted_credentials)})")
        except Exception as encrypt_error:
            print(f"❌ Error encrypting: {encrypt_error}")
            import traceback
            traceback.print_exc()
            return
        
        session_metadata["oauth_credentials"][user_id_str] = encrypted_credentials
        print(f"📝 Stored credentials in session_metadata['oauth_credentials']['{user_id_str}']")
        print(f"   Total OAuth users: {list(session_metadata['oauth_credentials'].keys())}")
        
        # Update integration (EXACT same as callback)
        integration.session_metadata = session_metadata
        flag_modified(integration, "session_metadata")  # IMPORTANT: Flag JSONB as modified
        if user_id and (not integration.user_id or integration.user_id != user_id):
            integration.user_id = user_id
            print(f"✅ Updated integration.user_id to {user_id}")
        
        print(f"\n💾 Committing to database...")
        try:
            await db.commit()
            print(f"✅ Database commit successful")
        except Exception as commit_error:
            print(f"❌ Error committing: {commit_error}")
            import traceback
            traceback.print_exc()
            await db.rollback()
            return
        
        print(f"\n🔄 Refreshing integration...")
        await db.refresh(integration)
        
        # Verify credentials were saved (EXACT same as callback)
        refreshed_metadata = integration.session_metadata or {}
        refreshed_oauth = refreshed_metadata.get("oauth_credentials", {})
        
        print(f"\n🔍 Verifying saved credentials...")
        print(f"   Expected key: {user_id_str}")
        print(f"   Available keys: {list(refreshed_oauth.keys())}")
        print(f"   All metadata keys: {list(refreshed_metadata.keys())}")
        
        if user_id_str in refreshed_oauth:
            print(f"✅ Verified: OAuth credentials saved successfully!")
            print(f"   Stored credentials length: {len(refreshed_oauth[user_id_str])}")
        else:
            print(f"❌ ERROR: OAuth credentials NOT found after commit and refresh!")
            print(f"   This is the same error as in the real callback")

if __name__ == "__main__":
    asyncio.run(test_exact_callback_flow())

