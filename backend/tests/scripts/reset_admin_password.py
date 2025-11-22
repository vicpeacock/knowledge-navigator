#!/usr/bin/env python3
"""
Script per reimpostare la password dell'admin a 'admin123'
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import settings
from app.models.database import User
from app.core.auth import hash_password
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def reset_admin_password():
    """Reimposta la password dell'admin a 'admin123'"""
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.email.ilike('admin@example.com'))
        )
        user = result.scalar_one_or_none()
        
        if not user:
            logger.error("❌ Utente admin@example.com non trovato")
            return False
        
        # Reset password to the correct one
        new_password = "AdminPassword123!"
        user.password_hash = hash_password(new_password)
        await session.commit()
        
        logger.info(f"✅ Password reimpostata per {user.email}")
        logger.info(f"   Password: {new_password}")
        return True
    
    await engine.dispose()


if __name__ == "__main__":
    success = asyncio.run(reset_admin_password())
    sys.exit(0 if success else 1)

