#!/usr/bin/env python3
"""
Test semplificato per verificare il rilevamento contraddizioni completamente basato su LLM
Testa solo la funzione _analyze_with_llm senza bisogno di MemoryManager/ChromaDB
"""
import asyncio
import sys
import os
import json

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.llama_cpp_client import LlamaCppClient


async def test_llm_contradiction_analysis():
    """Test diretto dell'analisi LLM per contraddizioni"""
    
    print("=" * 80)
    print("TEST: Rilevamento Contraddizioni (Completamente LLM-based)")
    print("=" * 80)
    print()
    
    # Inizializza client
    client = LlamaCppClient(
        base_url="http://localhost:11435",
        model="Phi-3-mini-4k-instruct-q4"
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
            # Costruisci prompt come fa _analyze_with_llm
            prompt = f"""Analyze if these two statements logically contradict each other.

EXISTING STATEMENT: "{test_case['existing']}"
NEW STATEMENT: "{test_case['new']}"

Determine if there is a LOGICAL CONTRADICTION between these statements. Consider:

1. **Direct Contradictions**: Opposite claims (e.g., "single" vs "married", "likes X" vs "dislikes X")
2. **Temporal Contradictions**: Incompatible dates/events (e.g., "born July 12" vs "born August 15" for same person)
3. **Numerical Contradictions**: Incompatible values for same property (e.g., "age 30" vs "age 35" at same time)
4. **Status Contradictions**: Mutually exclusive states (e.g., "works at A" vs "works at B" simultaneously)
5. **Preference Contradictions**: Opposite preferences (e.g., "prefers X" vs "prefers Y" for same thing)
6. **Relationship Contradictions**: Incompatible relationships (e.g., "single" vs "has wife")
7. **Factual Contradictions**: Incompatible facts about the same entity

IMPORTANT:
- NOT contradictions: Complementary information, additional details, information about different time periods
- ARE contradictions: Statements that logically exclude each other
- Consider CONTEXT: "works at A in 2020" and "works at B in 2024" are NOT contradictions

Respond ONLY with valid JSON (no other text):
{{
    "is_contradiction": true/false,
    "confidence": 0.0-1.0,
    "explanation": "brief explanation of the contradiction type or why there is no contradiction",
    "contradiction_type": "direct|temporal|numerical|status|preference|relationship|factual|none"
}}"""
            
            # Chiama LLM
            print("⏳ Chiamando LLM...")
            response_text = await asyncio.wait_for(
                client.generate_with_context(
                    prompt=prompt,
                    session_context=[],
                ),
                timeout=30.0
            )
            
            print(f"📥 Risposta LLM: {response_text[:200]}...")
            print()
            
            # Parse JSON dalla risposta
            result = None
            try:
                # Cerca JSON nella risposta (potrebbe avere testo prima/dopo)
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response_text[json_start:json_end]
                    result = json.loads(json_str)
                else:
                    # Prova a parsare tutta la risposta
                    result = json.loads(response_text.strip())
            except json.JSONDecodeError as e:
                print(f"⚠️  Errore parsing JSON: {e}")
                print(f"   Risposta completa: {response_text}")
                # Prova a estrarre informazioni manualmente
                is_contradiction = "true" in response_text.lower() or "is_contradiction" in response_text.lower()
                result = {
                    "is_contradiction": is_contradiction,
                    "confidence": 0.5,
                    "explanation": "Could not parse JSON",
                    "contradiction_type": "unknown"
                }
            
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
        success = asyncio.run(test_llm_contradiction_analysis())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrotto dall'utente")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nErrore fatale: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

