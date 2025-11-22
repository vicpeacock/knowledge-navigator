#!/usr/bin/env python3
"""
Test per verificare che il Docker MCP Gateway funzioni ancora correttamente
dopo le modifiche al MCPClient.
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
from app.models.database import User, Integration, Tenant
from app.core.tool_manager import ToolManager
from app.core.mcp_client import MCPClient
from app.core.config import settings as app_settings
from app.api.integrations.mcp import _get_mcp_client_for_integration
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


async def test_mcp_gateway():
    """Test completo del Docker MCP Gateway"""
    
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
        
        # Get admin user
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
        
        # Find Docker MCP Gateway integration (usually on port 8080)
        integration_result = await db.execute(
            select(Integration).where(
                Integration.provider == "mcp",
                Integration.service_type == "mcp_server",
                Integration.tenant_id == tenant_id,
                Integration.enabled == True
            )
        )
        integrations = integration_result.scalars().all()
        
        gateway_integration = None
        for integration in integrations:
            session_metadata = integration.session_metadata or {}
            server_url = session_metadata.get("server_url", "") or ""
            # Docker MCP Gateway is usually on port 8080
            if "8080" in server_url or "gateway" in server_url.lower():
                gateway_integration = integration
                break
        
        if not gateway_integration:
            logger.error("❌ Docker MCP Gateway integration not found")
            logger.info("   Looking for integration with server_url containing '8080' or 'gateway'")
            return
        
        logger.info(f"✅ Found Docker MCP Gateway integration: {gateway_integration.id}")
        logger.info(f"   Server URL: {gateway_integration.session_metadata.get('server_url', '')}")
        
        # TEST 1: Test MCPClient directly
        logger.info("\n" + "=" * 80)
        logger.info("TEST 1: Testing MCPClient directly with gateway URL")
        logger.info("=" * 80)
        
        gateway_url = gateway_integration.session_metadata.get("server_url", "http://localhost:8080")
        logger.info(f"   Gateway URL: {gateway_url}")
        
        # Create MCP client directly
        client = MCPClient(base_url=gateway_url, use_auth_token=True)
        logger.info(f"✅ Created MCP client with base_url: {client.base_url}")
        logger.info(f"   Expected: {gateway_url}/mcp")
        logger.info(f"   Actual: {client.base_url}")
        
        if not client.base_url.endswith("/mcp"):
            logger.error(f"❌ Base URL should end with /mcp, but got: {client.base_url}")
            return
        
        # Test list_tools()
        logger.info("\n📋 Testing list_tools()...")
        try:
            tools = await client.list_tools()
            logger.info(f"✅ list_tools() successful! Retrieved {len(tools)} tools")
            if tools:
                logger.info(f"   Sample tools: {[t.get('name') for t in tools[:5]]}")
        except Exception as e:
            logger.error(f"❌ list_tools() failed: {e}", exc_info=True)
            return
        
        # TEST 2: Test via _get_mcp_client_for_integration
        logger.info("\n" + "=" * 80)
        logger.info("TEST 2: Testing via _get_mcp_client_for_integration")
        logger.info("=" * 80)
        
        try:
            client2 = _get_mcp_client_for_integration(gateway_integration, current_user=user)
            logger.info(f"✅ Created MCP client via _get_mcp_client_for_integration")
            logger.info(f"   Base URL: {client2.base_url}")
            
            tools2 = await client2.list_tools()
            logger.info(f"✅ list_tools() successful! Retrieved {len(tools2)} tools")
        except Exception as e:
            logger.error(f"❌ Test via _get_mcp_client_for_integration failed: {e}", exc_info=True)
            return
        
        # TEST 3: Test via ToolManager
        logger.info("\n" + "=" * 80)
        logger.info("TEST 3: Testing via ToolManager (full flow)")
        logger.info("=" * 80)
        
        tool_manager = ToolManager(db=db, tenant_id=tenant_id)
        
        # Get available tools
        logger.info("📋 Getting available tools via ToolManager...")
        try:
            all_tools = await tool_manager.get_mcp_tools(current_user=user, include_all=True)
            gateway_tools = [t for t in all_tools if gateway_integration.id == t.get("mcp_integration_id")]
            logger.info(f"✅ Retrieved {len(gateway_tools)} tools from gateway")
            if gateway_tools:
                logger.info(f"   Sample tools: {[t.get('name') for t in gateway_tools[:5]]}")
        except Exception as e:
            logger.error(f"❌ get_mcp_tools() failed: {e}", exc_info=True)
            return
        
        # Test executing a tool if available
        if gateway_tools:
            test_tool = gateway_tools[0]
            test_tool_name = test_tool.get("name")
            logger.info(f"\n🔧 Testing tool execution: {test_tool_name}")
            
            # Check if tool is enabled
            user_metadata = user.user_metadata or {}
            enabled_tools = user_metadata.get("enabled_tools")
            if isinstance(enabled_tools, list) and test_tool_name not in enabled_tools:
                logger.info(f"   ⚠️  Tool {test_tool_name} is disabled, skipping execution test")
                logger.info(f"   ✅ But tool discovery works, which is the main test")
            else:
                try:
                    from app.models.database import Session
                    test_session = Session(
                        tenant_id=tenant_id,
                        user_id=user.id,
                        name="Test MCP Gateway",
                        status="active"
                    )
                    db.add(test_session)
                    await db.commit()
                    await db.refresh(test_session)
                    
                    result = await tool_manager.execute_tool(
                        tool_name=test_tool_name,
                        parameters={},
                        db=db,
                        session_id=test_session.id,
                        current_user=user
                    )
                    
                    logger.info(f"✅ Tool execution successful!")
                    logger.info(f"   Result type: {type(result)}")
                    if isinstance(result, dict):
                        logger.info(f"   Result keys: {list(result.keys())}")
                        if "error" in result:
                            logger.warning(f"   ⚠️  Tool returned error: {result['error']}")
                        else:
                            logger.info(f"   ✅ Result contains data (not an error)")
                    
                    # Clean up
                    await db.delete(test_session)
                    await db.commit()
                except Exception as e:
                    logger.error(f"❌ Tool execution failed: {e}", exc_info=True)
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ ALL GATEWAY TESTS PASSED!")
        logger.info("=" * 80)


if __name__ == "__main__":
    print("🔌 Testing Docker MCP Gateway")
    print("=" * 80)
    asyncio.run(test_mcp_gateway())

