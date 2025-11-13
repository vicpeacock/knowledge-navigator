#!/usr/bin/env python3
"""
Script per pulire contraddizioni e notifiche correlate.
Rimuove:
- Tutte le notifiche di tipo "contradiction" dal database
- Tutti i task di tipo "resolve_contradiction" dalla coda in-memory
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Change to backend directory to ensure relative imports work
import os
os.chdir(backend_dir)

# Fix NumPy 2.0 compatibility for ChromaDB (must be before chromadb import)
import numpy as np
if not hasattr(np, "float_"):
    np.float_ = np.float64  # type: ignore[attr-defined]
if not hasattr(np, "int_"):
    np.int_ = np.int64  # type: ignore[attr-defined]
if not hasattr(np, "uint"):
    np.uint = np.uint64  # type: ignore[attr-defined]

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings
from app.models.database import Notification as NotificationModel
from app.services.task_queue import TaskQueue, TaskStatus
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def clean_contradictions():
    """Pulisce contraddizioni e notifiche correlate"""
    
    # 1. Connessione a PostgreSQL
    database_url = settings.database_url
    engine = create_async_engine(database_url, echo=False)
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session_maker() as db:
        # Conta notifiche prima della pulizia
        result = await db.execute(
            select(NotificationModel).where(NotificationModel.type == "contradiction")
        )
        count_before = len(result.scalars().all())
        logger.info(f"📊 Notifiche di contraddizione in database prima della pulizia: {count_before}")
        
        # Rimuovi tutte le notifiche di tipo "contradiction"
        await db.execute(
            delete(NotificationModel).where(NotificationModel.type == "contradiction")
        )
        await db.commit()
        logger.info("✅ Notifiche di contraddizione rimosse dal database")
    
    # 2. Pulisci task dalla coda in-memory
    try:
        from app.core.dependencies import get_task_queue
        task_queue = get_task_queue()
        
        if task_queue:
            # Ottieni tutte le sessioni
            all_sessions = list(task_queue._tasks.keys())
            total_tasks_removed = 0
            
            for session_id in all_sessions:
                # Trova tutti i task di tipo "resolve_contradiction"
                # _tasks è un Dict[UUID, Dict[str, Task]]
                session_tasks_dict = task_queue._tasks.get(session_id, {})
                contradiction_task_ids = [
                    task_id for task_id, task in session_tasks_dict.items()
                    if task.type == "resolve_contradiction"
                ]
                
                if contradiction_task_ids:
                    logger.info(
                        f"📋 Trovati {len(contradiction_task_ids)} task di contraddizione per sessione {session_id}"
                    )
                    # Rimuovi i task dalla coda
                    for task_id in contradiction_task_ids:
                        try:
                            # Rimuovi il task dal dizionario
                            if session_id in task_queue._tasks and task_id in task_queue._tasks[session_id]:
                                del task_queue._tasks[session_id][task_id]
                                total_tasks_removed += 1
                                logger.debug(f"  ✅ Rimosso task {task_id}")
                        except Exception as e:
                            logger.warning(f"  ⚠️  Errore rimuovendo task {task_id}: {e}")
                    
                    # Rimuovi la sessione se non ha più task
                    if session_id in task_queue._tasks and len(task_queue._tasks[session_id]) == 0:
                        del task_queue._tasks[session_id]
                        logger.debug(f"  🗑️  Rimossa sessione vuota {session_id}")
            
            logger.info(f"✅ Rimossi {total_tasks_removed} task di contraddizione dalla coda in-memory")
        else:
            logger.warning("⚠️  TaskQueue non disponibile (probabilmente backend non avviato)")
            
    except Exception as e:
        logger.error(f"❌ Errore nella pulizia della coda task: {e}")
    
    # 3. Verifica finale
    async with async_session_maker() as db:
        result = await db.execute(
            select(NotificationModel).where(NotificationModel.type == "contradiction")
        )
        count_after = len(result.scalars().all())
        logger.info(f"📊 Notifiche di contraddizione in database dopo la pulizia: {count_after}")
    
    logger.info("✅ Pulizia contraddizioni completata!")
    await engine.dispose()


if __name__ == "__main__":
    print("⚠️  ATTENZIONE: Questo script rimuoverà TUTTE le notifiche di contraddizione e i task correlati!")
    response = input("Sei sicuro di voler procedere? (scrivi 'SI' per confermare): ")
    
    if response.strip().upper() == "SI":
        asyncio.run(clean_contradictions())
    else:
        print("❌ Operazione annullata.")

