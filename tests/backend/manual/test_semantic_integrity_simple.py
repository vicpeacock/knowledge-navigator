"""
Test script for semantic integrity checker - simplified version
Tests entity extraction and pre-filtering without LLM
"""
import asyncio
from uuid import uuid4
import pytest
from app.db.database import AsyncSessionLocal
from app.core.memory_manager import MemoryManager
from app.services.semantic_integrity_checker import SemanticIntegrityChecker
from app.core.dependencies import get_ollama_background_client

pytestmark = pytest.mark.skip(reason="Test semplificato dell'integrità semantica da eseguire manualmente")

async def test_entity_extraction():
    """Test entity extraction and concept categorization"""
    checker = SemanticIntegrityChecker(
        memory_manager=MemoryManager(),
        ollama_client=None,
    )
    
    print("🧪 Testing Entity Extraction\n")
    print("=" * 60)
    
    test_cases = [
        "Sono nato il 12 luglio 1966",
        "Il mio compleanno è il 15 marzo",
        "Sono single",
        "Ho una moglie",
        "Preferisco il caffè",
        "Non mi piace il caffè",
        "Lavoro in Innosuisse",
        "Sono freelance",
    ]
    
    for text in test_cases:
        entities = checker._extract_entities(text)
        print(f"\n📝 Test: '{text}'")
        print(f"   Date: {entities.get('dates', [])}")
        print(f"   Numbers: {entities.get('numbers', [])}")
        print(f"   Keywords: {entities.get('keywords', [])}")
        print(f"   Concepts: {entities.get('concepts', [])}")
    
    print("\n" + "=" * 60)
    print("\n🔍 Testing Conflict Detection (Pre-filter)\n")
    print("=" * 60)
    
    # Test contradictions
    contradiction_tests = [
        (
            "Sono nato il 12 luglio 1966",
            "Il mio compleanno è il 15 agosto",
            "Date contradiction"
        ),
        (
            "Sono single",
            "Ho una moglie",
            "Status contradiction"
        ),
        (
            "Preferisco il caffè",
            "Non mi piace il caffè",
            "Preference contradiction"
        ),
        (
            "Lavoro in Innosuisse",
            "Sono freelance",
            "Work status (might not be contradiction)"
        ),
        (
            "Sono nato il 12 luglio 1966",
            "Vivo a Teramo",
            "No contradiction (different concepts)"
        ),
    ]
    
    for existing, new, description in contradiction_tests:
        existing_entities = checker._extract_entities(existing)
        new_entities = checker._extract_entities(new)
        has_conflict = checker._entities_conflict(new_entities, existing_entities)
        
        print(f"\n📊 {description}")
        print(f"   Existing: '{existing}'")
        print(f"   New: '{new}'")
        print(f"   Conflict detected: {'✅ YES' if has_conflict else '❌ NO'}")
        if has_conflict:
            print(f"   Existing concepts: {existing_entities.get('concepts', [])}")
            print(f"   New concepts: {new_entities.get('concepts', [])}")
    
    print("\n" + "=" * 60)
    print("✅ Entity extraction test completed")

async def test_full_contradiction_detection():
    """Test full contradiction detection with LLM (slower)"""
    async with AsyncSessionLocal() as db:
        memory = MemoryManager()
        session_id = uuid4()
        
        print("\n\n🧪 Testing Full Contradiction Detection (with LLM)\n")
        print("=" * 60)
        
        # Test with actual contradiction
        new_knowledge = {
            "type": "personal_info",
            "content": "Sono nato il 20 agosto 1966",  # Different from existing "12 luglio 1966"
            "importance": 0.9,
        }
        
        print(f"\n📝 Nuova conoscenza da indicizzare:")
        print(f"   Contenuto: {new_knowledge['content']}")
        print(f"   (Esiste già: 'Data di nascita: 12 luglio 1966')")
        
        checker = SemanticIntegrityChecker(
            memory_manager=memory,
            ollama_client=get_ollama_background_client(),
        )
        
        print(f"\n🔍 Controllando contraddizioni...")
        result = await checker.check_contradictions(
            new_knowledge=new_knowledge,
            db=db,
            max_similar_memories=5,  # Limit to 5 for faster test
            confidence_threshold=0.7,  # Lower threshold for testing
        )
        
        print(f"\n📬 Risultato:")
        print(f"   Ha contraddizioni: {'✅ SÌ' if result.get('has_contradiction') else '❌ NO'}")
        print(f"   Confidenza massima: {result.get('confidence', 0):.2f}")
        print(f"   Numero contraddizioni: {len(result.get('contradictions', []))}")
        
        if result.get('contradictions'):
            for i, contr in enumerate(result.get('contradictions', []), 1):
                print(f"\n   Contraddizione {i}:")
                print(f"   - Tipo: {contr.get('contradiction_type', 'unknown')}")
                print(f"   - Confidenza: {contr.get('confidence', 0):.2f}")
                print(f"   - Nuova: {contr.get('new_memory', '')[:80]}...")
                print(f"   - Esistente: {contr.get('existing_memory', '')[:80]}...")
                print(f"   - Spiegazione: {contr.get('explanation', '')[:150]}...")
        
        print("\n" + "=" * 60)
        print("✅ Full contradiction detection test completed")

if __name__ == "__main__":
    print("🚀 Starting Semantic Integrity Tests\n")
    
    # First test: entity extraction (fast, no LLM)
    asyncio.run(test_entity_extraction())
    
    # Ask user if they want to test with LLM (slower)
    print("\n" + "=" * 60)
    print("\n⚠️  Test completo con LLM richiede più tempo.")
    print("Vuoi eseguirlo? (s/n): ", end="")
    
    # For automated testing, we'll run it
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--full":
        asyncio.run(test_full_contradiction_detection())
    else:
        print("\n💡 Per eseguire il test completo con LLM, usa: python test_semantic_integrity_simple.py --full")

