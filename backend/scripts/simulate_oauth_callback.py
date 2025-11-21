#!/usr/bin/env python3
"""Simulate OAuth callback to test credential saving"""
import asyncio
import sys
from pathlib import Path
import base64
import json
from uuid import UUID

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.database import AsyncSessionLocal
from app.models.database import Integration, User
from sqlalchemy import select
from app.core.config import settings
from app.api.integrations.mcp import _encrypt_credentials, _decrypt_credentials

async def simulate_callback():
    """Simulate OAuth callback with fake credentials"""
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
        
        print(f"✅ Found integration: {integration.id}")
        
        # Create fake OAuth credentials (simulating what Google would return)
        credentials = {
            "token": "fake_access_token_for_testing",
            "refresh_token": "fake_refresh_token_for_testing",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "scopes": [
                "https://www.googleapis.com/auth/calendar",
                "https://www.googleapis.com/auth/gmail.readonly",
            ],
        }
        
        print(f"\n🔐 Encrypting credentials...")
        try:
            encrypted_credentials = _encrypt_credentials(credentials, settings.credentials_encryption_key)
            print(f"✅ Credentials encrypted (length: {len(encrypted_credentials)})")
        except Exception as e:
            print(f"❌ Error encrypting: {e}")
            import traceback
            traceback.print_exc()
            return
        
        # Save credentials
        session_metadata = integration.session_metadata or {}
        if "oauth_credentials" not in session_metadata:
            session_metadata["oauth_credentials"] = {}
        
        user_id_str = str(user_id)
        session_metadata["oauth_credentials"][user_id_str] = encrypted_credentials
        
        print(f"\n📝 Storing credentials...")
        print(f"   Key: {user_id_str}")
        print(f"   Total OAuth users: {list(session_metadata['oauth_credentials'].keys())}")
        
        integration.session_metadata = session_metadata
        if user_id and (not integration.user_id or integration.user_id != user_id):
            integration.user_id = user_id
        
        try:
            await db.commit()
            print(f"✅ Database commit successful")
        except Exception as e:
            print(f"❌ Error committing: {e}")
            import traceback
            traceback.print_exc()
            await db.rollback()
            return
        
        await db.refresh(integration)
        
        # Verify credentials were saved
        refreshed_metadata = integration.session_metadata or {}
        refreshed_oauth = refreshed_metadata.get("oauth_credentials", {})
        
        print(f"\n🔍 Verifying saved credentials...")
        print(f"   Expected key: {user_id_str}")
        print(f"   Available keys: {list(refreshed_oauth.keys())}")
        
        if user_id_str in refreshed_oauth:
            print(f"✅ Credentials found!")
            try:
                decrypted = _decrypt_credentials(refreshed_oauth[user_id_str], settings.credentials_encryption_key)
                print(f"✅ Credentials decrypted successfully")
                print(f"   Token: {decrypted.get('token', '')[:30]}...")
                print(f"   Has refresh_token: {bool(decrypted.get('refresh_token'))}")
            except Exception as e:
                print(f"❌ Error decrypting: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"❌ Credentials NOT found after commit!")

if __name__ == "__main__":
    asyncio.run(simulate_callback())

