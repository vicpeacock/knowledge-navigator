#!/usr/bin/env python3
"""
Test script per verificare il rilevamento contraddizioni completamente basato su LLM
"""
import asyncio
import sys
import os
from typing import List, Dict
import pytest

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.llama_cpp_client import LlamaCppClient
from app.core.memory_manager import MemoryManager
from app.services.semantic_integrity_checker import SemanticIntegrityChecker
from app.core.dependencies import get_ollama_background_client


pytestmark = pytest.mark.skip(reason="Test approfondito dell'integrità semantica: richiede run manuale")


class MockMemoryManager(MemoryManager):
    def __init__(self):
        super().__init__()
        self.memory: List[Dict] = []

    def add_memory(self, memory_item: Dict):
        self.memory.append(memory_item)

    def get_memory(self) -> List[Dict]:
        return self.memory

    def clear_memory(self):
        self.memory = []


async def test_contradiction_detection():
    """Test del rilevamento contraddizioni con LLM"""
    
    print("=" * 80)
    print("TEST: Rilevamento Contraddizioni (Completamente LLM-based)")
    print("=" * 80)
    print()
    
    # Inizializza client e servizi
    client = LlamaCppClient(
        base_url="http://localhost:11435",
        model="Phi-3-mini-4k-instruct-q4"
    )
    
    memory_manager = MockMemoryManager()
    checker = SemanticIntegrityChecker(
        memory_manager=memory_manager,
        ollama_client=client
    )
    
    # Test cases
    test_cases = [
        {
            "name": "Contraddizione Temporale (Date diverse)",
            "new": "Sono nato il 20 agosto 1966",
            "existing": "Data di nascita: 12 luglio 1966",
            "expected": True,
        },
        {
            "name": "Contraddizione Diretta (Stati opposti)",
            "new": "Sono sposato",
            "existing": "Sono single",
            "expected": True,
        },
        {
            "name": "Contraddizione Numerica (Età)",
            "new": "Ho 35 anni",
            "existing": "Ho 30 anni",
            "expected": True,
        },
        {
            "name": "NON Contraddizione (Informazioni complementari)",
            "new": "Lavoro come sviluppatore",
            "existing": "Vivo a Milano",
            "expected": False,
        },
        {
            "name": "NON Contraddizione (Periodi temporali diversi)",
            "new": "Ho lavorato in A nel 2020",
            "existing": "Lavoro in B dal 2024",
            "expected": False,
        },
        {
            "name": "Contraddizione Preferenze",
            "new": "Preferisco Python",
            "existing": "Preferisco Java",
            "expected": True,
        },
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"TEST {i}/{len(test_cases)}: {test_case['name']}")
        print(f"{'='*80}")
        print(f"Nuova memoria:     {test_case['new']}")
        print(f"Memoria esistente: {test_case['existing']}")
        print(f"Atteso:            {'CONTRADDIZIONE' if test_case['expected'] else 'NO CONTRADDIZIONE'}")
        print()
        
        try:
            # Analizza con LLM
            result = await asyncio.wait_for(
                checker._analyze_with_llm(
                    new_memory=test_case['new'],
                    existing_memory=test_case['existing'],
                    confidence_threshold=0.7
                ),
                timeout=30.0
            )
            
            is_contradiction = result.get('is_contradiction', False)
            confidence = result.get('confidence', 0.0)
            explanation = result.get('explanation', '')
            contradiction_type = result.get('contradiction_type', 'none')
            
            print(f"✅ Risultato LLM:")
            print(f"   Contraddizione: {is_contradiction}")
            print(f"   Confidence:     {confidence:.2f}")
            print(f"   Tipo:           {contradiction_type}")
            print(f"   Spiegazione:    {explanation[:200]}...")
            print()
            
            # Verifica risultato
            if is_contradiction == test_case['expected']:
                print(f"✅ TEST PASSATO: Risultato corretto!")
                results.append(True)
            else:
                print(f"❌ TEST FALLITO: Atteso {test_case['expected']}, ottenuto {is_contradiction}")
                results.append(False)
                
        except asyncio.TimeoutError:
            print(f"❌ TIMEOUT: L'analisi ha impiegato più di 30 secondi")
            results.append(False)
        except Exception as e:
            print(f"❌ ERRORE: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    # Riepilogo
    print()
    print("=" * 80)
    print("RIEPILOGO TEST")
    print("=" * 80)
    print(f"Test totali:    {len(test_cases)}")
    print(f"Test passati:  {sum(results)}")
    print(f"Test falliti:  {len(results) - sum(results)}")
    print(f"Success rate:  {sum(results)/len(results)*100:.1f}%")
    print("=" * 80)
    
    return all(results)


if __name__ == "__main__":
    try:
        success = asyncio.run(test_contradiction_detection())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrotto dall'utente")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nErrore fatale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

