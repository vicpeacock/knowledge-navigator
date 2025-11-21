#!/usr/bin/env python3
"""Test MCP list_tools with OAuth"""
import asyncio
import sys
from pathlib import Path
from uuid import UUID

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.database import AsyncSessionLocal
from app.models.database import Integration, User
from sqlalchemy import select
from app.api.integrations.mcp import _get_mcp_client_for_integration

async def test_list_tools():
    """Test list_tools for both integrations"""
    async with AsyncSessionLocal() as db:
        # Test Google Workspace MCP
        google_integration_id = UUID("67465695-76d2-4036-94a4-9c8db7047d6a")
        user_id = UUID("5e54d258-7127-42e8-ae9b-7cb65f9fb01e")
        
        print("🔍 Testing Google Workspace MCP...")
        result = await db.execute(
            select(Integration)
            .where(Integration.id == google_integration_id)
        )
        google_integration = result.scalar_one_or_none()
        
        if google_integration:
            user_result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            
            if user:
                print(f"✅ Found integration and user")
                session_metadata = google_integration.session_metadata or {}
                oauth_credentials = session_metadata.get("oauth_credentials", {})
                user_id_str = str(user.id)
                print(f"   OAuth credentials keys: {list(oauth_credentials.keys())}")
                print(f"   Has credentials for user: {user_id_str in oauth_credentials}")
                
                try:
                    client = _get_mcp_client_for_integration(google_integration, current_user=user)
                    print(f"✅ Client created")
                    print(f"   Base URL: {client.base_url}")
                    print(f"   Headers: {list(client.headers.keys())}")
                    if "Authorization" in client.headers:
                        token_preview = client.headers["Authorization"][:30]
                        print(f"   Authorization header: {token_preview}...")
                    
                    print(f"\n🔍 Calling list_tools()...")
                    tools = await client.list_tools()
                    print(f"✅ Retrieved {len(tools)} tools")
                    if tools:
                        print(f"   First 5 tools: {[t.get('name', '') for t in tools[:5]]}")
                    else:
                        print(f"   ⚠️  No tools returned!")
                except Exception as e:
                    print(f"❌ Error: {e}")
                    import traceback
                    traceback.print_exc()
        
        # Test Docker MCP Gateway
        print(f"\n🔍 Testing Docker MCP Gateway...")
        docker_integration_id = UUID("60d18a65-b29f-49cf-a066-40c6c00640ed")
        result = await db.execute(
            select(Integration)
            .where(Integration.id == docker_integration_id)
        )
        docker_integration = result.scalar_one_or_none()
        
        if docker_integration:
            print(f"✅ Found Docker integration")
            try:
                client = _get_mcp_client_for_integration(docker_integration, current_user=None)
                print(f"✅ Client created")
                print(f"   Base URL: {client.base_url}")
                print(f"   Headers: {list(client.headers.keys())}")
                
                print(f"\n🔍 Calling list_tools()...")
                tools = await client.list_tools()
                print(f"✅ Retrieved {len(tools)} tools")
                if tools:
                    print(f"   First 5 tools: {[t.get('name', '') for t in tools[:5]]}")
                else:
                    print(f"   ⚠️  No tools returned!")
            except Exception as e:
                print(f"❌ Error: {e}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_list_tools())

