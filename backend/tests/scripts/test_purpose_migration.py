#!/usr/bin/env python3
"""
Test script per verificare la migration del campo purpose nelle integrazioni.
"""
import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from app.db.database import get_db, Base
from app.models.database import Integration, User, Tenant
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_purpose_migration():
    """Test che tutte le integrazioni abbiano il campo purpose impostato correttamente"""
    engine = create_async_engine(settings.database_url, echo=False)
    
    async with engine.begin() as conn:
        # Check if purpose column exists
        result = await conn.execute(
            text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'integrations' AND column_name = 'purpose'
            """)
        )
        column_exists = result.scalar() is not None
        
        if not column_exists:
            logger.error("❌ Campo 'purpose' non trovato nella tabella integrations!")
            logger.error("   Esegui la migration: alembic upgrade head")
            return False
        
        logger.info("✅ Campo 'purpose' presente nella tabella integrations")
        
        # Check that all integrations have purpose set
        result = await conn.execute(
            text("SELECT COUNT(*) FROM integrations WHERE purpose IS NULL")
        )
        null_count = result.scalar()
        
        if null_count > 0:
            logger.error(f"❌ Trovate {null_count} integrazioni senza purpose!")
            return False
        
        logger.info("✅ Tutte le integrazioni hanno il campo purpose impostato")
        
        # Check purpose values distribution
        result = await conn.execute(
            text("""
                SELECT purpose, COUNT(*) as count
                FROM integrations
                GROUP BY purpose
                ORDER BY count DESC
            """)
        )
        purpose_distribution = result.fetchall()
        
        logger.info("\n📊 Distribuzione purpose:")
        for purpose, count in purpose_distribution:
            logger.info(f"   {purpose}: {count}")
        
        # Verify constraints: user_* should have user_id, service_* should have user_id = NULL
        result = await conn.execute(
            text("""
                SELECT COUNT(*) 
                FROM integrations 
                WHERE purpose LIKE 'user_%' AND user_id IS NULL
            """)
        )
        invalid_user_integrations = result.scalar()
        
        if invalid_user_integrations > 0:
            logger.error(f"❌ Trovate {invalid_user_integrations} integrazioni user_* senza user_id!")
            return False
        
        logger.info("✅ Tutte le integrazioni user_* hanno user_id impostato")
        
        result = await conn.execute(
            text("""
                SELECT COUNT(*) 
                FROM integrations 
                WHERE purpose LIKE 'service_%' AND user_id IS NOT NULL
            """)
        )
        invalid_service_integrations = result.scalar()
        
        if invalid_service_integrations > 0:
            logger.error(f"❌ Trovate {invalid_service_integrations} integrazioni service_* con user_id!")
            return False
        
        logger.info("✅ Tutte le integrazioni service_* hanno user_id = NULL")
        
        # Check indexes
        result = await conn.execute(
            text("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE tablename = 'integrations' 
                AND indexname LIKE '%purpose%'
            """)
        )
        indexes = [row[0] for row in result.fetchall()]
        
        if 'ix_integrations_purpose' not in indexes:
            logger.warning("⚠️  Indice ix_integrations_purpose non trovato")
        else:
            logger.info("✅ Indice ix_integrations_purpose presente")
        
        if 'ix_integrations_tenant_purpose_enabled' not in indexes:
            logger.warning("⚠️  Indice ix_integrations_tenant_purpose_enabled non trovato")
        else:
            logger.info("✅ Indice ix_integrations_tenant_purpose_enabled presente")
    
    await engine.dispose()
    return True


async def main():
    """Main test function"""
    logger.info("🧪 Test migration campo purpose\n")
    
    success = await test_purpose_migration()
    
    if success:
        logger.info("\n✅ Tutti i test della migration sono passati!")
        return 0
    else:
        logger.error("\n❌ Alcuni test della migration sono falliti!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

