#!/usr/bin/env python3
"""Check MCP integrations and selected tools"""
import asyncio
from app.db.database import get_db
from app.models.database import Integration
from sqlalchemy import select

async def check():
    async for db in get_db():
        result = await db.execute(
            select(Integration)
            .where(Integration.service_type == "mcp_server")
            .where(Integration.enabled == True)
        )
        integrations = result.scalars().all()
        
        print(f'\nFound {len(integrations)} enabled MCP integration(s)\n')
        
        if not integrations:
            print("❌ No enabled MCP integrations found!")
            print("   Please go to /integrations and connect an MCP server, then select some tools.")
            return
        
        for integration in integrations:
            metadata = integration.session_metadata or {}
            selected_tools = metadata.get("selected_tools", [])
            server_url = metadata.get("server_url", "")
            
            print(f"Integration: {integration.id}")
            print(f"  Server URL: {server_url}")
            print(f"  Selected tools: {len(selected_tools)}")
            
            if selected_tools:
                print(f"  Tools:")
                for tool in selected_tools[:10]:
                    print(f"    - {tool}")
                if len(selected_tools) > 10:
                    print(f"    ... and {len(selected_tools) - 10} more")
            else:
                print(f"  ⚠️  No tools selected!")
            print()
        
        break

if __name__ == '__main__':
    asyncio.run(check())

