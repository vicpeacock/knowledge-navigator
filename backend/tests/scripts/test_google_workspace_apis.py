#!/usr/bin/env python3
"""
Test completo per verificare che le API Google Workspace siano abilitate e funzionanti.
Testa Drive, Gmail e Calendar.
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
from app.models.database import User, Integration, Session, Tenant
from app.core.tool_manager import ToolManager
from app.services.oauth_token_manager import OAuthTokenManager
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Enable INFO for specific modules
logging.getLogger("app.core.mcp_client").setLevel(logging.INFO)
logging.getLogger("app.core.tool_manager").setLevel(logging.INFO)


async def test_google_workspace_apis():
    """Test completo delle API Google Workspace"""
    
    # Create database connection
    from app.core.config import settings as app_settings
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
        
        # Get user with OAuth credentials
        user_result = await db.execute(
            select(User).where(
                User.tenant_id == tenant_id,
                User.email.ilike("admin@example.com"),
                User.active == True
            ).limit(1)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            logger.error("❌ No admin user found")
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
            if "8003" in server_url or "workspace" in server_url.lower():
                google_integration = integration
                break
        
        if not google_integration:
            logger.error("❌ Google Workspace MCP integration not found")
            return
        
        logger.info(f"✅ Found Google Workspace MCP integration: {google_integration.id}")
        
        # Check OAuth credentials
        session_metadata = google_integration.session_metadata or {}
        oauth_credentials = session_metadata.get("oauth_credentials", {})
        user_id_str = str(user.id)
        
        if user_id_str not in oauth_credentials:
            logger.error(f"❌ No OAuth credentials found for user {user.email}")
            logger.info("   Please authenticate via the frontend first")
            return
        
        logger.info(f"✅ OAuth credentials found for user {user.email}")
        
        # Create test session
        test_session = Session(
            tenant_id=tenant_id,
            user_id=user.id,
            name="Test Google Workspace APIs",
            status="active"
        )
        db.add(test_session)
        await db.commit()
        await db.refresh(test_session)
        logger.info(f"✅ Created test session: {test_session.id}")
        
        try:
            tool_manager = ToolManager(db=db, tenant_id=tenant_id)
            
            # Temporarily enable all Drive/Gmail/Calendar tools for testing
            original_metadata = user.user_metadata or {}
            test_metadata = dict(original_metadata)
            current_enabled = test_metadata.get("enabled_tools", [])
            if not isinstance(current_enabled, list):
                current_enabled = []
            
            # Get all available tools
            all_tools = await tool_manager.get_mcp_tools(current_user=user, include_all=True)
            workspace_tools = [
                t for t in all_tools 
                if any(keyword in t.get("name", "").lower() 
                      for keyword in ["drive", "gmail", "calendar"])
            ]
            
            # Add workspace tools to enabled list
            workspace_tool_names = []
            for tool in workspace_tools:
                tool_name = tool.get("name")
                if tool_name and tool_name not in current_enabled:
                    current_enabled.append(tool_name)
                    workspace_tool_names.append(tool_name)
            
            test_metadata["enabled_tools"] = current_enabled
            
            # Update user metadata temporarily
            from app.models.database import User as UserModel
            from sqlalchemy import update
            await db.execute(
                update(UserModel)
                .where(UserModel.id == user.id)
                .values(user_metadata=test_metadata)
            )
            await db.commit()
            await db.refresh(user)
            
            # Verify the update worked
            refreshed_user_result = await db.execute(
                select(UserModel).where(UserModel.id == user.id)
            )
            refreshed_user = refreshed_user_result.scalar_one_or_none()
            if refreshed_user:
                refreshed_enabled = (refreshed_user.user_metadata or {}).get("enabled_tools", [])
                logger.info(f"✅ Temporarily enabled {len(workspace_tool_names)} workspace tools for testing")
                logger.info(f"   Total enabled tools: {len(refreshed_enabled)}")
                logger.info(f"   Tools enabled: {', '.join(workspace_tool_names[:10])}{'...' if len(workspace_tool_names) > 10 else ''}")
                
                # Verify specific tools are enabled
                test_tools = ["mcp_list_gmail_messages", "mcp_list_calendar_events"]
                for test_tool in test_tools:
                    if test_tool in refreshed_enabled:
                        logger.info(f"   ✅ {test_tool} is enabled")
                    else:
                        logger.warning(f"   ⚠️  {test_tool} is NOT in enabled list")
            
            # Test results
            test_results = {
                "drive": {"passed": 0, "failed": 0, "errors": []},
                "gmail": {"passed": 0, "failed": 0, "errors": []},
                "calendar": {"passed": 0, "failed": 0, "errors": []}
            }
            
            # TEST 1: Google Drive API
            logger.info("\n" + "=" * 80)
            logger.info("TEST 1: Google Drive API")
            logger.info("=" * 80)
            
            drive_tools = [
                ("mcp_list_drive_items", {}),
                ("mcp_search_drive_files", {"query": "test"}),
            ]
            
            for tool_name, params in drive_tools:
                logger.info(f"\n🔧 Testing tool: {tool_name}")
                try:
                    result = await tool_manager.execute_tool(
                        tool_name=tool_name,
                        parameters=params,
                        db=db,
                        session_id=test_session.id,
                        current_user=user
                    )
                    
                    if isinstance(result, dict):
                        if "error" in result:
                            error_msg = result.get("error", "Unknown error")
                            logger.error(f"   ❌ Error: {error_msg}")
                            test_results["drive"]["failed"] += 1
                            test_results["drive"]["errors"].append(f"{tool_name}: {error_msg}")
                        elif result.get("success") is False:
                            logger.error(f"   ❌ Tool returned success=False")
                            test_results["drive"]["failed"] += 1
                        else:
                            logger.info(f"   ✅ Tool executed successfully")
                            test_results["drive"]["passed"] += 1
                    else:
                        logger.info(f"   ✅ Tool executed (result type: {type(result)})")
                        test_results["drive"]["passed"] += 1
                except Exception as e:
                    logger.error(f"   ❌ Exception: {e}", exc_info=True)
                    test_results["drive"]["failed"] += 1
                    test_results["drive"]["errors"].append(f"{tool_name}: {str(e)}")
            
            # TEST 2: Gmail API
            logger.info("\n" + "=" * 80)
            logger.info("TEST 2: Gmail API")
            logger.info("=" * 80)
            
            # Find actual Gmail tool names
            all_tools_for_gmail = await tool_manager.get_mcp_tools(current_user=user, include_all=True)
            gmail_tool_names = [t.get("name") for t in all_tools_for_gmail if "gmail" in t.get("name", "").lower() and "search" in t.get("name", "").lower()]
            
            if not gmail_tool_names:
                logger.warning("   ⚠️  No Gmail search tools found, trying list tool")
                gmail_tool_names = [t.get("name") for t in all_tools_for_gmail if "gmail" in t.get("name", "").lower() and "list" in t.get("name", "").lower()]
            
            if gmail_tool_names:
                gmail_tool_name = gmail_tool_names[0]
                logger.info(f"   Using Gmail tool: {gmail_tool_name}")
                # Use appropriate parameters based on tool name
                if "search" in gmail_tool_name.lower():
                    # search_gmail_messages only accepts 'query' parameter
                    gmail_tools = [
                        (gmail_tool_name, {"query": "is:unread"}),
                    ]
                else:
                    gmail_tools = [
                        (gmail_tool_name, {"max_results": 5}),
                    ]
            else:
                logger.warning("   ⚠️  No Gmail tools found, skipping Gmail test")
                gmail_tools = []
            
            for tool_name, params in gmail_tools:
                logger.info(f"\n🔧 Testing tool: {tool_name}")
                try:
                    result = await tool_manager.execute_tool(
                        tool_name=tool_name,
                        parameters=params,
                        db=db,
                        session_id=test_session.id,
                        current_user=user
                    )
                    
                    if isinstance(result, dict):
                        if "error" in result:
                            error_msg = result.get("error", "Unknown error")
                            logger.error(f"   ❌ Error: {error_msg}")
                            test_results["gmail"]["failed"] += 1
                            test_results["gmail"]["errors"].append(f"{tool_name}: {error_msg}")
                        elif result.get("success") is False:
                            logger.error(f"   ❌ Tool returned success=False")
                            test_results["gmail"]["failed"] += 1
                        else:
                            logger.info(f"   ✅ Tool executed successfully")
                            test_results["gmail"]["passed"] += 1
                    else:
                        logger.info(f"   ✅ Tool executed (result type: {type(result)})")
                        test_results["gmail"]["passed"] += 1
                except Exception as e:
                    logger.error(f"   ❌ Exception: {e}", exc_info=True)
                    test_results["gmail"]["failed"] += 1
                    test_results["gmail"]["errors"].append(f"{tool_name}: {str(e)}")
            
            # TEST 3: Google Calendar API
            logger.info("\n" + "=" * 80)
            logger.info("TEST 3: Google Calendar API")
            logger.info("=" * 80)
            
            # Find actual Calendar tool names
            all_tools_for_calendar = await tool_manager.get_mcp_tools(current_user=user, include_all=True)
            calendar_tool_names = [t.get("name") for t in all_tools_for_calendar if "calendar" in t.get("name", "").lower()]
            
            if calendar_tool_names:
                calendar_tool_name = calendar_tool_names[0]
                logger.info(f"   Using Calendar tool: {calendar_tool_name}")
                # list_calendars doesn't accept max_results, use empty params
                calendar_tools = [
                    (calendar_tool_name, {}),
                ]
            else:
                logger.warning("   ⚠️  No Calendar tools found, skipping Calendar test")
                calendar_tools = []
            
            for tool_name, params in calendar_tools:
                logger.info(f"\n🔧 Testing tool: {tool_name}")
                try:
                    result = await tool_manager.execute_tool(
                        tool_name=tool_name,
                        parameters=params,
                        db=db,
                        session_id=test_session.id,
                        current_user=user
                    )
                    
                    if isinstance(result, dict):
                        if "error" in result:
                            error_msg = result.get("error", "Unknown error")
                            logger.error(f"   ❌ Error: {error_msg}")
                            test_results["calendar"]["failed"] += 1
                            test_results["calendar"]["errors"].append(f"{tool_name}: {error_msg}")
                        elif result.get("success") is False:
                            logger.error(f"   ❌ Tool returned success=False")
                            test_results["calendar"]["failed"] += 1
                        else:
                            logger.info(f"   ✅ Tool executed successfully")
                            test_results["calendar"]["passed"] += 1
                    else:
                        logger.info(f"   ✅ Tool executed (result type: {type(result)})")
                        test_results["calendar"]["passed"] += 1
                except Exception as e:
                    logger.error(f"   ❌ Exception: {e}", exc_info=True)
                    test_results["calendar"]["failed"] += 1
                    test_results["calendar"]["errors"].append(f"{tool_name}: {str(e)}")
            
            # Summary
            logger.info("\n" + "=" * 80)
            logger.info("📊 TEST SUMMARY")
            logger.info("=" * 80)
            
            total_passed = sum(r["passed"] for r in test_results.values())
            total_failed = sum(r["failed"] for r in test_results.values())
            
            for api_name, results in test_results.items():
                logger.info(f"\n{api_name.upper()}:")
                logger.info(f"  ✅ Passed: {results['passed']}")
                logger.info(f"  ❌ Failed: {results['failed']}")
                if results["errors"]:
                    logger.info(f"  Errors:")
                    for error in results["errors"]:
                        logger.info(f"    - {error}")
            
            logger.info(f"\n📈 TOTAL:")
            logger.info(f"  ✅ Passed: {total_passed}")
            logger.info(f"  ❌ Failed: {total_failed}")
            
            if total_failed == 0:
                logger.info("\n✅ ALL TESTS PASSED! APIs are working correctly.")
            else:
                logger.warning(f"\n⚠️  {total_failed} test(s) failed. Check errors above.")
            
        finally:
            # Restore original user metadata
            from app.models.database import User as UserModel
            from sqlalchemy import update
            await db.execute(
                update(UserModel)
                .where(UserModel.id == user.id)
                .values(user_metadata=original_metadata)
            )
            await db.commit()
            
            # Clean up test session
            await db.delete(test_session)
            await db.commit()
            logger.info(f"\n✅ Restored original user preferences and cleaned up test session")


if __name__ == "__main__":
    print("🧪 Testing Google Workspace APIs")
    print("=" * 80)
    asyncio.run(test_google_workspace_apis())

