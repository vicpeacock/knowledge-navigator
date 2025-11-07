#!/usr/bin/env python3
"""Simple MCP test"""
import asyncio
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

pytestmark = pytest.mark.skip(reason="Test MCP semplificato da eseguire manualmente")

from app.core.mcp_client import MCPClient

async def test():
    client = MCPClient()
    try:
        # Test list_tools
        print("1. Testing list_tools()...")
        tools = await client.list_tools()
        print(f"   ✅ Found {len(tools)} tools")
        
        # Test call_tool (browser_navigate)
        print("\n2. Testing call_tool(browser_navigate)...")
        result = await client.call_tool(
            "browser_navigate",
            {"url": "https://example.com"}
        )
        print(f"   ✅ Tool call successful")
        print(f"   Result preview: {str(result)[:200]}")
        
        # Test browser_snapshot
        print("\n3. Testing call_tool(browser_snapshot)...")
        result2 = await client.call_tool(
            "browser_snapshot",
            {}
        )
        print(f"   ✅ Snapshot successful")
        print(f"   Result preview: {str(result2)[:200]}")
        
        print("\n✅ All tests passed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await client.close()

if __name__ == "__main__":
    result = asyncio.run(test())
    exit(0 if result else 1)

