#!/usr/bin/env python3
"""Quick MCP test"""
import asyncio
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

pytestmark = pytest.mark.skip(reason="Quick test MCP manuale: non eseguirlo in CI")

from app.core.mcp_client import MCPClient

async def test():
    print("Testing MCPClient...")
    client = MCPClient()
    try:
        print(f"Base URL: {client.base_url}")
        print("Calling list_tools()...")
        tools = await client.list_tools()
        print(f"✅ Retrieved {len(tools)} tools")
        if tools:
            print(f"First tool: {tools[0].get('name')}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await client.close()

if __name__ == "__main__":
    result = asyncio.run(test())
    sys.exit(0 if result else 1)

