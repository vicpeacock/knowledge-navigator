#!/usr/bin/env python3
"""Test MCP client with Ollama"""
import asyncio
from app.core.mcp_client import MCPClient

async def test():
    print("Testing MCP Client...")
    client = MCPClient()
    
    try:
        # Test 1: List tools
        print("\n1. Testing list_tools()...")
        tools = await client.list_tools()
        print(f"   ✅ Found {len(tools)} tools")
        
        if tools:
            print(f"\n   First 5 tools:")
            for i, tool in enumerate(tools[:5], 1):
                print(f"   {i}. {tool.get('name')}")
        
        # Test 2: Call a simple tool (browser_navigate)
        print("\n2. Testing call_tool(browser_navigate)...")
        result = await client.call_tool(
            "browser_navigate",
            {"url": "https://example.com"}
        )
        print(f"   ✅ Tool call successful")
        print(f"   Result preview: {str(result)[:200]}...")
        
        # Test 3: Browser snapshot
        print("\n3. Testing call_tool(browser_snapshot)...")
        result2 = await client.call_tool(
            "browser_snapshot",
            {}
        )
        print(f"   ✅ Snapshot successful")
        print(f"   Result preview: {str(result2)[:200]}...")
        
        print("\n✅ All MCP tests passed!")
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

