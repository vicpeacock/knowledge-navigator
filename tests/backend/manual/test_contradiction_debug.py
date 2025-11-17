#!/usr/bin/env python3
"""
Test script per debuggare il rilevamento contraddizioni
"""
import asyncio
import sys
import os
import pytest

pytestmark = pytest.mark.skip(reason="Test manuale/integrativo: eseguirlo direttamente via __main__ quando serve")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.memory_manager import MemoryManager
from app.core.dependencies import get_ollama_background_client
from app.services.semantic_integrity_checker import SemanticIntegrityChecker
from app.db.database import AsyncSessionLocal


async def test_contradiction_detection():
    """Test del rilevamento contraddizioni con logging dettagliato"""
    
    print("=" * 80)
    print("TEST: Rilevamento Contraddizioni - Debug")
    print("=" * 80)
    print()
    
    memory_manager = MemoryManager()
    ollama_client = get_ollama_background_client()
    
    async with AsyncSessionLocal() as db:
        # Prima: aggiungi "Mi piace la pastasciutta" in memoria
        print("1. Aggiungendo 'Mi piace la pastasciutta' in memoria...")
        await memory_manager.add_long_term_memory(
            db,
            content="L'utente ama la pastasciutta",
            learned_from_sessions=[],
            importance_score=0.7,
        )
        await db.commit()
        print("   ✅ Salvato in memoria")
        print()
        
        # Verifica che sia stato salvato
        print("2. Verificando memorie esistenti...")
        existing = await memory_manager.retrieve_long_term_memory(
            query="pastasciutta",
            n_results=5,
        )
        print(f"   Trovate {len(existing)} memorie per 'pastasciutta':")
        for i, mem in enumerate(existing, 1):
            print(f"   {i}. {mem[:100]}...")
        print()
        
        # Ora testa la contraddizione con "Detesto gli spaghetti"
        print("3. Testando contraddizione con 'Detesto gli spaghetti'...")
        checker = SemanticIntegrityChecker(
            memory_manager=memory_manager,
            ollama_client=ollama_client,
        )
        
        new_knowledge = {
            "type": "preference",
            "content": "L'utente detesta gli spaghetti",
            "importance": 0.7,
        }
        
        result = await checker.check_contradictions(
            new_knowledge=new_knowledge,
            db=db,
            max_similar_memories=15,
            confidence_threshold=0.7,
        )
        
        print()
        print("=" * 80)
        print("RISULTATO:")
        print("=" * 80)
        print(f"Has contradiction: {result.get('has_contradiction')}")
        print(f"Confidence: {result.get('confidence', 0):.2f}")
        print(f"Contradictions count: {len(result.get('contradictions', []))}")
        print()
        
        if result.get('contradictions'):
            for i, contr in enumerate(result.get('contradictions', []), 1):
                print(f"Contradiction {i}:")
                print(f"  New: {contr.get('new_memory', '')}")
                print(f"  Existing: {contr.get('existing_memory', '')}")
                print(f"  Type: {contr.get('contradiction_type', 'unknown')}")
                print(f"  Confidence: {contr.get('confidence', 0):.2f}")
                print(f"  Explanation: {contr.get('explanation', '')[:200]}...")
                print()
        else:
            print("❌ Nessuna contraddizione rilevata")
            print()
            print("Verificando ricerca semantica...")
            similar = await checker._find_similar_memories(
                "L'utente detesta gli spaghetti",
                n_results=15,
            )
            print(f"Memorie simili trovate: {len(similar)}")
            for i, mem in enumerate(similar, 1):
                print(f"  {i}. {mem[:100]}...")
        
        print("=" * 80)


if __name__ == "__main__":
    try:
        asyncio.run(test_contradiction_detection())
    except KeyboardInterrupt:
        print("\n\nTest interrotto dall'utente")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nErrore fatale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

