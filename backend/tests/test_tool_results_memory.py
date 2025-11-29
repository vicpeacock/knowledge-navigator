#!/usr/bin/env python3
"""
Test per verificare che i tool_results vengano salvati e recuperati correttamente
dalla memoria a breve termine per permettere chiamate sequenziali di tool.
"""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.core.config import settings
from app.core.memory_manager import MemoryManager
from app.models.database import Session as SessionModel, User, Tenant
from app.models.schemas import ChatRequest
from app.agents import run_langgraph_chat
from app.core.ollama_client import OllamaClient
from app.core.dependencies import get_ollama_client, get_planner_client
from app.services.agent_activity_stream import AgentActivityStream


async def test_tool_results_memory():
    """Test che i tool_results vengano salvati e recuperati dalla memoria"""
    
    print("=" * 80)
    print("TEST: Tool Results Memory Persistence")
    print("=" * 80)
    print()
    
    # Database connection
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        # Get or create test tenant and user
        tenant_result = await db.execute(
            select(Tenant).where(Tenant.name == "default_tenant")
        )
        tenant = tenant_result.scalar_one_or_none()
        
        if not tenant:
            print("❌ Tenant 'default_tenant' non trovato")
            return
        
        user_result = await db.execute(
            select(User).where(User.tenant_id == tenant.id, User.email == "test@example.com")
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            print("❌ Utente test@example.com non trovato")
            print("   Crea un utente di test prima di eseguire questo test")
            return
        
        print(f"✅ Utente trovato: {user.email} (ID: {user.id})")
        print()
        
        # Create test session
        test_session = SessionModel(
            tenant_id=tenant.id,
            name="Test Tool Results Memory",
        )
        db.add(test_session)
        await db.commit()
        await db.refresh(test_session)
        
        session_id = test_session.id
        print(f"✅ Sessione creata: {session_id}")
        print()
        
        # Initialize components
        memory_manager = MemoryManager(tenant_id=tenant.id)
        ollama = await get_ollama_client()
        planner_client = await get_planner_client()
        agent_activity_stream = AgentActivityStream()
        
        # Test 1: Simulate tool execution that returns IDs
        print("Test 1: Simulare esecuzione tool che restituisce ID")
        print("-" * 80)
        
        # Simulate tool_results with email IDs
        test_tool_results = [
            {
                "tool": "mcp_search_emails",
                "parameters": {"query": "urgente OR rispondi subito OR priorità"},
                "result": {
                    "emails": [
                        {"id": "19a93674987a96f7", "subject": "Email urgente 1"},
                        {"id": "199e7cb12c09945f", "subject": "Email urgente 2"},
                        {"id": "test123", "subject": "Email urgente 3"},
                    ],
                    "count": 3,
                }
            }
        ]
        
        # Save tool_results to short-term memory manually
        context_data = {
            "last_user_message": "Cerca email urgenti",
            "last_assistant_message": "Ho trovato 3 email urgenti",
            "message_count": 2,
            "tool_results": test_tool_results,
        }
        
        await memory_manager.update_short_term_memory(
            db,
            session_id,
            context_data,
            tenant_id=tenant.id,
        )
        
        print(f"✅ Tool results salvati nella memoria a breve termine")
        print(f"   Tool: {test_tool_results[0]['tool']}")
        print(f"   Email IDs: {[e['id'] for e in test_tool_results[0]['result']['emails']]}")
        print()
        
        # Test 2: Retrieve tool_results from memory
        print("Test 2: Recuperare tool_results dalla memoria")
        print("-" * 80)
        
        retrieved_memory = await memory_manager.get_short_term_memory(db, session_id)
        
        if retrieved_memory:
            retrieved_tool_results = retrieved_memory.get("tool_results", [])
            print(f"✅ Memoria recuperata")
            print(f"   Tool results trovati: {len(retrieved_tool_results)}")
            
            if retrieved_tool_results:
                first_result = retrieved_tool_results[0]
                print(f"   Tool: {first_result.get('tool')}")
                if isinstance(first_result.get('result'), dict) and 'emails' in first_result['result']:
                    email_ids = [e.get('id') for e in first_result['result']['emails']]
                    print(f"   Email IDs recuperati: {email_ids}")
                    
                    # Verify IDs match
                    original_ids = [e['id'] for e in test_tool_results[0]['result']['emails']]
                    if email_ids == original_ids:
                        print(f"   ✅ IDs corrispondono!")
                    else:
                        print(f"   ❌ IDs non corrispondono!")
                        print(f"      Originali: {original_ids}")
                        print(f"      Recuperati: {email_ids}")
                else:
                    print(f"   ⚠️  Struttura risultato inattesa: {type(first_result.get('result'))}")
            else:
                print(f"   ❌ Nessun tool_result trovato nella memoria recuperata")
        else:
            print(f"   ❌ Memoria a breve termine non trovata")
        
        print()
        
        # Test 3: Simulate acknowledgement and verify tool_results are available
        print("Test 3: Simulare acknowledgement e verificare tool_results disponibili")
        print("-" * 80)
        
        # Create a chat request with acknowledgement
        ack_request = ChatRequest(
            message="si grazie",
            use_memory=True,
        )
        
        # Get session context
        from app.services.conversation_summarizer import ConversationSummarizer
        summarizer = ConversationSummarizer()
        
        # Get previous messages
        from app.models.database import Message as MessageModel
        messages_result = await db.execute(
            select(MessageModel)
            .where(MessageModel.session_id == session_id)
            .order_by(MessageModel.created_at)
        )
        previous_messages = messages_result.scalars().all()
        all_messages_dict = [
            {"role": msg.role, "content": msg.content}
            for msg in previous_messages
        ]
        
        # Get short-term memory (should include tool_results)
        short_term = await memory_manager.get_short_term_memory(db, session_id)
        retrieved_memory_list = []
        
        if short_term:
            tool_results_from_memory = short_term.get("tool_results", [])
            if tool_results_from_memory:
                from app.agents.langgraph_app import _format_tool_results_for_llm
                tool_results_text = _format_tool_results_for_llm(tool_results_from_memory)
                retrieved_memory_list.insert(0, f"Risultati tool precedenti:\n{tool_results_text}")
                print(f"✅ Tool results recuperati dalla memoria per acknowledgement")
                print(f"   Tool results text length: {len(tool_results_text)}")
                print(f"   Preview: {tool_results_text[:200]}...")
            else:
                print(f"   ⚠️  Nessun tool_result trovato nella memoria a breve termine")
        else:
            print(f"   ⚠️  Memoria a breve termine non trovata")
        
        print()
        
        # Test 4: Verify tool_results are in state during plan execution
        print("Test 4: Verificare che tool_results siano nello stato durante esecuzione piano")
        print("-" * 80)
        
        # This would require running the actual LangGraph flow, which is complex
        # Instead, we'll verify the logic directly
        
        # Simulate what happens in tool_loop_node when acknowledgement is True
        if short_term and short_term.get("tool_results"):
            previous_tool_results = short_term.get("tool_results", [])
            print(f"✅ Tool results recuperati per acknowledgement: {len(previous_tool_results)}")
            
            # Verify structure
            if previous_tool_results:
                first_result = previous_tool_results[0]
                if isinstance(first_result.get('result'), dict) and 'emails' in first_result['result']:
                    email_ids = [e.get('id') for e in first_result['result']['emails']]
                    print(f"   Email IDs disponibili nello stato: {email_ids}")
                    print(f"   ✅ Gli ID possono essere usati per chiamare mcp_get_email")
                else:
                    print(f"   ⚠️  Struttura risultato inattesa")
        else:
            print(f"   ❌ Tool results non disponibili nello stato")
        
        print()
        
        # Cleanup
        await db.delete(test_session)
        await db.commit()
        print("✅ Test session eliminata")
    
    await engine.dispose()
    
    print()
    print("=" * 80)
    print("TEST COMPLETATO")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_tool_results_memory())

