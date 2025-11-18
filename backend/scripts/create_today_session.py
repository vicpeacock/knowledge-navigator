"""
Script per creare la sessione giornaliera per l'admin
"""
import asyncio
import sys
import os
from uuid import UUID

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db.database import AsyncSessionLocal
from app.models.database import User
from app.services.daily_session_manager import DailySessionManager
from app.core.dependencies import init_clients, get_memory_manager, get_ollama_client
from sqlalchemy import select
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_today_session():
    """Crea la sessione giornaliera per l'admin"""
    logger.info("📅 Creating today's session for admin...")
    
    async with AsyncSessionLocal() as db:
        # Trova l'utente admin - prova prima Admin@example.com, poi qualsiasi admin
        admin_result = await db.execute(
            select(User).where(User.email.ilike("admin@example.com")).limit(1)
        )
        admin = admin_result.scalar_one_or_none()
        
        if not admin:
            # Fallback: trova qualsiasi admin
            admin_result = await db.execute(
                select(User).where(User.role == "admin").limit(1)
            )
            admin = admin_result.scalar_one_or_none()
        
        if not admin:
            logger.error("❌ Nessun utente admin trovato")
            return
        
        logger.info(f"✅ Trovato admin: {admin.email} (ID: {admin.id}, role: {admin.role})")
        
        # Calcola la data di oggi nel timezone dell'utente
        from datetime import datetime
        from zoneinfo import ZoneInfo
        
        timezone_str = admin.timezone or "UTC"
        try:
            user_tz = ZoneInfo(timezone_str)
        except Exception as e:
            logger.warning(f"Invalid timezone '{timezone_str}', using UTC: {e}")
            user_tz = ZoneInfo("UTC")
        
        now = datetime.now(user_tz)
        today_date = now.strftime("%Y-%m-%d")
        
        logger.info(f"   Data di oggi (timezone {timezone_str}): {today_date}")
        
        # Verifica se esiste già una sessione per oggi
        from app.models.database import Session as SessionModel
        existing_session_result = await db.execute(
            select(SessionModel).where(
                SessionModel.tenant_id == admin.tenant_id,
                SessionModel.user_id == admin.id,
                SessionModel.status == "active",
                SessionModel.session_metadata["day"].astext == today_date,
            )
        )
        existing_session = existing_session_result.scalar_one_or_none()
        
        if existing_session:
            logger.info(f"✅ Sessione già esistente: {existing_session.id} ({existing_session.name})")
            return existing_session
        
        # Crea nuova sessione
        try:
            init_clients()
            memory_manager = get_memory_manager()
            ollama_client = get_ollama_client()
            
            daily_manager = DailySessionManager(
                db=db,
                memory_manager=memory_manager,
                ollama_client=ollama_client,
            )
            
            today_session, is_new = await daily_manager.get_or_create_today_session(
                user_id=admin.id,
                tenant_id=admin.tenant_id,
            )
            
            if is_new:
                logger.info(f"✅ Creata nuova sessione: {today_session.id} ({today_session.name})")
            else:
                logger.info(f"✅ Sessione già esistente: {today_session.id} ({today_session.name})")
            
            logger.info(f"   Status: {today_session.status}")
            logger.info(f"   Metadata: {today_session.session_metadata}")
            
            return today_session
        except Exception as e:
            logger.warning(f"⚠️  Errore con DailySessionManager, creo sessione direttamente: {e}")
            # Fallback: crea sessione direttamente
            session_name = f"Sessione {today_date}"
            new_session = SessionModel(
                tenant_id=admin.tenant_id,
                user_id=admin.id,
                name=session_name,
                title=f"Sessione {today_date}",
                description=f"Sessione giornaliera del {today_date}",
                status="active",
                session_metadata={
                    "day": today_date,
                    "is_daily_session": True,
                    "timezone": timezone_str,
                },
            )
            db.add(new_session)
            await db.commit()
            await db.refresh(new_session)
            logger.info(f"✅ Creata sessione direttamente: {new_session.id} ({new_session.name})")
            return new_session


async def main():
    """Esegue la creazione della sessione"""
    logger.info("=" * 60)
    logger.info("📅 Create Today's Session Script")
    logger.info("=" * 60)
    
    try:
        session = await create_today_session()
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ Sessione giornaliera creata/recuperata!")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"\n❌ Errore durante la creazione della sessione: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

