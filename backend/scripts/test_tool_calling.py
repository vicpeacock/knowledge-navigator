#!/usr/bin/env python3
"""Test script to verify tool calling functionality"""
import asyncio
import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.tool_manager import ToolManager
from app.core.ollama_client import OllamaClient
from app.db.database import AsyncSessionLocal
from app.models.database import Tenant, User
from app.models.schemas import ChatRequest
from sqlalchemy import select

async def test_tool_availability():
    """Test 1: Verify tools are available"""
    print("=" * 80)
    print("TEST 1: Tool Availability")
    print("=" * 80)
    
    async with AsyncSessionLocal() as db:
        # Get tenant
        result = await db.execute(select(Tenant.id).limit(1))
        tenant_id = result.scalar_one_or_none()
        
        tool_manager = ToolManager(db=db, tenant_id=tenant_id)
        
        # Get all tools
        all_tools = await tool_manager.get_available_tools(current_user=None)
        print(f"\n✅ Total tools available: {len(all_tools)}")
        
        # Check for Google Maps tools
        google_maps_tools = [t for t in all_tools if 'maps' in t.get('name', '').lower()]
        print(f"✅ Google Maps tools: {len(google_maps_tools)}")
        for tool in google_maps_tools:
            print(f"   - {tool.get('name')}: {tool.get('description', '')[:80]}")
        
        # Check for MCP tools
        mcp_tools = [t for t in all_tools if t.get('name', '').startswith('mcp_')]
        print(f"✅ MCP tools: {len(mcp_tools)}")
        
        return all_tools, google_maps_tools

async def test_tool_passing_to_ollama():
    """Test 2: Verify tools are passed correctly to Ollama"""
    print("\n" + "=" * 80)
    print("TEST 2: Tool Passing to Ollama")
    print("=" * 80)
    
    async with AsyncSessionLocal() as db:
        # Get tenant
        result = await db.execute(select(Tenant.id).limit(1))
        tenant_id = result.scalar_one_or_none()
        
        tool_manager = ToolManager(db=db, tenant_id=tenant_id)
        ollama = OllamaClient()
        
        # Get tools
        all_tools = await tool_manager.get_available_tools(current_user=None)
        tools_description = await tool_manager.get_tools_system_prompt()
        
        print(f"\n✅ Tools to pass: {len(all_tools)}")
        print(f"✅ Tools description length: {len(tools_description)}")
        
        # Test with a simple prompt that should trigger tool calling
        test_prompt = "Cerca ristoranti a Roma"
        
        print(f"\n📝 Test prompt: '{test_prompt}'")
        print(f"📝 Passing {len(all_tools)} tools to Ollama...")
        
        try:
            # Convert tools to Ollama format
            ollama_tools = []
            for tool in all_tools:
                ollama_tool = {
                    "type": "function",
                    "function": {
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {}),
                    }
                }
                ollama_tools.append(ollama_tool)
            
            print(f"✅ Converted {len(ollama_tools)} tools to Ollama format")
            
            # Check if Google Maps tools are in the list
            maps_tools_in_list = [t for t in ollama_tools if 'maps' in t.get('function', {}).get('name', '').lower()]
            print(f"✅ Google Maps tools in Ollama format: {len(maps_tools_in_list)}")
            for tool in maps_tools_in_list[:3]:  # Show first 3
                name = tool.get('function', {}).get('name', '')
                desc = tool.get('function', {}).get('description', '')[:60]
                print(f"   - {name}: {desc}...")
            
            # Make a test call to Ollama
            print(f"\n📞 Calling Ollama with tools...")
            response = await ollama.generate_with_context(
                prompt=test_prompt,
                session_context=[],
                retrieved_memory=None,
                tools=all_tools,
                tools_description=tools_description,
                return_raw=True,
            )
            
            print(f"✅ Ollama response received")
            
            # Check if Ollama returned tool calls
            if isinstance(response, dict):
                tool_calls = response.get("_parsed_tool_calls", [])
                raw_tool_calls = response.get("_raw_tool_calls", [])
                content = response.get("content", "")
                
                print(f"\n📊 Response analysis:")
                print(f"   - Content length: {len(content)}")
                print(f"   - Parsed tool calls: {len(tool_calls)}")
                print(f"   - Raw tool calls: {len(raw_tool_calls)}")
                
                if tool_calls:
                    print(f"\n✅ Tool calls detected!")
                    for i, tc in enumerate(tool_calls, 1):
                        print(f"   {i}. Tool: {tc.get('name')}")
                        print(f"      Parameters: {tc.get('parameters', {})}")
                else:
                    print(f"\n⚠️  No tool calls detected in response")
                    print(f"   Content: {content[:200]}...")
                    
                    # Check if content mentions tools
                    if 'tool' in content.lower() or 'maps' in content.lower():
                        print(f"   ⚠️  Content mentions tools/maps but no tool calls were made")
            else:
                print(f"⚠️  Unexpected response format: {type(response)}")
                print(f"   Response: {str(response)[:200]}...")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

