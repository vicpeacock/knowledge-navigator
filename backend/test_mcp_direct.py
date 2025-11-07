#!/usr/bin/env python3
"""Direct MCP API tests"""
import asyncio
import sys
import os
import pytest
from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

pytestmark = pytest.mark.skip(reason="Test MCP diretto manuale: richiede ambiente dedicato")

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def test_direct_connection():
    """Test direct connection using MCP library"""
    base_url = "http://localhost:8080"
    
    print(f"\n🔧 Testing direct MCP connection to {base_url}")
    print("="*60)
    
    exit_stack = AsyncExitStack()
    
    try:
        print("\n1. Creating streamablehttp_client...")
        transport = await exit_stack.enter_async_context(
            streamablehttp_client(base_url, headers={})
        )
        read_stream, write_stream, session_info = transport
        print(f"   ✅ Transport created: {type(transport)}")
        print(f"   ✅ Session info: {session_info}")
        
        print("\n2. Creating ClientSession...")
        session = await exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        print("   ✅ ClientSession created")
        
        print("\n3. Calling session.initialize()...")
        init_result = await asyncio.wait_for(
            session.initialize(),
            timeout=15.0
        )
        print(f"   ✅ Initialize completed: {init_result}")
        
        print("\n4. Calling session.list_tools()...")
        tools_response = await asyncio.wait_for(
            session.list_tools(),
            timeout=30.0
        )
        print(f"   ✅ Tools retrieved: {len(tools_response.tools)} tools")
        
        for i, tool in enumerate(tools_response.tools[:5], 1):
            print(f"   {i}. {tool.name}")
        
        print("\n✅ All tests passed!")
        return True
        
    except asyncio.TimeoutError as e:
        print(f"\n❌ Timeout: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("\n5. Cleaning up...")
        await exit_stack.aclose()
        print("   ✅ Cleanup completed")

if __name__ == "__main__":
    result = asyncio.run(test_direct_connection())
    sys.exit(0 if result else 1)

