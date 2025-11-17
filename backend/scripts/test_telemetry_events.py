#!/usr/bin/env python3
"""
Test per verificare che tutti gli eventi di telemetria vengano pubblicati correttamente.
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
from app.models.database import Session as SessionModel, User, Tenant
from sqlalchemy import select
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_telemetry_events():
    """Test che verifica che tutti gli eventi di telemetria vengano pubblicati"""
    print("🧪 Test Telemetria Eventi\n")
    
    async with AsyncSessionLocal() as db:
        # Setup
        tenant_result = await db.execute(select(Tenant).limit(1))
        tenant = tenant_result.scalar_one_or_none()
        if not tenant:
            print("❌ Nessun tenant trovato")
            return False
        
        session_result = await db.execute(
            select(SessionModel).where(SessionModel.tenant_id == tenant.id).limit(1)
        )
        session = session_result.scalar_one_or_none()
        if not session:
            session = SessionModel(tenant_id=tenant.id, title="Test Telemetry")
            db.add(session)
            await db.commit()
            await db.refresh(session)
        
        user_result = await db.execute(
            select(User).where(User.tenant_id == tenant.id).limit(1)
        )
        user = user_result.scalar_one_or_none()
        
        # Initialize
        init_clients()
        ollama = get_ollama_client()
        planner_client = get_planner_client()
        memory_manager = get_memory_manager()
        agent_activity_stream = get_agent_activity_stream()
        
        # Register for events
        queue = await agent_activity_stream.register(session.id)
        print(f"✅ Registrato per eventi sulla sessione {session.id}\n")
        
        # Create request
        request = ChatRequest(
            session_id=session.id,
            message="Test telemetria",
            use_memory=True,
            force_web_search=False
        )
        
        print(f"📤 Invio richiesta: '{request.message}'")
        print("   ⏳ Attendere esecuzione LangGraph...\n")
        
        try:
            result = await run_langgraph_chat(
                db=db,
                session_id=session.id,
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
            
            # Collect events from queue
            events_received = []
            try:
                while True:
                    event = await asyncio.wait_for(queue.get(), timeout=0.5)
                    events_received.append(event)
            except asyncio.TimeoutError:
                pass
            
            # Also check agent_activity in response
            agent_activity = result.get('chat_response', {}).agent_activity if result.get('chat_response') else []
            
            print(f"📊 Eventi ricevuti dalla coda: {len(events_received)}")
            print(f"📊 Eventi in agent_activity: {len(agent_activity)}")
            
            all_events = events_received + agent_activity
            unique_events = {}
            for event in all_events:
                agent_id = event.get('agent_id', 'unknown')
                status = event.get('status', 'unknown')
                key = f"{agent_id}:{status}"
                if key not in unique_events:
                    unique_events[key] = event
            
            print(f"\n📋 Eventi unici trovati ({len(unique_events)}):")
            for key, event in sorted(unique_events.items()):
                agent_name = event.get('agent_name', event.get('agent_id', 'unknown'))
                status = event.get('status', 'unknown')
                print(f"   - {agent_name}: {status}")
            
            # Verifica agenti attesi
            expected_agents = {
                'event_handler': ['started', 'completed'],
                'orchestrator': ['started', 'completed'],
                'tool_loop': ['started', 'completed'],
                'knowledge_agent': ['started', 'completed'],
                'notification_collector': ['started', 'completed'],
                'response_formatter': ['started', 'completed'],
            }
            
            print(f"\n🔍 Verifica agenti attesi:")
            all_present = True
            for agent_id, expected_statuses in expected_agents.items():
                found_statuses = []
                for event in unique_events.values():
                    if event.get('agent_id') == agent_id:
                        found_statuses.append(event.get('status'))
                
                found_statuses = set(found_statuses)
                expected_statuses_set = set(expected_statuses)
                
                if found_statuses >= expected_statuses_set:
                    print(f"   ✅ {agent_id}: trovati {found_statuses}")
                else:
                    missing = expected_statuses_set - found_statuses
                    print(f"   ❌ {agent_id}: mancanti {missing} (trovati: {found_statuses})")
                    all_present = False
            
            await agent_activity_stream.unregister(session.id, queue)
            
            if all_present:
                print("\n✅ Tutti gli agenti hanno pubblicato gli eventi attesi!")
                return True
            else:
                print("\n❌ Alcuni agenti non hanno pubblicato tutti gli eventi attesi")
                return False
                
        except Exception as e:
            print(f"\n❌ Errore: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = asyncio.run(test_telemetry_events())
    sys.exit(0 if success else 1)

