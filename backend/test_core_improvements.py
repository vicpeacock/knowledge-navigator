#!/usr/bin/env python3
"""
Test script for Core Improvements:
- Auto-learning from conversations
- Advanced semantic search
- Memory consolidation
"""
import asyncio
import sys
from uuid import uuid4
from datetime import datetime
import pytest

pytestmark = pytest.mark.skip(reason="Test manuali per verifiche integrate: eseguirli a mano quando necessario")

# Add backend to path
sys.path.insert(0, '/Users/pallotta/Personal AI Assistant/backend')

from app.db.database import AsyncSessionLocal
from app.core.memory_manager import MemoryManager
from app.core.ollama_client import OllamaClient
from app.services.conversation_learner import ConversationLearner
from app.services.advanced_search import AdvancedSearch
from app.services.memory_consolidator import MemoryConsolidator


async def test_auto_learning():
    """Test auto-learning from conversations"""
    print("\n" + "="*60)
    print("TEST 1: Auto-Learning from Conversations")
    print("="*60)
    
    db = AsyncSessionLocal()
    memory = MemoryManager()
    ollama = OllamaClient()
    learner = ConversationLearner(memory_manager=memory, ollama_client=ollama)
    
    try:
        # Create a test session
        session_id = uuid4()
        
        # Simulate a conversation with extractable knowledge
        test_messages = [
            {"role": "user", "content": "Il mio compleanno è il 15 marzo"},
            {"role": "assistant", "content": "Perfetto! Ho notato che il tuo compleanno è il 15 marzo. Lo ricorderò."},
            {"role": "user", "content": "Preferisco lavorare al mattino, sono più produttivo"},
            {"role": "assistant", "content": "Capito! Preferisci lavorare al mattino perché sei più produttivo. Lo terrò a mente."},
        ]
        
        print(f"📝 Test conversation:")
        for msg in test_messages:
            print(f"  {msg['role']}: {msg['content']}")
        
        # Extract knowledge
        print("\n🔍 Extracting knowledge...")
        knowledge_items = await learner.extract_knowledge_from_conversation(
            db=db,
            session_id=session_id,
            messages=test_messages,
            min_importance=0.5,
        )
        
        print(f"\n✅ Extracted {len(knowledge_items)} knowledge items:")
        for i, item in enumerate(knowledge_items, 1):
            print(f"  {i}. Type: {item.get('type', 'unknown')}")
            print(f"     Content: {item.get('content', '')[:80]}...")
            print(f"     Importance: {item.get('importance', 0):.2f}")
        
        if knowledge_items:
            # Index knowledge
            print("\n💾 Indexing knowledge...")
            indexing_stats = await learner.index_extracted_knowledge(
                db=db,
                knowledge_items=knowledge_items,
                session_id=session_id,
            )
            print(f"✅ Indexed {indexing_stats.get('indexed', 0)} items")
            print(f"   Errors: {len(indexing_stats.get('errors', []))}")
            
            # Verify retrieval
            print("\n🔎 Verifying retrieval...")
            retrieved = await memory.retrieve_long_term_memory(
                query="compleanno",
                n_results=3,
            )
            print(f"✅ Retrieved {len(retrieved)} memories for 'compleanno'")
            if retrieved:
                print(f"   First result: {retrieved[0][:100]}...")
        else:
            print("⚠️  No knowledge extracted (this might be normal if LLM doesn't find important info)")
        
        await db.commit()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        await db.rollback()
        return False
    finally:
        await db.close()


async def test_advanced_search():
    """Test advanced semantic search"""
    print("\n" + "="*60)
    print("TEST 2: Advanced Semantic Search (Hybrid)")
    print("="*60)
    
    memory = MemoryManager()
    search_service = AdvancedSearch(memory_manager=memory)
    
    try:
        # Test hybrid search
        print("\n🔍 Testing hybrid search for 'Python async'...")
        results = await search_service.hybrid_search(
            query="Python async",
            n_results=3,
            semantic_weight=0.7,
            keyword_weight=0.3,
        )
        
        print(f"✅ Found {len(results)} results:")
        for i, result in enumerate(results, 1):
            print(f"\n  {i}. Combined Score: {result.get('combined_score', 0):.3f}")
            print(f"     Semantic: {result.get('semantic_score', 0):.3f}, Keyword: {result.get('keyword_score', 0):.3f}")
            print(f"     Type: {result.get('content_type', 'unknown')}")
            content = result.get('content', '')
            print(f"     Content: {content[:100]}...")
        
        # Test suggestions
        print("\n💡 Testing query suggestions...")
        suggestions = await search_service.suggest_related(
            query="Python async programming",
            n_suggestions=3,
        )
        print(f"✅ Generated {len(suggestions)} suggestions:")
        for i, suggestion in enumerate(suggestions, 1):
            print(f"  {i}. {suggestion}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_memory_consolidation():
    """Test memory consolidation"""
    print("\n" + "="*60)
    print("TEST 3: Memory Consolidation")
    print("="*60)
    
    db = AsyncSessionLocal()
    memory = MemoryManager()
    consolidator = MemoryConsolidator(memory_manager=memory)
    
    try:
        # First, add some duplicate-like memories
        print("\n📝 Creating test memories...")
        session_id1 = uuid4()
        session_id2 = uuid4()
        
        # Add similar memories
        await memory.add_long_term_memory(
            db=db,
            content="[FACT] L'utente preferisce lavorare al mattino",
            learned_from_sessions=[session_id1],
            importance_score=0.7,
        )
        
        await memory.add_long_term_memory(
            db=db,
            content="[FACT] L'utente è più produttivo al mattino",
            learned_from_sessions=[session_id2],
            importance_score=0.6,
        )
        
        await db.commit()
        print("✅ Created 2 similar memories")
        
        # Test consolidation
        print("\n🔄 Testing consolidation...")
        stats = await consolidator.consolidate_duplicates(
            db=db,
            similarity_threshold=0.75,
        )
        
        print(f"✅ Consolidation stats:")
        print(f"   Merged groups: {stats.get('merged', 0)}")
        print(f"   Kept memories: {stats.get('kept', 0)}")
        print(f"   Removed duplicates: {stats.get('removed', 0)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        await db.rollback()
        return False
    finally:
        await db.close()


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("TESTING CORE IMPROVEMENTS")
    print("="*60)
    
    results = []
    
    # Test 1: Auto-learning
    results.append(await test_auto_learning())
    
    # Test 2: Advanced search
    results.append(await test_advanced_search())
    
    # Test 3: Memory consolidation
    results.append(await test_memory_consolidation())
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"✅ Passed: {sum(results)}/{len(results)}")
    print(f"❌ Failed: {len(results) - sum(results)}/{len(results)}")
    
    if all(results):
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests failed")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
