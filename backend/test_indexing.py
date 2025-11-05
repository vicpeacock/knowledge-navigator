"""
Script di test per verificare l'indicizzazione dei contenuti web
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import settings
from app.core.memory_manager import MemoryManager
from app.services.web_indexer import WebIndexer
from app.services.email_indexer import EmailIndexer
from uuid import UUID
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_web_indexing():
    """Test dell'indicizzazione contenuti web"""
    print("\n" + "="*60)
    print("TEST INDICIZZAZIONE CONTENUTI WEB")
    print("="*60 + "\n")
    
    # Setup database
    engine = create_async_engine(
        settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
        echo=False
    )
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # Test session ID (usa un UUID valido)
    test_session_id = UUID("00000000-0000-0000-0000-000000000001")
    
    async with async_session() as db:
        # Initialize memory manager
        from app.core.dependencies import init_clients
        init_clients()
        memory_manager = MemoryManager()
        
        # Initialize web indexer
        web_indexer = WebIndexer(memory_manager)
        
        # Test 1: Indicizzazione risultati web_search
        print("📊 Test 1: Indicizzazione risultati web_search")
        print("-" * 60)
        
        search_query = "Python async programming"
        mock_search_results = [
            {
                "title": "Python AsyncIO Tutorial",
                "url": "https://example.com/python-asyncio",
                "content": "AsyncIO is a library for writing concurrent code using async/await syntax. It's perfect for I/O-bound and high-level structured network code."
            },
            {
                "title": "Understanding Python Coroutines",
                "url": "https://example.com/python-coroutines",
                "content": "Coroutines are functions that can be paused and resumed. They're the building blocks of async programming in Python."
            }
        ]
        
        try:
            index_stats = await web_indexer.index_web_search_results(
                db=db,
                search_query=search_query,
                results=mock_search_results,
                session_id=test_session_id,
            )
            print(f"✅ Indicizzati {index_stats.get('indexed', 0)} risultati")
            print(f"   Query: {search_query}")
            print(f"   Risultati: {len(mock_search_results)}")
        except Exception as e:
            print(f"❌ Errore: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 2: Indicizzazione web_fetch
        print("\n📄 Test 2: Indicizzazione contenuto web_fetch")
        print("-" * 60)
        
        test_url = "https://example.com/test-page"
        mock_fetch_result = {
            "title": "Test Page",
            "content": "This is a test page content for indexing. It contains useful information about web scraping and indexing.",
            "links": ["https://example.com/link1", "https://example.com/link2"]
        }
        
        try:
            indexed = await web_indexer.index_web_fetch_result(
                db=db,
                url=test_url,
                result=mock_fetch_result,
                session_id=test_session_id,
            )
            if indexed:
                print(f"✅ Contenuto indicizzato per URL: {test_url}")
            else:
                print(f"⚠️ Contenuto non indicizzato (troppo corto o altro motivo)")
        except Exception as e:
            print(f"❌ Errore: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 3: Verifica recupero dalla memoria
        print("\n🔍 Test 3: Verifica recupero dalla memoria")
        print("-" * 60)
        
        try:
            # Cerca contenuti relativi alla query di test
            retrieved = await memory_manager.retrieve_long_term_memory(
                query="Python async programming asyncIO",
                n_results=5,
            )
            print(f"✅ Recuperati {len(retrieved)} contenuti dalla memoria long-term")
            for i, content in enumerate(retrieved[:3], 1):
                preview = content[:100].replace('\n', ' ')
                print(f"   {i}. {preview}...")
        except Exception as e:
            print(f"❌ Errore nel recupero: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 4: Verifica database PostgreSQL
        print("\n💾 Test 4: Verifica database PostgreSQL")
        print("-" * 60)
        
        try:
            from app.models.database import MemoryLong
            from sqlalchemy import select, func
            
            # Conta i record in memory_long
            count_result = await db.execute(
                select(func.count(MemoryLong.id))
            )
            total_count = count_result.scalar()
            print(f"✅ Record totali in memory_long: {total_count}")
            
            # Verifica record per questa sessione
            session_count_result = await db.execute(
                select(func.count(MemoryLong.id))
                .where(MemoryLong.learned_from_sessions.contains([str(test_session_id)]))
            )
            session_count = session_count_result.scalar()
            print(f"✅ Record per questa sessione di test: {session_count}")
            
            # Mostra ultimi 3 record
            recent_result = await db.execute(
                select(MemoryLong)
                .order_by(MemoryLong.id.desc())
                .limit(3)
            )
            recent_records = recent_result.scalars().all()
            print(f"\n📋 Ultimi 3 record indicizzati:")
            for i, record in enumerate(recent_records, 1):
                preview = record.content[:80].replace('\n', ' ')
                print(f"   {i}. Importance: {record.importance_score:.2f}")
                print(f"      Content: {preview}...")
                print(f"      Sessions: {len(record.learned_from_sessions)}")
        except Exception as e:
            print(f"❌ Errore nella verifica database: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "="*60)
        print("TEST COMPLETATO")
        print("="*60 + "\n")
    
    await engine.dispose()


async def test_email_indexing():
    """Test dell'indicizzazione email"""
    print("\n" + "="*60)
    print("TEST INDICIZZAZIONE EMAIL")
    print("="*60 + "\n")
    
    # Setup database
    engine = create_async_engine(
        settings.database_url.replace("postgresql://", "postgresql+asyncpg://"),
        echo=False
    )
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    test_session_id = UUID("00000000-0000-0000-0000-000000000001")
    
    async with async_session() as db:
        from app.core.dependencies import init_clients
        init_clients()
        memory_manager = MemoryManager()
        
        email_indexer = EmailIndexer(memory_manager)
        
        # Mock email data
        mock_emails = [
            {
                "id": "test-email-1",
                "from": "test@example.com",
                "subject": "Test Email 1",
                "body": "This is a test email body with important information about the project.",
                "snippet": "Test email snippet",
                "unread": True,
            },
            {
                "id": "test-email-2",
                "from": "another@example.com",
                "subject": "Test Email 2",
                "body": "Another test email with different content.",
                "snippet": "Another snippet",
                "unread": False,
            }
        ]
        
        print("📧 Test: Indicizzazione email")
        print("-" * 60)
        
        try:
            index_stats = await email_indexer.index_emails(
                db=db,
                emails=mock_emails,
                session_id=test_session_id,
                auto_index=True,
            )
            print(f"✅ Indicizzate {index_stats.get('indexed', 0)} email su {len(mock_emails)}")
            print(f"   Totali: {index_stats.get('total', 0)}")
            print(f"   Scartate: {index_stats.get('skipped', 0)}")
        except Exception as e:
            print(f"❌ Errore: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "="*60)
        print("TEST EMAIL COMPLETATO")
        print("="*60 + "\n")
    
    await engine.dispose()


if __name__ == "__main__":
    print("\n🧪 Script di Test per Indicizzazione")
    print("="*60)
    
    # Test web indexing
    asyncio.run(test_web_indexing())
    
    # Test email indexing
    asyncio.run(test_email_indexing())
    
    print("\n✅ Tutti i test completati!\n")

