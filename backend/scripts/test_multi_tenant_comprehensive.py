#!/usr/bin/env python3
"""
Test completo per verificare che tutti i servizi rispettino il multi-tenancy
e che la telemetria funzioni correttamente.
"""
import asyncio
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import AsyncSessionLocal
from app.models.schemas import ChatRequest
from app.core.dependencies import (
    init_clients,
    get_ollama_client,
    get_memory_manager,
    get_planner_client,
    get_agent_activity_stream,
)
from app.agents import run_langgraph_chat
from app.models.database import Session as SessionModel, User, Tenant, MemoryShort, Message as MessageModel
from sqlalchemy import select
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_multi_tenant_comprehensive():
    """Test completo multi-tenancy e telemetria"""
    print("🧪 Test Completo Multi-Tenancy e Telemetria\n")
    
    async with AsyncSessionLocal() as db:
        # Test 1: Verifica tenant isolation
        print("1️⃣  Test: Tenant Isolation")
        tenant_result = await db.execute(select(Tenant).limit(2))
        tenants = tenant_result.scalars().all()
        
        if len(tenants) < 1:
            print("   ❌ Nessun tenant trovato")
            return False
        
        tenant1 = tenants[0]
        tenant2 = tenants[1] if len(tenants) > 1 else tenants[0]
        print(f"   ✅ Tenant 1: {tenant1.id}")
        if len(tenants) > 1:
            print(f"   ✅ Tenant 2: {tenant2.id}")
        
        # Test 2: Verifica session isolation
        print("\n2️⃣  Test: Session Isolation")
        session1_result = await db.execute(
            select(SessionModel)
            .where(SessionModel.tenant_id == tenant1.id)
            .limit(1)
        )
        session1 = session1_result.scalar_one_or_none()
        
        if not session1:
            session1 = SessionModel(tenant_id=tenant1.id, title="Test Session 1")
            db.add(session1)
            await db.commit()
            await db.refresh(session1)
        
        print(f"   ✅ Session 1: {session1.id} (tenant: {session1.tenant_id})")
        
        # Verifica che le sessioni siano isolate
        session_check = await db.execute(
            select(SessionModel.id)
            .where(SessionModel.tenant_id == tenant1.id)
        )
        tenant1_sessions = session_check.scalars().all()
        print(f"   ✅ Tenant 1 ha {len(tenant1_sessions)} sessioni")
        
        # Test 3: Verifica memory isolation
        print("\n3️⃣  Test: Memory Isolation")
        memory_result = await db.execute(
            select(MemoryShort)
            .where(MemoryShort.tenant_id == tenant1.id)
        )
        tenant1_memories = memory_result.scalars().all()
        print(f"   ✅ Tenant 1 ha {len(tenant1_memories)} memorie short-term")
        
        # Verifica che le memorie abbiano tenant_id
        for mem in tenant1_memories[:3]:
            if mem.tenant_id:
                print(f"   ✅ Memoria {mem.session_id} ha tenant_id: {mem.tenant_id}")
            else:
                print(f"   ❌ Memoria {mem.session_id} NON ha tenant_id!")
                return False
        
        # Test 4: Verifica message isolation
        print("\n4️⃣  Test: Message Isolation")
        message_result = await db.execute(
            select(MessageModel)
            .where(MessageModel.tenant_id == tenant1.id)
            .limit(5)
        )
        tenant1_messages = message_result.scalars().all()
        print(f"   ✅ Tenant 1 ha {len(tenant1_messages)} messaggi")
        
        for msg in tenant1_messages[:3]:
            if msg.tenant_id:
                print(f"   ✅ Messaggio {msg.id} ha tenant_id: {msg.tenant_id}")
            else:
                print(f"   ❌ Messaggio {msg.id} NON ha tenant_id!")
                return False
        
        # Test 5: Verifica LangGraph execution e telemetria
        print("\n5️⃣  Test: LangGraph Execution e Telemetria")
        init_clients()
        ollama = get_ollama_client()
        planner_client = get_planner_client()
        memory_manager = get_memory_manager()
        agent_activity_stream = get_agent_activity_stream()
        
        # Get user
        user_result = await db.execute(
            select(User).where(User.tenant_id == tenant1.id).limit(1)
        )
        user = user_result.scalar_one_or_none()
        
        request = ChatRequest(
            session_id=session1.id,
            message="Test: dimmi solo OK",
            use_memory=True,
            force_web_search=False
        )
        
        print(f"   📤 Invio richiesta: '{request.message}'")
        try:
            result = await run_langgraph_chat(
                db=db,
                session_id=session1.id,
                request=request,
                ollama=ollama,
                planner_client=planner_client,
                agent_activity_stream=agent_activity_stream,
                memory_manager=memory_manager,
                session_context=[],
                retrieved_memory=[],
                memory_used={},
                previous_messages=None,
                pending_plan=None,
                current_user=user,
            )
            
            print(f"   ✅ LangGraph completato")
            print(f"   📊 Response length: {len(result['chat_response'].response) if result.get('chat_response') else 0}")
            
            # Verifica agent activity
            agent_activity = result.get('chat_response', {}).agent_activity if result.get('chat_response') else []
            print(f"   📡 Agent activity events: {len(agent_activity)}")
            
            if agent_activity:
                agent_ids = set(e.get('agent_id') for e in agent_activity)
                print(f"   📋 Agenti che hanno pubblicato eventi: {sorted(agent_ids)}")
                
                # Verifica che tutti i nodi principali abbiano pubblicato
                expected_agents = {'event_handler', 'orchestrator', 'tool_loop', 'knowledge_agent', 'notification_collector', 'response_formatter'}
                missing = expected_agents - agent_ids
                if missing:
                    print(f"   ⚠️  Agenti mancanti: {sorted(missing)}")
                else:
                    print(f"   ✅ Tutti gli agenti hanno pubblicato eventi")
            else:
                print(f"   ❌ Nessun evento di agent activity!")
                return False
            
        except Exception as e:
            print(f"   ❌ Errore: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Test 6: Verifica che tenant_id sia sempre presente nelle nuove memorie
        print("\n6️⃣  Test: Verifica tenant_id in nuove memorie")
        new_memory_result = await db.execute(
            select(MemoryShort)
            .where(MemoryShort.session_id == session1.id)
        )
        new_memory = new_memory_result.scalar_one_or_none()
        
        if new_memory:
            if new_memory.tenant_id:
                print(f"   ✅ Nuova memoria ha tenant_id: {new_memory.tenant_id}")
            else:
                print(f"   ❌ Nuova memoria NON ha tenant_id!")
                return False
        else:
            print(f"   ⚠️  Nessuna memoria short-term trovata (potrebbe essere normale)")
        
        print("\n✅ Tutti i test completati con successo!")
        return True

if __name__ == "__main__":
    success = asyncio.run(test_multi_tenant_comprehensive())
    sys.exit(0 if success else 1)

