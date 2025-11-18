"""
Script per pulire tutte le sessioni tranne quella di oggi dell'admin
e pulire la memoria a lungo termine
"""
import asyncio
import sys
import os
from datetime import datetime
from uuid import UUID

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db.database import AsyncSessionLocal
from app.models.database import User, Session as SessionModel, Message as MessageModel
from app.services.daily_session_manager import DailySessionManager
from app.core.dependencies import init_clients, get_memory_manager, get_ollama_client
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def cleanup_sessions(keep_admin_today: bool = True):
    """Rimuove tutte le sessioni tranne quella di oggi dell'admin"""
    logger.info("🧹 Starting session cleanup...")
    
    init_clients()
    memory_manager = get_memory_manager()
    ollama_client = get_ollama_client()
    
    async with AsyncSessionLocal() as db:
        # Trova l'utente admin
        admin_result = await db.execute(
            select(User).where(User.role == "admin").limit(1)
        )
        admin = admin_result.scalar_one_or_none()
        
        if not admin:
            logger.error("❌ Nessun utente admin trovato")
            return
        
        logger.info(f"✅ Trovato admin: {admin.email} (ID: {admin.id})")
        
        # Ottieni la sessione di oggi dell'admin
        daily_manager = DailySessionManager(
            db=db,
            memory_manager=memory_manager,
            ollama_client=ollama_client,
        )
        
        today_session, _ = await daily_manager.get_or_create_today_session(
            user_id=admin.id,
            tenant_id=admin.tenant_id,
        )
        
        logger.info(f"✅ Sessione di oggi: {today_session.id} ({today_session.name})")
        
        # Conta tutte le sessioni prima della pulizia
        all_sessions_result = await db.execute(select(SessionModel))
        all_sessions = all_sessions_result.scalars().all()
        count_before = len(all_sessions)
        logger.info(f"📊 Sessioni totali prima della pulizia: {count_before}")
        
        # Rimuovi tutte le sessioni tranne quella di oggi dell'admin
        sessions_to_delete = [s for s in all_sessions if s.id != today_session.id]
        
        if sessions_to_delete:
            # Rimuovi prima le notifiche associate
            from app.models.database import Notification as NotificationModel
            for session in sessions_to_delete:
                notifications_result = await db.execute(
                    select(NotificationModel).where(NotificationModel.session_id == session.id)
                )
                notifications = notifications_result.scalars().all()
                for notification in notifications:
                    await db.delete(notification)
                if notifications:
                    logger.info(f"   Rimosse {len(notifications)} notifiche dalla sessione {session.id}")
            
            # Rimuovi i messaggi associati
            for session in sessions_to_delete:
                messages_result = await db.execute(
                    select(MessageModel).where(MessageModel.session_id == session.id)
                )
                messages = messages_result.scalars().all()
                for message in messages:
                    await db.delete(message)
                logger.info(f"   Rimossi {len(messages)} messaggi dalla sessione {session.id}")
            
            # Rimuovi le sessioni
            for session in sessions_to_delete:
                await db.delete(session)
            
            await db.commit()
            logger.info(f"✅ Rimosse {len(sessions_to_delete)} sessioni")
        else:
            logger.info("ℹ️  Nessuna sessione da rimuovere")
        
        # Verifica finale
        remaining_sessions_result = await db.execute(select(SessionModel))
        remaining_sessions = remaining_sessions_result.scalars().all()
        count_after = len(remaining_sessions)
        logger.info(f"📊 Sessioni rimanenti: {count_after}")
        
        if count_after == 1 and remaining_sessions[0].id == today_session.id:
            logger.info("✅ Pulizia sessioni completata correttamente")
        else:
            logger.warning(f"⚠️  Attenzione: rimangono {count_after} sessioni invece di 1")


async def cleanup_long_term_memory():
    """Pulisce tutta la memoria a lungo termine"""
    logger.info("🧹 Starting long-term memory cleanup...")
    
    from app.models.database import MemoryLong
    from app.core.config import settings
    import chromadb
    
    async with AsyncSessionLocal() as db:
        # Conta memorie prima della pulizia
        result = await db.execute(select(MemoryLong))
        count_before = len(result.scalars().all())
        logger.info(f"📊 Memorie long-term in PostgreSQL prima della pulizia: {count_before}")
        
        # Rimuovi tutte le memorie long-term da PostgreSQL
        await db.execute(delete(MemoryLong))
        await db.commit()
        logger.info("✅ Memorie long-term rimosse da PostgreSQL")
        
        # Verifica finale PostgreSQL
        result_after = await db.execute(select(MemoryLong))
        count_after = len(result_after.scalars().all())
        logger.info(f"📊 Memorie long-term in PostgreSQL dopo la pulizia: {count_after}")
    
    # Pulisci ChromaDB
    try:
        chroma_client = chromadb.HttpClient(
            host=settings.chromadb_host,
            port=settings.chromadb_port,
        )
        
        # Ottieni tutte le collections che iniziano con "long_term_memory"
        try:
            # Prova a ottenere la collection principale
            collection = chroma_client.get_collection(name="long_term_memory")
            
            count_before_chroma = collection.count()
            logger.info(f"📊 Documenti in ChromaDB prima della pulizia: {count_before_chroma}")
            
            if count_before_chroma > 0:
                all_data = collection.get()
                ids = all_data.get("ids", [])
                if ids:
                    collection.delete(ids=ids)
                    logger.info(f"✅ Rimossi {len(ids)} documenti da ChromaDB")
            
            count_after_chroma = collection.count()
            logger.info(f"📊 Documenti in ChromaDB dopo la pulizia: {count_after_chroma}")
        except Exception as e:
            logger.warning(f"⚠️  Collection 'long_term_memory' non trovata o vuota: {e}")
        
        # Pulisci anche le collections tenant-specific
        try:
            # Lista tutte le collections e trova quelle che iniziano con "long_term_memory_tenant_"
            all_collections = chroma_client.list_collections()
            for coll_info in all_collections:
                if coll_info.name.startswith("long_term_memory_tenant_"):
                    collection = chroma_client.get_collection(name=coll_info.name)
                    count = collection.count()
                    if count > 0:
                        all_data = collection.get()
                        ids = all_data.get("ids", [])
                        if ids:
                            collection.delete(ids=ids)
                            logger.info(f"✅ Rimossi {len(ids)} documenti da {coll_info.name}")
        except Exception as e:
            logger.warning(f"⚠️  Errore nella pulizia delle collections tenant-specific: {e}")
            
    except Exception as e:
        logger.error(f"❌ Errore nella connessione a ChromaDB: {e}")
    
    logger.info("✅ Pulizia memoria a lungo termine completata!")


async def main():
    """Esegue la pulizia completa"""
    logger.info("=" * 60)
    logger.info("🧹 Cleanup Script - Sessioni e Memoria")
    logger.info("=" * 60)
    
    try:
        await cleanup_sessions(keep_admin_today=True)
        await cleanup_long_term_memory()
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ Pulizia completata!")
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"\n❌ Errore durante la pulizia: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

