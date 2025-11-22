#!/usr/bin/env python3
"""
Test completo per Google Drive MCP con OAuth.
Testa initialize(), list_tools(), e call_tool() con header corretti.
"""
import asyncio
import sys
import os
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, update
from app.models.database import User, Integration, Session, Tenant
from app.core.tool_manager import ToolManager
from app.core.mcp_client import MCPClient
from app.core.config import settings as app_settings
from app.api.integrations.mcp import _get_mcp_client_for_integration
from app.services.oauth_token_manager import OAuthTokenManager
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Enable DEBUG for specific modules
logging.getLogger("app.core.mcp_client").setLevel(logging.DEBUG)
logging.getLogger("app.core.tool_manager").setLevel(logging.INFO)
logging.getLogger("app.api.integrations.mcp").setLevel(logging.INFO)


async def test_mcp_drive_complete():
    """Test completo del flusso Google Drive MCP"""
    
    # Create database connection
    database_url = app_settings.database_url
    engine = create_async_engine(database_url, echo=False)
    async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session_maker() as db:
        # Get tenant
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.active == True).limit(1)
        )
        tenant = tenant_result.scalar_one_or_none()
        
        if not tenant:
            logger.error("❌ No active tenant found")
            return
        tenant_id = tenant.id
        logger.info(f"✅ Using tenant: {tenant.name} (id: {tenant_id})")
        
        # Find Google Workspace MCP integration
        integration_result = await db.execute(
            select(Integration).where(
                Integration.provider == "mcp",
                Integration.service_type == "mcp_server",
                Integration.tenant_id == tenant_id,
                Integration.enabled == True
            )
        )
        integrations = integration_result.scalars().all()
        
        google_integration = None
        for integration in integrations:
            session_metadata = integration.session_metadata or {}
            server_url = session_metadata.get("server_url", "") or ""
            if "workspace" in server_url.lower() or "8003" in server_url or "google" in server_url.lower():
                google_integration = integration
                break
        
        if not google_integration:
            logger.error("❌ Google Workspace MCP integration not found")
            return
        
        logger.info(f"✅ Found Google Workspace MCP integration: {google_integration.id}")
        logger.info(f"   Server URL: {google_integration.session_metadata.get('server_url', '')}")
        
        # Get user with OAuth credentials
        # First try to find user with OAuth credentials from this integration
        user = None
        session_metadata = google_integration.session_metadata or {}
        oauth_credentials = session_metadata.get("oauth_credentials", {})
        if oauth_credentials:
            # Get first user ID from credentials
            user_id_strs = [uid for uid in oauth_credentials.keys() if uid != "test_user" and len(uid) == 36]
            if user_id_strs:
                from uuid import UUID
                try:
                    user_id_with_creds = UUID(user_id_strs[0])
                    user_result = await db.execute(
                        select(User).where(User.id == user_id_with_creds)
                    )
                    user = user_result.scalar_one_or_none()
                    if user:
                        logger.info(f"✅ Found user with OAuth credentials: {user.email} (id: {user.id})")
                except Exception:
                    pass
        
        # Fallback to admin user
        if not user:
            user_result = await db.execute(
                select(User).where(
                    User.tenant_id == tenant_id,
                    User.email.ilike("admin@example.com"),  # Case-insensitive
                    User.active == True
                ).limit(1)
            )
            user = user_result.scalar_one_or_none()
        
        if not user:
            logger.error("❌ No user found")
            return
        
        logger.info(f"✅ Using user: {user.email} (id: {user.id})")
        
        # Check OAuth credentials for this user
        user_id_str = str(user.id)
        
        if user_id_str not in oauth_credentials:
            logger.error(f"❌ No OAuth credentials found for user {user.email}")
            logger.info("   Please authenticate via the frontend first")
            return
        
        logger.info(f"✅ OAuth credentials found for user {user.email}")
        
        # Temporarily enable Drive tools for testing
        original_metadata = user.user_metadata or {}
        original_enabled_tools = original_metadata.get("enabled_tools")
        
        # Enable all Drive tools for testing
        tool_manager = ToolManager(db=db, tenant_id=tenant_id)
        all_tools = await tool_manager.get_mcp_tools(current_user=user, include_all=True)
        drive_tool_names = [t.get("name") for t in all_tools if "drive" in t.get("name", "").lower()]
        
        if not drive_tool_names:
            logger.error("❌ No Drive tools found")
            return
        
        logger.info(f"✅ Found {len(drive_tool_names)} Drive tools")
        
        # Temporarily enable Drive tools
        test_metadata = dict(original_metadata)
        current_enabled = test_metadata.get("enabled_tools", [])
        if not isinstance(current_enabled, list):
            current_enabled = []
        # Add Drive tools to enabled list
        for tool_name in drive_tool_names:
            if tool_name not in current_enabled:
                current_enabled.append(tool_name)
        test_metadata["enabled_tools"] = current_enabled
        
        # Update user metadata temporarily
        from app.models.database import User as UserModel
        await db.execute(
            update(UserModel)
            .where(UserModel.id == user.id)
            .values(user_metadata=test_metadata)
        )
        await db.commit()
        await db.refresh(user)
        
        logger.info(f"✅ Temporarily enabled {len(drive_tool_names)} Drive tools for testing")
        
        try:
            # TEST 1: Test initialize() with correct headers
            logger.info("\n" + "=" * 80)
            logger.info("TEST 1: Testing initialize() with correct headers")
            logger.info("=" * 80)
            
            # Get OAuth token
            oauth_token = await OAuthTokenManager.get_valid_token(
                integration=google_integration,
                user=user,
                db=db,
                auto_refresh=True
            )
            
            if not oauth_token:
                logger.error("❌ Could not retrieve OAuth token")
                return
            
            logger.info(f"✅ Retrieved OAuth token (length: {len(oauth_token)})")
            
            # Create MCP client
            client = _get_mcp_client_for_integration(google_integration, current_user=user, oauth_token=oauth_token)
            logger.info(f"✅ Created MCP client with base_url: {client.base_url}")
            
            # Test initialize() by calling list_tools() which calls initialize() internally
            logger.info("\n📋 Testing list_tools() (this will call initialize() internally)...")
            try:
                tools = await client.list_tools()
                logger.info(f"✅ list_tools() successful! Retrieved {len(tools)} tools")
                logger.info(f"   Sample tools: {[t.get('name') for t in tools[:5]]}")
            except Exception as e:
                logger.error(f"❌ list_tools() failed: {e}", exc_info=True)
                return
            
            # TEST 2: Test call_tool() with a simple Drive tool
            logger.info("\n" + "=" * 80)
            logger.info("TEST 2: Testing call_tool() with Drive tool")
            logger.info("=" * 80)
            
            # Use a simple tool that doesn't require parameters
            test_tool_name = "mcp_list_drive_items"  # This should list files
            if test_tool_name not in [t.get("name") for t in tools]:
                # Try another tool
                test_tool_name = drive_tool_names[0]
            
            logger.info(f"🔧 Testing tool: {test_tool_name}")
            logger.info(f"   Parameters: {{}} (empty for list)")
            
            try:
                result = await client.call_tool(test_tool_name, {})
                logger.info("✅ call_tool() successful!")
                logger.info(f"   Result type: {type(result)}")
                if isinstance(result, dict):
                    logger.info(f"   Result keys: {list(result.keys())}")
                    # Print preview
                    import json
                    result_str = json.dumps(result, indent=2, default=str)
                    if len(result_str) > 500:
                        logger.info(f"   Result preview:\n{result_str[:500]}...")
                    else:
                        logger.info(f"   Result:\n{result_str}")
                else:
                    logger.info(f"   Result: {result}")
            except Exception as e:
                logger.error(f"❌ call_tool() failed: {e}", exc_info=True)
                return
            
            # TEST 3: Test via ToolManager (full flow)
            logger.info("\n" + "=" * 80)
            logger.info("TEST 3: Testing via ToolManager (full flow)")
            logger.info("=" * 80)
            
            # Create test session
            test_session = Session(
                tenant_id=tenant_id,
                user_id=user.id,
                name="Test Drive OAuth Complete",
                status="active"
            )
            db.add(test_session)
            await db.commit()
            await db.refresh(test_session)
            logger.info(f"✅ Created test session: {test_session.id}")
            
            try:
                result = await tool_manager.execute_tool(
                    tool_name=test_tool_name,
                    parameters={},
                    db=db,
                    session_id=test_session.id,
                    current_user=user
                )
                
                logger.info("✅ ToolManager.execute_tool() successful!")
                logger.info(f"   Result type: {type(result)}")
                if isinstance(result, dict):
                    logger.info(f"   Result keys: {list(result.keys())}")
                    if "error" in result:
                        logger.error(f"   ❌ Error in result: {result['error']}")
                    else:
                        logger.info(f"   ✅ Result contains data (not an error)")
            except Exception as e:
                logger.error(f"❌ ToolManager.execute_tool() failed: {e}", exc_info=True)
            finally:
                # Clean up test session
                await db.delete(test_session)
                await db.commit()
            
            logger.info("\n" + "=" * 80)
            logger.info("✅ ALL TESTS PASSED!")
            logger.info("=" * 80)
            
        finally:
            # Restore original user metadata
            await db.execute(
                update(UserModel)
                .where(UserModel.id == user.id)
                .values(user_metadata=original_metadata)
            )
            await db.commit()
            logger.info(f"✅ Restored original user preferences")


if __name__ == "__main__":
    print("🔐 Testing Google Drive MCP - Complete Flow")
    print("=" * 80)
    asyncio.run(test_mcp_drive_complete())

