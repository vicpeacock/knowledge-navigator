#!/usr/bin/env python3
"""Script to check available tools and their descriptions"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.tool_manager import ToolManager
from app.db.database import AsyncSessionLocal
from app.models.database import Tenant
from sqlalchemy import select, text

async def check_tools():
    async with AsyncSessionLocal() as db:
        # Get first tenant (or use None for default)
        result = await db.execute(select(Tenant.id).limit(1))
        tenant_id = result.scalar_one_or_none()
        if not tenant_id:
            print("No tenant found, using None")
            tenant_id = None
        else:
            print(f"Using tenant: {tenant_id}")
        
        tool_manager = ToolManager(db=db, tenant_id=tenant_id)
        
        # Get base tools
        base_tools = tool_manager.get_base_tools()
        print(f"\n=== Base Tools ({len(base_tools)}) ===")
        for tool in base_tools:
            print(f"  - {tool.get('name')}: {tool.get('description', '')[:80]}")
        
        # Get MCP tools (without user filtering)
        mcp_tools = await tool_manager.get_mcp_tools(current_user=None, include_all=True)
        print(f"\n=== MCP Tools ({len(mcp_tools)}) ===")
        
        google_maps_tools = []
        for tool in mcp_tools:
            name = tool.get('name', '')
            desc = tool.get('description', '')
            if 'google' in name.lower() or 'maps' in name.lower() or 'geocode' in name.lower() or 'places' in name.lower():
                google_maps_tools.append(tool)
            print(f"  - {name}: {desc[:80]}")
        
        print(f"\n=== Google Maps Tools ({len(google_maps_tools)}) ===")
        for tool in google_maps_tools:
            print(f"  - {tool.get('name')}")
            print(f"    Description: {tool.get('description', '')[:200]}")
            print(f"    Parameters: {tool.get('parameters', {})}")
            print()
        
        # Get all available tools (with user filtering if user provided)
        all_tools = await tool_manager.get_available_tools(current_user=None)
        print(f"\n=== All Available Tools ({len(all_tools)}) ===")
        google_maps_available = [t for t in all_tools if 'google' in t.get('name', '').lower() or 'maps' in t.get('name', '').lower() or 'geocode' in t.get('name', '').lower() or 'places' in t.get('name', '').lower()]
        print(f"Google Maps tools in available list: {len(google_maps_available)}")
        for tool in google_maps_available:
            print(f"  - {tool.get('name')}: {tool.get('description', '')[:100]}")

if __name__ == "__main__":
    asyncio.run(check_tools())

