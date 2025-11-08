"""
Script semplice per verificare lo stato dell'indicizzazione
Controlla i record in memory_long e ChromaDB
"""
import asyncio
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, func
from app.models.database import MemoryLong, Session as SessionModel
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

async def check_indexing_status():
    """Verifica lo stato dell'indicizzazione nel database"""
    try:
        
        # Setup database
        engine = create_async_engine(
            settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
            echo=False
        )
        async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        async with async_session() as db:
            # Conta record in memory_long
            count_result = await db.execute(
                select(func.count(MemoryLong.id))
            )
            total_count = count_result.scalar()
            
            print(f"\n📊 STATO INDICIZZAZIONE")
            print("="*60)
            print(f"✅ Record totali in memory_long: {total_count}")
            
            # Carica tutti i record (anche se sono 0)
            all_result = await db.execute(
                select(MemoryLong)
                .order_by(MemoryLong.id.desc())
            )
            all_records = all_result.scalars().all()
            
            if total_count > 0:
                
                print(f"\n📋 Tutti i {len(all_records)} record indicizzati:")
                print("-" * 60)
                
                # Raggruppa per sessione
                from collections import defaultdict
                by_session = defaultdict(list)
                
                for record in all_records:
                    for session_id_str in record.learned_from_sessions:
                        by_session[session_id_str].append(record)
                
                # Mostra statistiche per sessione
                print(f"\n📊 Record per sessione:")
                for session_id_str, records in by_session.items():
                    try:
                        session_uuid = UUID(session_id_str)
                        session_result = await db.execute(
                            select(SessionModel).where(SessionModel.id == session_uuid)
                        )
                        session = session_result.scalar_one_or_none()
                        session_name = session.name if session else "Session not found"
                        session_date = session.created_at.strftime("%Y-%m-%d %H:%M:%S") if session and session.created_at else "Unknown"
                    except:
                        session_name = "Unknown"
                        session_date = "Unknown"
                    
                    print(f"   Session {session_id_str[:8]}... ({session_name}) - {len(records)} record")
                    print(f"      Data: {session_date}")
                
                # Mostra dettagli degli ultimi 10 record
                print(f"\n📋 Dettagli ultimi 10 record:")
                for i, record in enumerate(all_records[:10], 1):
                    preview = record.content[:80].replace('\n', ' ')
                    print(f"\n   {i}. ID: {record.id}")
                    print(f"      Importance: {record.importance_score:.2f}")
                    print(f"      Embedding ID: {record.embedding_id}")
                    print(f"      Content: {preview}...")
                    print(f"      Sessions: {record.learned_from_sessions}")
                    
                    # Identifica tipo di contenuto
                    if "Web Search Result" in record.content:
                        print(f"      Tipo: Web Search")
                    elif "Web Page Snapshot" in record.content or "Web Fetch" in record.content:
                        print(f"      Tipo: Web Page")
                    elif "Email" in record.content or "From:" in record.content:
                        print(f"      Tipo: Email")
                    else:
                        print(f"      Tipo: Unknown")
            else:
                print("\n⚠️  Nessun contenuto indicizzato ancora.")
                print("   Prova a fare una ricerca web dalla chat per testare l'indicizzazione.")
            
            # Cerca sessioni con data "11/4/2025" o simile
            print(f"\n🔍 Cerca sessioni del 11/4/2025:")
            print("-" * 60)
            from datetime import datetime, timezone
            date_start = datetime(2025, 11, 4, 0, 0, 0, tzinfo=timezone.utc)
            date_end = datetime(2025, 11, 5, 0, 0, 0, tzinfo=timezone.utc)
            sessions_result = await db.execute(
                select(SessionModel)
                .where(SessionModel.created_at >= date_start)
                .where(SessionModel.created_at < date_end)
                .order_by(SessionModel.created_at.desc())
            )
            sessions_11_4 = sessions_result.scalars().all()
            
            if sessions_11_4:
                print(f"✅ Trovate {len(sessions_11_4)} sessioni del 11/4/2025:")
                for s in sessions_11_4:
                    print(f"   - {s.id}")
                    print(f"     Nome: {s.name}")
                    print(f"     Creata: {s.created_at}")
                    
                    # Conta record per questa sessione
                    session_records = [r for r in all_records if str(s.id) in r.learned_from_sessions]
                    print(f"     Record indicizzati: {len(session_records)}")
            else:
                print("⚠️  Nessuna sessione trovata per quella data")
            
            print("\n" + "="*60)
        
        await engine.dispose()
        
    except Exception as e:
        print(f"\n❌ Errore: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Import AsyncSession qui per evitare errori se non disponibile
    try:
        asyncio.run(check_indexing_status())
    except ImportError:
        print("\n⚠️  SQLAlchemy non disponibile. Attiva l'ambiente virtuale prima.")
        print("   Oppure usa il test dalla chat (vedi TEST_INDEXING.md)")

