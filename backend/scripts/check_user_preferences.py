#!/usr/bin/env python3
"""Script to check user tool preferences"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import AsyncSessionLocal
from app.models.database import User
from sqlalchemy import select

async def check_preferences():
    async with AsyncSessionLocal() as db:
        # Get all users
        result = await db.execute(select(User))
        users = result.scalars().all()
        
        print(f"Found {len(users)} users:")
        print()
        
        for user in users:
            print(f"User: {user.email}")
            print(f"  ID: {user.id}")
            user_metadata = user.user_metadata or {}
            enabled_tools = user_metadata.get("enabled_tools")
            print(f"  enabled_tools: {enabled_tools}")
            print(f"  Type: {type(enabled_tools)}")
            if isinstance(enabled_tools, list):
                print(f"  Count: {len(enabled_tools)}")
                if enabled_tools:
                    print(f"  Tools: {enabled_tools[:10]}{'...' if len(enabled_tools) > 10 else ''}")
                    if "web_search" in enabled_tools:
                        print(f"  ⚠️  web_search is ENABLED")
                    else:
                        print(f"  ✅ web_search is DISABLED")
                else:
                    print(f"  ⚠️  Empty list - all tools disabled")
            elif enabled_tools is None:
                print(f"  ℹ️  None - all tools enabled by default")
            print()

if __name__ == "__main__":
    asyncio.run(check_preferences())

