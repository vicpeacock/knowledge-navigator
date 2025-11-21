#!/usr/bin/env python3
"""Check MCP integrations in database"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.database import AsyncSessionLocal
from app.models.database import Integration, User
from sqlalchemy import select
from app.core.config import settings
import json

async def check_integrations():
    async with AsyncSessionLocal() as db:
        # Get all MCP integrations
        result = await db.execute(
            select(Integration)
            .where(Integration.service_type == "mcp_server")
        )
        integrations = result.scalars().all()
        
        print(f"\n🔍 Found {len(integrations)} MCP integrations:\n")
        
        for integration in integrations:
            print(f"Integration ID: {integration.id}")
            print(f"  Enabled: {integration.enabled}")
            print(f"  User ID: {integration.user_id}")
            print(f"  Tenant ID: {integration.tenant_id}")
            
            session_metadata = integration.session_metadata or {}
            server_url = session_metadata.get("server_url", "")
            name = session_metadata.get("name", "")
            oauth_required = session_metadata.get("oauth_required", False)
            available_tools = session_metadata.get("available_tools", [])
            oauth_credentials = session_metadata.get("oauth_credentials", {})
            
            print(f"  Server URL: {server_url}")
            print(f"  Name: {name}")
            print(f"  OAuth Required: {oauth_required}")
            print(f"  Available Tools Count: {len(available_tools)}")
            if available_tools:
                print(f"  Available Tools: {available_tools[:10]}{'...' if len(available_tools) > 10 else ''}")
            
            print(f"  OAuth Credentials Users: {list(oauth_credentials.keys())}")
            
            # Check if this is Google Workspace MCP
            is_google_workspace = (
                "workspace" in server_url.lower() or
                "8003" in server_url or
                "google" in server_url.lower()
            )
            print(f"  Is Google Workspace: {is_google_workspace}")
            
            # Get user info if user_id is set
            if integration.user_id:
                user_result = await db.execute(
                    select(User).where(User.id == integration.user_id)
                )
                user = user_result.scalar_one_or_none()
                if user:
                    print(f"  User Email: {user.email}")
                    # Check if user has OAuth credentials
                    user_id_str = str(user.id)
                    if user_id_str in oauth_credentials:
                        print(f"  ✅ OAuth credentials found for user {user.email}")
                    else:
                        print(f"  ⚠️  No OAuth credentials for user {user.email}")
            
            print()
        
        # Check users with MCP tool preferences
        print("\n👥 Users with MCP tool preferences:\n")
        result = await db.execute(select(User))
        users = result.scalars().all()
        
        for user in users:
            user_metadata = user.user_metadata or {}
            mcp_preferences = user_metadata.get("mcp_tools_preferences", {})
            if mcp_preferences:
                print(f"User: {user.email} ({user.id})")
                for integration_id, tools in mcp_preferences.items():
                    print(f"  Integration {integration_id}: {len(tools)} tools selected")
                    if tools:
                        print(f"    Tools: {tools[:5]}{'...' if len(tools) > 5 else ''}")
                print()

if __name__ == "__main__":
    asyncio.run(check_integrations())

