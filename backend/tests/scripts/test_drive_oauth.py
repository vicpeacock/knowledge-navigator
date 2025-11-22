#!/usr/bin/env python3
"""
Test script to verify OAuth authentication for Google Drive tools.
This script directly tests the tool execution without going through the frontend.
"""
import asyncio
import sys
import os
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select
from app.models.database import User, Integration, Session
from app.core.tool_manager import ToolManager
from app.db.database import get_db
from app.core.config import settings as app_settings
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Also enable DEBUG for specific modules
logging.getLogger("app.core.tool_manager").setLevel(logging.DEBUG)
logging.getLogger("app.api.integrations.mcp").setLevel(logging.DEBUG)
logging.getLogger("app.services.oauth_token_manager").setLevel(logging.DEBUG)
logging.getLogger("app.core.mcp_client").setLevel(logging.DEBUG)


async def test_drive_tool():
    """Test Google Drive tool with OAuth authentication"""
    
    # Create database connection
    database_url = app_settings.database_url
    engine = create_async_engine(database_url, echo=False)
    async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session_maker() as db:
        # Get tenant_id (use default or first tenant)
        from app.models.database import Tenant
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.active == True).limit(1)
        )
        tenant = tenant_result.scalar_one_or_none()
        
        if not tenant:
            logger.error("❌ No active tenant found in database")
            return
        
        tenant_id = tenant.id
        logger.info(f"✅ Using tenant: {tenant.name} (id: {tenant_id})")
        
        # Get user with OAuth credentials (or admin user)
        # First, try to find user with OAuth credentials
        integration_result_temp = await db.execute(
            select(Integration).where(
                Integration.provider == "mcp",
                Integration.service_type == "mcp_server",
                Integration.tenant_id == tenant_id,
                Integration.enabled == True
            )
        )
        integrations_temp = integration_result_temp.scalars().all()
        
        user_with_creds = None
        for integration_temp in integrations_temp:
            session_metadata_temp = integration_temp.session_metadata or {}
            oauth_credentials = session_metadata_temp.get("oauth_credentials", {})
            if oauth_credentials:
                # Get first user ID from credentials
                user_id_strs = [uid for uid in oauth_credentials.keys() if uid != "test_user" and len(uid) == 36]
                if user_id_strs:
                    from uuid import UUID
                    try:
                        user_id_with_creds = UUID(user_id_strs[0])
                        user_result_with_creds = await db.execute(
                            select(User).where(User.id == user_id_with_creds)
                        )
                        user_with_creds = user_result_with_creds.scalar_one_or_none()
                        if user_with_creds:
                            logger.info(f"✅ Found user with OAuth credentials: {user_with_creds.email} (id: {user_with_creds.id})")
                            break
                    except Exception:
                        pass
        
        # Fallback to admin user if no user with credentials found
        if not user_with_creds:
            user_result = await db.execute(
                select(User).where(
                    User.tenant_id == tenant_id,
                    User.role == "admin",
                    User.active == True
                ).limit(1)
            )
            user_with_creds = user_result.scalar_one_or_none()
            if user_with_creds:
                logger.info(f"✅ Using admin user: {user_with_creds.email} (id: {user_with_creds.id})")
        
        user = user_with_creds
        
        if not user:
            logger.error("❌ No active user found in database")
            return
        
        logger.info(f"✅ Using user: {user.email} (id: {user.id})")
        
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
            logger.info("   Available integrations:")
            for integration in integrations:
                session_metadata = integration.session_metadata or {}
                server_url = session_metadata.get("server_url", "")
                integration_name = session_metadata.get("name", "Unknown")
                logger.info(f"   - {integration_name}: {server_url}")
            return
        
        integration_name = google_integration.session_metadata.get('name', '') or google_integration.session_metadata.get('server_url', 'Unknown')
        integration_name = google_integration.session_metadata.get('name', '') or google_integration.session_metadata.get('server_url', 'Unknown')
        logger.info(f"✅ Found Google Workspace MCP integration: {integration_name}")
        logger.info(f"   Server URL: {google_integration.session_metadata.get('server_url', '')}")
        
        # Check OAuth credentials for this user
        session_metadata = google_integration.session_metadata or {}
        oauth_credentials = session_metadata.get("oauth_credentials", {})
        user_id_str = str(user.id)
        
        logger.info(f"\n🔍 Checking OAuth credentials...")
        logger.info(f"   User ID: {user_id_str}")
        logger.info(f"   OAuth credentials keys in database: {list(oauth_credentials.keys())}")
        
        if user_id_str not in oauth_credentials:
            logger.error(f"\n❌ No OAuth credentials found for user {user.email} (ID: {user_id_str})")
            logger.info("   Please authenticate via the frontend first:")
            logger.info(f"   Go to Integrations → {integration_name} → Authorize OAuth")
            
            # Check if there are any credentials for other users - offer to test with one of them
            if oauth_credentials:
                logger.info(f"\n   ℹ️  Found OAuth credentials for other users:")
                for other_user_id in oauth_credentials.keys():
                    logger.info(f"     - User ID: {other_user_id}")
                
                # Try to find one of these users and test with them
                logger.info(f"\n   🔍 Attempting to test with a user that has OAuth credentials...")
                test_user_with_creds = None
                for other_user_id in oauth_credentials.keys():
                    try:
                        other_user_uuid = UUID(other_user_id) if other_user_id != "test_user" else None
                        if other_user_uuid:
                            other_user_result = await db.execute(
                                select(User).where(User.id == other_user_uuid)
                            )
                            test_user_with_creds = other_user_result.scalar_one_or_none()
                            if test_user_with_creds:
                                logger.info(f"   ✅ Found user with credentials: {test_user_with_creds.email} (ID: {other_user_id})")
                                break
                    except Exception:
                        continue
                
                if test_user_with_creds:
                    logger.info(f"\n   🧪 Testing with user: {test_user_with_creds.email}")
                    user = test_user_with_creds
                    user_id_str = str(user.id)
                else:
                    logger.warning(f"   ⚠️  Could not find user records for the OAuth credentials")
                    logger.info("   Please authenticate with your user account via the frontend first")
                    return
            else:
                return
        
        # Check if credentials are encrypted/valid
        try:
            from app.api.integrations.mcp import _decrypt_credentials
            encrypted_creds = oauth_credentials[user_id_str]
            credentials = _decrypt_credentials(encrypted_creds, app_settings.credentials_encryption_key)
            has_token = bool(credentials.get("token"))
            has_refresh_token = bool(credentials.get("refresh_token"))
            logger.info(f"   ✅ Credentials found and decrypted successfully")
            logger.info(f"   Has access token: {has_token}")
            logger.info(f"   Has refresh token: {has_refresh_token}")
        except Exception as e:
            logger.error(f"   ⚠️  Error decrypting credentials: {e}")
            logger.info("   Credentials may be invalid or corrupted")
            return
        
        logger.info(f"✅ OAuth credentials found for user {user.email}")
        
        # Create a test session for the tool execution
        test_session = Session(
            tenant_id=tenant_id,
            user_id=user.id,
            name="Test Drive OAuth",
            status="active"
        )
        db.add(test_session)
        await db.commit()
        await db.refresh(test_session)
        
        logger.info(f"✅ Created test session: {test_session.id}")
        
        try:
            # Create ToolManager
            tool_manager = ToolManager(db=db, tenant_id=tenant_id)
            
            # List available tools to find the drive tool
            logger.info("\n🔍 Listing available MCP tools...")
            mcp_tools = await tool_manager.get_mcp_tools(current_user=user)
            drive_tools = [t for t in mcp_tools if "drive" in t.get("name", "").lower()]
            
            logger.info(f"✅ Found {len(drive_tools)} Drive tools:")
            for tool in drive_tools:
                logger.info(f"   - {tool.get('name')}: {tool.get('description', '')[:100]}")
            
            if not drive_tools:
                logger.error("❌ No Drive tools found")
                return
            
            # Use the first drive tool (usually mcp_drive_list_files)
            drive_tool_name = drive_tools[0].get("name")
            logger.info(f"\n🔧 Testing tool: {drive_tool_name}")
            
            # Execute the tool
            logger.info("\n🚀 Executing tool...")
            logger.info("=" * 80)
            
            try:
                result = await tool_manager.execute_tool(
                    tool_name=drive_tool_name,
                    parameters={},  # Empty parameters for list_files
                    db=db,
                    session_id=test_session.id,
                    current_user=user
                )
                
                logger.info("=" * 80)
                logger.info("✅ Tool executed successfully!")
                logger.info(f"\n📄 Result type: {type(result)}")
                
                if isinstance(result, dict):
                    logger.info(f"📄 Result keys: {list(result.keys())}")
                    # Print a preview of the result
                    import json
                    result_preview = json.dumps(result, indent=2, default=str)[:1000]
                    logger.info(f"📄 Result preview:\n{result_preview}")
                else:
                    logger.info(f"📄 Result: {result}")
                
            except Exception as e:
                logger.error("=" * 80)
                logger.error(f"❌ Tool execution failed: {e}", exc_info=True)
                
                # Check if it's an OAuth error
                error_msg = str(e).lower()
                if "oauth" in error_msg or "401" in error_msg or "unauthorized" in error_msg or "authentication" in error_msg:
                    logger.error("\n🔐 This appears to be an OAuth authentication error.")
                    logger.error("   Possible causes:")
                    logger.error("   1. OAuth token expired and refresh failed")
                    logger.error("   2. OAuth credentials invalid")
                    logger.error("   3. User needs to re-authenticate")
                    logger.error(f"\n   Solution: Go to Integrations → {integration_name} → Authorize OAuth")
        
        finally:
            # Clean up test session
            await db.delete(test_session)
            await db.commit()
            logger.info(f"\n🧹 Cleaned up test session")


if __name__ == "__main__":
    print("🔐 Testing Google Drive OAuth Authentication")
    print("=" * 80)
    asyncio.run(test_drive_tool())