async def test_tool_execution():
    """Test 3: Verify tool execution works"""
    print("\n" + "=" * 80)
    print("TEST 3: Tool Execution")
    print("=" * 80)
    
    async with AsyncSessionLocal() as db:
        # Get tenant
        result = await db.execute(select(Tenant.id).limit(1))
        tenant_id = result.scalar_one_or_none()
        
        tool_manager = ToolManager(db=db, tenant_id=tenant_id)
        
        # Test with a Google Maps tool
        test_tool_name = "mcp_maps_search_places"
        test_parameters = {
            "query": "ristoranti Roma",
            "location": "Rome, Italy"
        }
        
        print(f"\n📝 Testing tool execution:")
        print(f"   Tool: {test_tool_name}")
        print(f"   Parameters: {test_parameters}")
        
        try:
            # Check if tool exists
            all_tools = await tool_manager.get_available_tools(current_user=None)
            tool_exists = any(t.get('name') == test_tool_name for t in all_tools)
            
            if not tool_exists:
                print(f"❌ Tool {test_tool_name} not found in available tools")
                print(f"   Available tool names: {[t.get('name') for t in all_tools[:10]]}...")
                return
            
            print(f"✅ Tool {test_tool_name} found")
            
            # Try to execute the tool
            print(f"\n🔧 Executing tool...")
            result = await tool_manager.execute_tool(
                test_tool_name,
                test_parameters,
                db=db,
                session_id=None,
                current_user=None
            )
            
            print(f"✅ Tool execution completed")
            print(f"   Result type: {type(result)}")
            if isinstance(result, dict):
                if "error" in result:
                    print(f"   ❌ Error: {result.get('error')}")
                else:
                    print(f"   ✅ Success: {json.dumps(result, indent=2, default=str)[:500]}")
            else:
                print(f"   Result: {str(result)[:200]}...")
                
        except Exception as e:
            print(f"❌ Error executing tool: {e}")
            import traceback
            traceback.print_exc()

async def test_user_preferences():
    """Test 4: Check if user preferences are filtering tools"""
    print("\n" + "=" * 80)
    print("TEST 4: User Preferences")
    print("=" * 80)
    
    async with AsyncSessionLocal() as db:
        # Get tenant
        result = await db.execute(select(Tenant.id).limit(1))
        tenant_id = result.scalar_one_or_none()
        
        # Get first user
        user_result = await db.execute(select(User).limit(1))
        user = user_result.scalar_one_or_none()
        
        if not user:
            print("⚠️  No user found, skipping user preference test")
            return
        
        print(f"\n👤 Testing with user: {user.email}")
        
        tool_manager = ToolManager(db=db, tenant_id=tenant_id)
        
        # Get tools without user
        tools_no_user = await tool_manager.get_available_tools(current_user=None)
        print(f"✅ Tools without user filter: {len(tools_no_user)}")
        
        # Get tools with user
        tools_with_user = await tool_manager.get_available_tools(current_user=user)
        print(f"✅ Tools with user filter: {len(tools_with_user)}")
        
        # Check user metadata
        user_metadata = user.user_metadata or {}
        enabled_tools = user_metadata.get("enabled_tools")
        print(f"\n📊 User preferences:")
        print(f"   enabled_tools: {enabled_tools}")
        print(f"   Type: {type(enabled_tools)}")
        
        if enabled_tools is None:
            print(f"   ℹ️  No preferences set - all tools should be enabled")
        elif isinstance(enabled_tools, list):
            print(f"   📋 {len(enabled_tools)} tools enabled")
            maps_enabled = [t for t in enabled_tools if 'maps' in t.lower()]
            print(f"   🗺️  Google Maps tools enabled: {len(maps_enabled)}")
            if maps_enabled:
                print(f"      {', '.join(maps_enabled)}")
            else:
                print(f"   ⚠️  No Google Maps tools enabled!")
        
        # Check which tools are filtered out
        filtered_out = [t for t in tools_no_user if t not in tools_with_user]
        if filtered_out:
            print(f"\n⚠️  {len(filtered_out)} tools filtered out by user preferences")
            for tool in filtered_out[:5]:
                print(f"   - {tool.get('name')}")

async def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("TOOL CALLING TEST SUITE")
    print("=" * 80)
    
    try:
        # Test 1: Tool availability
        all_tools, google_maps_tools = await test_tool_availability()
        
        if len(google_maps_tools) == 0:
            print("\n❌ CRITICAL: No Google Maps tools found!")
            return
        
        # Test 2: Tool passing to Ollama
        await test_tool_passing_to_ollama()
        
        # Test 3: Tool execution
        await test_tool_execution()
        
        # Test 4: User preferences
        await test_user_preferences()
        
        print("\n" + "=" * 80)
        print("TEST SUITE COMPLETED")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

