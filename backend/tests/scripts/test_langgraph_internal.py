#!/usr/bin/env python3
"""
Script per testare direttamente LangGraph senza passare per l'API HTTP.
Questo permette di vedere esattamente cosa succede nel grafo.
"""
import asyncio
import sys
from pathlib import Path
from uuid import UUID

# Add parent directory to path
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

async def test_langgraph_internal():
    """Test LangGraph chiamando direttamente la funzione."""
    print("🧪 Testing LangGraph Internal Execution\n")
    
    async with AsyncSessionLocal() as db:
        # Get default tenant
        print("1️⃣  Getting default tenant...")
        tenant_result = await db.execute(
            select(Tenant).limit(1)
        )
        tenant = tenant_result.scalar_one_or_none()
        if not tenant:
            print("❌ No tenant found")
            return
        tenant_id = tenant.id
        print(f"   ✅ Tenant: {tenant_id}")
        
        # Get or create a session
        print("\n2️⃣  Getting or creating session...")
        session_result = await db.execute(
            select(SessionModel)
            .where(SessionModel.tenant_id == tenant_id)
            .limit(1)
        )
        session = session_result.scalar_one_or_none()
        
        if not session:
            # Create a new session
            session = SessionModel(
                tenant_id=tenant_id,
                title="Test Session"
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
            print(f"   ✅ Created new session: {session.id}")
        else:
            print(f"   ✅ Using existing session: {session.id}")
        
        # Get or create a user
        print("\n3️⃣  Getting or creating user...")
        user_result = await db.execute(
            select(User)
            .where(User.tenant_id == tenant_id)
            .limit(1)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            print("   ⚠️  No user found, will use None (some features may not work)")
            user = None
        else:
            print(f"   ✅ Using user: {user.email}")
        
        # Initialize dependencies
        print("\n4️⃣  Initializing dependencies...")
        print("   Initializing clients...")
        init_clients()  # Initialize global clients
        ollama = get_ollama_client()
        planner_client = get_planner_client()
        memory_manager = get_memory_manager()
        agent_activity_stream = get_agent_activity_stream()
        print(f"   ✅ Ollama client: {ollama is not None}")
        print(f"   ✅ Planner client: {planner_client is not None}")
        print(f"   ✅ Memory manager: {memory_manager is not None}")
        print(f"   ✅ Agent activity stream: {agent_activity_stream is not None}")
        
        # Create chat request
        print("\n5️⃣  Creating chat request...")
        request = ChatRequest(
            session_id=session.id,
            message="Puoi pianificare il viaggio utilizzando Google Maps tool? Da Chemin du Gué 69, Petit‑Lancy a Yverdon-les-Bains",
            use_memory=True,
            force_web_search=False
        )
        print(f"   ✅ Request: '{request.message}'")
        
        # Prepare context
        print("\n6️⃣  Preparing context...")
        session_context = []
        retrieved_memory = []
        memory_used = {}
        previous_messages = None
        pending_plan = None
        
        print("   ✅ Context prepared")
        
        # Call LangGraph
        print("\n7️⃣  Calling LangGraph run_langgraph_chat()...")
        print("   ⚠️  This will execute the full graph...")
        try:
            result = await run_langgraph_chat(
                db=db,
                session_id=session.id,
                request=request,
                ollama=ollama,
                planner_client=planner_client,
                agent_activity_stream=agent_activity_stream,
                memory_manager=memory_manager,
                session_context=session_context,
                retrieved_memory=retrieved_memory,
                memory_used=memory_used,
                previous_messages=previous_messages,
                pending_plan=pending_plan,
                current_user=user,
            )
            
            print("\n✅ LangGraph execution completed!")
            print(f"   Response length: {len(result['chat_response'].response) if result.get('chat_response') else 0}")
            print(f"   Response preview: {result['chat_response'].response[:200] if result.get('chat_response') else 'NONE'}")
            print(f"   Tools used: {result['chat_response'].tools_used if result.get('chat_response') else []}")
            print(f"   Agent activity events: {len(result['chat_response'].agent_activity) if result.get('chat_response') else 0}")
            
            if result.get('chat_response') and result['chat_response'].agent_activity:
                print("\n   Agent Activity:")
                for event in result['chat_response'].agent_activity:
                    # event is a Pydantic model (AgentActivityEvent), not a dict
                    agent_name = event.agent_name if hasattr(event, 'agent_name') else getattr(event, 'agent_name', 'Unknown')
                    status = event.status if hasattr(event, 'status') else getattr(event, 'status', 'unknown')
                    print(f"      - {agent_name}: {status}")
            
        except Exception as e:
            print(f"\n❌ LangGraph execution failed: {e}")
            import traceback
            traceback.print_exc()
            raise

if __name__ == "__main__":
    asyncio.run(test_langgraph_internal())

