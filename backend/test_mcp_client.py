#!/usr/bin/env python3
"""
Test script for MCP Client
Tests the MCP client directly without going through the chatbot
"""
import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.mcp_client import MCPClient
from app.core.config import settings
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)


async def test_list_tools():
    """Test listing available tools"""
    print("\n" + "="*60)
    print("TEST 1: List Available Tools")
    print("="*60)
    
    client = MCPClient()
    try:
        print(f"Connecting to {client.base_url}...")
        print("Note: This may take up to 30 seconds for the first connection...")
        tools = await asyncio.wait_for(
            client.list_tools(),
            timeout=60.0  # Increased timeout
        )
        print(f"\n✅ Successfully retrieved {len(tools)} tools")
        
        if tools:
            print("\nFirst 5 tools:")
            for i, tool in enumerate(tools[:5], 1):
                print(f"  {i}. {tool.get('name', 'unknown')}")
                print(f"     Description: {tool.get('description', 'N/A')[:80]}...")
            
            # Find browser tools
            browser_tools = [t for t in tools if 'browser' in t.get('name', '').lower() or 'navigate' in t.get('name', '').lower()]
            if browser_tools:
                print(f"\n🌐 Found {len(browser_tools)} browser/navigation tools:")
                for tool in browser_tools[:5]:
                    print(f"  - {tool.get('name')}")
        else:
            print("⚠️  No tools found")
        
        return tools
    except asyncio.TimeoutError:
        print(f"\n❌ Timeout listing tools after 45 seconds")
        return []
    except Exception as e:
        print(f"\n❌ Error listing tools: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        try:
            await client.close()
        except:
            pass


async def test_call_browser_navigate():
    """Test calling browser_navigate tool"""
    print("\n" + "="*60)
    print("TEST 2: Call browser_navigate Tool")
    print("="*60)
    
    client = MCPClient()
    try:
        # First, list tools to find the correct name
        tools = await client.list_tools()
        
        # Find browser navigate tool
        navigate_tool = None
        for tool in tools:
            name = tool.get('name', '').lower()
            if 'navigate' in name and 'back' not in name:
                navigate_tool = tool.get('name')
                break
        
        if not navigate_tool:
            print("⚠️  browser_navigate tool not found in available tools")
            print("Available tool names (first 10):")
            for tool in tools[:10]:
                print(f"  - {tool.get('name')}")
            return None
        
        print(f"\n🔧 Using tool: {navigate_tool}")
        print(f"   URL: http://swisspulse.band")
        
        # Call the tool
        result = await client.call_tool(
            navigate_tool,
            {"url": "http://swisspulse.band"}
        )
        
        print(f"\n✅ Tool call successful!")
        print(f"Result type: {type(result)}")
        print(f"Result keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
        print(f"\nResult preview (first 500 chars):")
        result_str = str(result)
        print(result_str[:500])
        if len(result_str) > 500:
            print("...")
        
        return result
    except Exception as e:
        print(f"\n❌ Error calling tool: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        await client.close()


async def test_call_browser_snapshot():
    """Test calling browser_snapshot tool"""
    print("\n" + "="*60)
    print("TEST 3: Call browser_snapshot Tool")
    print("="*60)
    
    client = MCPClient()
    try:
        # First, list tools to find the correct name
        tools = await client.list_tools()
        
        # Find browser snapshot tool
        snapshot_tool = None
        for tool in tools:
            name = tool.get('name', '').lower()
            if 'snapshot' in name:
                snapshot_tool = tool.get('name')
                break
        
        if not snapshot_tool:
            print("⚠️  browser_snapshot tool not found")
            return None
        
        print(f"\n🔧 Using tool: {snapshot_tool}")
        
        # Call the tool (no parameters needed for snapshot)
        result = await client.call_tool(
            snapshot_tool,
            {}
        )
        
        print(f"\n✅ Tool call successful!")
        print(f"Result type: {type(result)}")
        print(f"Result keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
        print(f"\nResult preview (first 1000 chars):")
        result_str = str(result)
        print(result_str[:1000])
        if len(result_str) > 1000:
            print("...")
        
        return result
    except Exception as e:
        print(f"\n❌ Error calling tool: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        await client.close()


async def test_multiple_clients():
    """Test that multiple clients can work independently"""
    print("\n" + "="*60)
    print("TEST 4: Multiple Clients")
    print("="*60)
    
    client1 = MCPClient()
    client2 = MCPClient()
    
    try:
        print("\n🔧 Testing client 1...")
        tools1 = await client1.list_tools()
        print(f"✅ Client 1 retrieved {len(tools1)} tools")
        
        print("\n🔧 Testing client 2...")
        tools2 = await client2.list_tools()
        print(f"✅ Client 2 retrieved {len(tools2)} tools")
        
        if len(tools1) == len(tools2):
            print(f"\n✅ Both clients retrieved the same number of tools ({len(tools1)})")
        else:
            print(f"\n⚠️  Clients retrieved different numbers of tools: {len(tools1)} vs {len(tools2)}")
        
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await client1.close()
        await client2.close()


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("MCP Client Direct Tests")
    print("="*60)
    print(f"MCP Gateway URL: {settings.mcp_gateway_url}")
    print(f"Testing connection...\n")
    
    results = {}
    
    # Test 1: List tools
    try:
        tools = await test_list_tools()
        results['list_tools'] = len(tools) > 0
    except Exception as e:
        results['list_tools'] = False
        print(f"❌ Test 1 failed: {e}")
    
    # Test 2: Call browser_navigate (if tools available)
    if results.get('list_tools'):
        try:
            result = await test_call_browser_navigate()
            results['browser_navigate'] = result is not None
        except Exception as e:
            results['browser_navigate'] = False
            print(f"❌ Test 2 failed: {e}")
    
    # Test 3: Call browser_snapshot (if navigate worked)
    if results.get('browser_navigate'):
        try:
            result = await test_call_browser_snapshot()
            results['browser_snapshot'] = result is not None
        except Exception as e:
            results['browser_snapshot'] = False
            print(f"❌ Test 3 failed: {e}")
    
    # Test 4: Multiple clients
    try:
        success = await test_multiple_clients()
        results['multiple_clients'] = success
    except Exception as e:
        results['multiple_clients'] = False
        print(f"❌ Test 4 failed: {e}")
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

