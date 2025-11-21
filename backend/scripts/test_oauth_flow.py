#!/usr/bin/env python3
"""Test OAuth flow for Google Workspace MCP"""
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

async def test_state_encoding():
    """Test state encoding/decoding"""
    integration_id = UUID("67465695-76d2-4036-94a4-9c8db7047d6a")
    user_id = UUID("5e54d258-7127-42e8-ae9b-7cb65f9fb01e")
    
    # Encode state (same as authorize endpoint)
    state_payload = {
        "integration_id": str(integration_id),
        "user_id": str(user_id),
    }
    state_str = base64.urlsafe_b64encode(
        json.dumps(state_payload).encode("utf-8")
    ).decode("utf-8")
    
    print(f"✅ Encoded state: {state_str}")
    print(f"   Length: {len(state_str)}")
    
    # Decode state (same as callback)
    try:
        state_bytes = state_str.encode("utf-8")
        missing_padding = len(state_bytes) % 4
        if missing_padding:
            state_bytes += b'=' * (4 - missing_padding)
        
        decoded = base64.urlsafe_b64decode(state_bytes)
        payload_str = decoded.decode("utf-8")
        payload = json.loads(payload_str)
        
        print(f"✅ Decoded state:")
        print(f"   integration_id: {payload.get('integration_id')}")
        print(f"   user_id: {payload.get('user_id')}")
        
        decoded_integration_id = UUID(payload.get("integration_id"))
        decoded_user_id = UUID(payload.get("user_id"))
        
        print(f"✅ UUIDs parsed correctly:")
        print(f"   integration_id: {decoded_integration_id}")
        print(f"   user_id: {decoded_user_id}")
        
        return True
    except Exception as e:
        print(f"❌ Error decoding state: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_integration_exists():
    """Test if integration exists"""
    async with AsyncSessionLocal() as db:
        integration_id = UUID("67465695-76d2-4036-94a4-9c8db7047d6a")
        result = await db.execute(
            select(Integration)
            .where(Integration.id == integration_id)
        )
        integration = result.scalar_one_or_none()
        
        if integration:
            print(f"✅ Integration found: {integration.id}")
            print(f"   Enabled: {integration.enabled}")
            print(f"   User ID: {integration.user_id}")
            session_metadata = integration.session_metadata or {}
            print(f"   Server URL: {session_metadata.get('server_url', 'N/A')}")
            return integration
        else:
            print(f"❌ Integration not found")
            return None

async def main():
    print("🧪 Testing OAuth flow components...\n")
    
    print("1️⃣ Testing state encoding/decoding:")
    if not await test_state_encoding():
        print("❌ State encoding test failed")
        return
    
    print("\n2️⃣ Testing integration exists:")
    integration = await test_integration_exists()
    if not integration:
        print("❌ Integration test failed")
        return
    
    print("\n✅ All tests passed!")

if __name__ == "__main__":
    asyncio.run(main())

