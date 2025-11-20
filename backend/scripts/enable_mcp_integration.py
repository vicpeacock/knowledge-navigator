#!/usr/bin/env python3
"""Script per abilitare un'integrazione MCP"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update
from app.models.database import Integration
from app.core.config import settings
from uuid import UUID

async def enable_mcp_integration(integration_id: str):
    """Abilita un'integrazione MCP"""
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Find integration
        result = await session.execute(
            select(Integration)
            .where(Integration.id == UUID(integration_id))
            .where(Integration.service_type == "mcp_server")
        )
        integration = result.scalar_one_or_none()
        
        if not integration:
            print(f"❌ Integrazione MCP {integration_id} non trovata")
            return False
        
        print(f"📋 Integrazione trovata: {integration.id}")
        print(f"   Nome: {integration.session_metadata.get('name', 'N/A') if integration.session_metadata else 'N/A'}")
        print(f"   Server URL: {integration.session_metadata.get('server_url', 'N/A') if integration.session_metadata else 'N/A'}")
        print(f"   Enabled: {integration.enabled}")
        
        if integration.enabled:
            print(f"✅ Integrazione già abilitata")
            return True
        
        # Enable integration
        await session.execute(
            update(Integration)
            .where(Integration.id == UUID(integration_id))
            .values(enabled=True)
        )
        await session.commit()
        
        print(f"✅ Integrazione {integration_id} abilitata con successo")
        return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python enable_mcp_integration.py <integration_id>")
        print("Example: python enable_mcp_integration.py 60d18a65-b29f-49cf-a066-40c6c00640ed")
        sys.exit(1)
    
    integration_id = sys.argv[1]
    asyncio.run(enable_mcp_integration(integration_id))

