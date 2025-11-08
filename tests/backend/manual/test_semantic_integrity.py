"""
Test script for semantic integrity checker
Simulates adding new knowledge that contradicts existing memories
"""
import asyncio
from uuid import uuid4
import pytest
from app.db.database import AsyncSessionLocal
from app.core.memory_manager import MemoryManager
from app.services.background_agent import BackgroundAgent
from app.services.notification_service import NotificationService
from app.core.dependencies import get_ollama_background_client

pytestmark = pytest.mark.skip(reason="Test di integrazione sull'integrità semantica: eseguirlo manualmente")

async def test_contradiction():
    """Test contradiction detection"""
    async with AsyncSessionLocal() as db:
        memory = MemoryManager()
        session_id = uuid4()
        
        print("🧪 Testing Semantic Integrity Checker\n")
        print("=" * 60)
        
        # Simulate new knowledge that contradicts existing memory
        # Existing: "Data di nascita: 12 luglio 1966"
        # New: "Sono nato il 20 agosto 1966"
        new_knowledge = {
            "type": "personal_info",
            "content": "Sono nato il 20 agosto 1966",
            "importance": 0.9,
        }
        
        print(f"\n📝 Nuova conoscenza da indicizzare:")
        print(f"   Tipo: {new_knowledge['type']}")
        print(f"   Contenuto: {new_knowledge['content']}")
        print(f"   Importanza: {new_knowledge['importance']}")
        
        # Process with BackgroundAgent
        print(f"\n🔍 Processando con BackgroundAgent...")
        agent = BackgroundAgent(
            memory_manager=memory,
            db=db,
            ollama_client=None,  # Will use background client
        )
        
        await agent.process_new_knowledge(
            knowledge_item=new_knowledge,
            session_id=session_id,
        )
        
        # Check for notifications
        notification_service = NotificationService(db)
        notifications = await notification_service.get_pending_notifications(
            session_id=session_id,
            read=False,
        )
        
        print(f"\n📬 Notifiche create: {len(notifications)}")
        
        if notifications:
            for i, notif in enumerate(notifications, 1):
                print(f"\n   Notifica {i}:")
                print(f"   - Tipo: {notif['type']}")
                print(f"   - Urgenza: {notif['urgency']}")
                print(f"   - ID: {notif['id']}")
                
                if notif['type'] == 'contradiction':
                    content = notif['content']
                    contradictions = content.get('contradictions', [])
                    print(f"   - Contraddizioni trovate: {len(contradictions)}")
                    
                    for j, contr in enumerate(contradictions, 1):
                        print(f"\n     Contraddizione {j}:")
                        print(f"     - Confidenza: {contr.get('confidence', 0):.2f}")
                        print(f"     - Nuova memoria: {contr.get('new_memory', '')}")
                        print(f"     - Memoria esistente: {contr.get('existing_memory', '')[:100]}...")
                        print(f"     - Spiegazione: {contr.get('explanation', '')[:150]}...")
        else:
            print("\n   ⚠️  Nessuna notifica creata (potrebbe non aver rilevato contraddizioni)")
        
        print("\n" + "=" * 60)
        print("✅ Test completato")

if __name__ == "__main__":
    asyncio.run(test_contradiction())

