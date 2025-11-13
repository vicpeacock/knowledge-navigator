#!/usr/bin/env python3
"""
Script per pulire la memoria a lungo termine.
Rimuove tutte le memorie long-term da ChromaDB e PostgreSQL.

Uso: Assicurati di essere nell'ambiente virtuale:
    source backend/venv/bin/activate  # o il percorso del tuo venv
    python backend/scripts/clean_long_term_memory.py
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
import chromadb
from app.core.config import settings
from app.models.database import MemoryLong
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def clean_long_term_memory():
    """Pulisce tutta la memoria a lungo termine"""
    
    # 1. Connessione a PostgreSQL
    database_url = settings.database_url
    engine = create_async_engine(database_url, echo=False)
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session_maker() as db:
        # Conta memorie prima della pulizia
        result = await db.execute(select(MemoryLong))
        count_before = len(result.scalars().all())
        logger.info(f"📊 Memorie long-term in PostgreSQL prima della pulizia: {count_before}")
        
        # Rimuovi tutte le memorie long-term
        await db.execute(delete(MemoryLong))
        await db.commit()
        logger.info("✅ Memorie long-term rimosse da PostgreSQL")
    
    # 2. Connessione a ChromaDB
    try:
        chroma_client = chromadb.HttpClient(
            host=settings.chromadb_host,
            port=settings.chromadb_port,
        )
        
        # Ottieni la collection
        try:
            collection = chroma_client.get_collection(name="long_term_memory")
            
            # Conta documenti prima della pulizia
            count_before_chroma = collection.count()
            logger.info(f"📊 Documenti in ChromaDB prima della pulizia: {count_before_chroma}")
            
            # Ottieni tutti gli ID
            all_data = collection.get()
            ids = all_data.get("ids", [])
            
            if ids:
                # Rimuovi tutti i documenti
                collection.delete(ids=ids)
                logger.info(f"✅ Rimossi {len(ids)} documenti da ChromaDB")
            else:
                logger.info("ℹ️  Nessun documento da rimuovere da ChromaDB")
                
        except Exception as e:
            logger.warning(f"⚠️  Collection 'long_term_memory' non trovata o vuota: {e}")
            
    except Exception as e:
        logger.error(f"❌ Errore nella connessione a ChromaDB: {e}")
    
    # 3. Verifica finale
    async with async_session_maker() as db:
        result = await db.execute(select(MemoryLong))
        count_after = len(result.scalars().all())
        logger.info(f"📊 Memorie long-term in PostgreSQL dopo la pulizia: {count_after}")
    
    try:
        collection = chroma_client.get_collection(name="long_term_memory")
        count_after_chroma = collection.count()
        logger.info(f"📊 Documenti in ChromaDB dopo la pulizia: {count_after_chroma}")
    except:
        pass
    
    logger.info("✅ Pulizia completata!")
    await engine.dispose()


if __name__ == "__main__":
    print("⚠️  ATTENZIONE: Questo script rimuoverà TUTTA la memoria a lungo termine!")
    response = input("Sei sicuro di voler procedere? (scrivi 'SI' per confermare): ")
    
    if response.strip().upper() == "SI":
        asyncio.run(clean_long_term_memory())
    else:
        print("❌ Operazione annullata.")

