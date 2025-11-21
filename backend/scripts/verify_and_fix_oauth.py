#!/usr/bin/env python3
"""Verify and fix OAuth credentials for Google Workspace MCP"""
import asyncio
import sys
from pathlib import Path
import json

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.database import AsyncSessionLocal
from app.models.database import Integration, User
from sqlalchemy import select
from app.core.config import settings
from app.api.integrations.mcp import _encrypt_credentials, _decrypt_credentials
from uuid import UUID

async def verify_and_fix():
    async with AsyncSessionLocal() as db:
        # Find Google Workspace MCP integration
        integration_id = UUID("67465695-76d2-4036-94a4-9c8db7047d6a")
        result = await db.execute(
            select(Integration)
            .where(Integration.id == integration_id)
        )
        integration = result.scalar_one_or_none()
        
        if not integration:
            print("❌ Integration not found")
            return
        
        print(f"✅ Found integration: {integration.id}")
        print(f"   User ID: {integration.user_id}")
        
        # Get user
        if not integration.user_id:
            print("❌ No user_id set on integration")
            return
        
        user_result = await db.execute(
            select(User).where(User.id == integration.user_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            print(f"❌ User {integration.user_id} not found")
            return
        
        print(f"✅ Found user: {user.email}")
        
        session_metadata = integration.session_metadata or {}
        oauth_credentials = session_metadata.get("oauth_credentials", {})
        user_id_str = str(user.id)
        
        print(f"\n📋 Current session_metadata structure:")
        print(f"   Keys: {list(session_metadata.keys())}")
        print(f"   OAuth credentials keys: {list(oauth_credentials.keys())}")
        
        # Check if credentials exist
        if user_id_str in oauth_credentials:
            print(f"\n✅ Credentials found for user {user_id_str}")
            try:
                encrypted = oauth_credentials[user_id_str]
                decrypted = _decrypt_credentials(encrypted, settings.credentials_encryption_key)
                print(f"   Token: {decrypted.get('token', '')[:30]}...")
                print(f"   Has refresh_token: {bool(decrypted.get('refresh_token'))}")
                print(f"   Scopes: {decrypted.get('scopes', [])}")
            except Exception as e:
                print(f"❌ Error decrypting: {e}")
        else:
            print(f"\n❌ No credentials found for user {user_id_str}")
            print(f"\n🔧 Since OAuth was successful, the callback should have saved credentials.")
            print(f"   This suggests the callback may not have been called, or failed silently.")
            print(f"\n💡 Solution: Re-run OAuth flow with the new logging to see what happens.")
            
            # Check if there are any credentials under different keys
            if oauth_credentials:
                print(f"\n⚠️  Found credentials under different keys:")
                for key in oauth_credentials.keys():
                    print(f"   - Key: {key}")
                    try:
                        encrypted = oauth_credentials[key]
                        decrypted = _decrypt_credentials(encrypted, settings.credentials_encryption_key)
                        print(f"     Token: {decrypted.get('token', '')[:30]}...")
                        print(f"     Moving to correct key...")
                        oauth_credentials[user_id_str] = oauth_credentials.pop(key)
                        session_metadata["oauth_credentials"] = oauth_credentials
                        integration.session_metadata = session_metadata
                        await db.commit()
                        print(f"✅ Moved credentials to correct key")
                    except Exception as e:
                        print(f"     Error decrypting: {e}")

if __name__ == "__main__":
    asyncio.run(verify_and_fix())

