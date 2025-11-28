#!/usr/bin/env python3
"""
Test standalone di Gemini API seguendo esattamente lo schema suggerito da Gemini 3.
Questo script NON usa nulla del backend, testa direttamente l'API Gemini.
"""
import os
import sys
import asyncio
from typing import Optional, List, Dict, Any

# Verifica che google-generativeai sia installato
try:
    import google.generativeai as genai
    import google.generativeai.types as genai_types
    print("✅ google-generativeai importato correttamente")
except ImportError as e:
    print(f"❌ Errore: {e}")
    print("Installa con: pip install google-generativeai")
    sys.exit(1)

# Carica API key da variabile d'ambiente
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("❌ Errore: GEMINI_API_KEY non trovata nelle variabili d'ambiente")
    print("   Esporta con: export GEMINI_API_KEY='your-key-here'")
    sys.exit(1)

# Configura Gemini
genai.configure(api_key=GEMINI_API_KEY)

def create_safety_settings(block_none: bool = False) -> List[Any]:
    """
    Crea safety settings seguendo lo schema di Gemini 3.
    
    Args:
        block_none: Se True, usa BLOCK_NONE (richiede allowlist). Altrimenti usa BLOCK_ONLY_HIGH.
    
    Returns:
        Lista di SafetySetting objects o dict (se SafetySetting non disponibile)
    """
    HarmCategory = genai_types.HarmCategory
    HarmBlockThreshold = genai_types.HarmBlockThreshold
    
    threshold = HarmBlockThreshold.BLOCK_NONE if block_none else HarmBlockThreshold.BLOCK_ONLY_HIGH
    threshold_name = "BLOCK_NONE" if block_none else "BLOCK_ONLY_HIGH"
    
    print(f"🔍 Creando safety settings con threshold: {threshold_name}")
    
    # Prova a usare SafetySetting objects (preferito)
    try:
        if hasattr(genai_types, 'SafetySetting'):
            SafetySetting = genai_types.SafetySetting
            print("✅ Usando SafetySetting objects")
            return [
                SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=threshold,
                ),
                SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=threshold,
                ),
                SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=threshold,
                ),
                SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=threshold,
                ),
            ]
        else:
            # Fallback: prova import diretto
            from google.generativeai.types import SafetySetting
            print("✅ Usando SafetySetting objects (import diretto)")
            return [
                SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=threshold,
                ),
                SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=threshold,
                ),
                SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                    threshold=threshold,
                ),
                SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                    threshold=threshold,
                ),
            ]
    except (ImportError, AttributeError) as e:
        # Fallback a dict format
        print(f"⚠️  SafetySetting objects non disponibili: {e}")
        print("   Usando formato dict come fallback")
        return [
            {
                "category": HarmCategory.HARM_CATEGORY_HARASSMENT,
                "threshold": threshold,
            },
            {
                "category": HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                "threshold": threshold,
            },
            {
                "category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                "threshold": threshold,
            },
            {
                "category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                "threshold": threshold,
            },
        ]


def test_gemini_basic(prompt: str, model_name: str = "gemini-2.5-pro"):
    """
    Test 1: Test base senza configurazioni speciali
    """
    print("\n" + "="*80)
    print("TEST 1: Test base (senza configurazioni)")
    print("="*80)
    print(f"📝 Prompt: {prompt}")
    print(f"🤖 Model: {model_name}")
    
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        
        if response.candidates:
            candidate = response.candidates[0]
            finish_reason = getattr(candidate, 'finish_reason', None)
            
            if finish_reason == 1:  # SAFETY
                print("❌ BLOCCATO: finish_reason=1 (SAFETY)")
                if hasattr(candidate, 'safety_ratings'):
                    for rating in candidate.safety_ratings:
                        cat = getattr(rating.category, 'name', str(rating.category))
                        prob = getattr(rating.probability, 'name', str(rating.probability))
                        print(f"   - {cat}: {prob}")
                return None
            else:
                text = response.text
                print(f"✅ SUCCESS: {text[:200]}")
                return text
        else:
            print("❌ Nessun candidato nella risposta")
            return None
    except Exception as e:
        print(f"❌ ERRORE: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_gemini_with_safety_settings(prompt: str, model_name: str = "gemini-2.5-pro", block_none: bool = False):
    """
    Test 2: Con safety settings passati al costruttore (schema Gemini 3)
    """
    print("\n" + "="*80)
    threshold_name = "BLOCK_NONE" if block_none else "BLOCK_ONLY_HIGH"
    print(f"TEST 2: Con safety_settings nel costruttore ({threshold_name})")
    print("="*80)
    print(f"📝 Prompt: {prompt}")
    print(f"🤖 Model: {model_name}")
    
    try:
        safety_settings = create_safety_settings(block_none=block_none)
        
        # CRITICAL: Pass safety_settings al costruttore (schema Gemini 3)
        model = genai.GenerativeModel(
            model_name,
            safety_settings=safety_settings
        )
        
        print(f"✅ Modello creato con safety_settings ({threshold_name})")
        
        response = model.generate_content(prompt)
        
        if response.candidates:
            candidate = response.candidates[0]
            finish_reason = getattr(candidate, 'finish_reason', None)
            
            if finish_reason == 1:  # SAFETY
                print("❌ BLOCCATO: finish_reason=1 (SAFETY)")
                if hasattr(candidate, 'safety_ratings'):
                    print("   Safety ratings:")
                    for rating in candidate.safety_ratings:
                        cat = getattr(rating.category, 'name', str(rating.category))
                        prob = getattr(rating.probability, 'name', str(rating.probability))
                        blocked = getattr(rating, 'blocked', False)
                        print(f"   - {cat}: {prob} (blocked={blocked})")
                
                # Controlla prompt_feedback
                if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                    pf = response.prompt_feedback
                    block_reason = getattr(pf, 'block_reason', None)
                    if block_reason:
                        block_reason_name = getattr(block_reason, 'name', str(block_reason))
                        print(f"   Prompt feedback block_reason: {block_reason_name}")
                
                return None
            else:
                text = response.text
                print(f"✅ SUCCESS: {text[:200]}")
                return text
        else:
            print("❌ Nessun candidato nella risposta")
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                pf = response.prompt_feedback
                block_reason = getattr(pf, 'block_reason', None)
                if block_reason:
                    block_reason_name = getattr(block_reason, 'name', str(block_reason))
                    print(f"   Prompt feedback block_reason: {block_reason_name}")
            return None
    except Exception as e:
        print(f"❌ ERRORE: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_gemini_with_system_instruction(prompt: str, model_name: str = "gemini-2.5-pro"):
    """
    Test 3: Con system_instruction e safety_settings nel costruttore (schema Gemini 3 completo)
    """
    print("\n" + "="*80)
    print("TEST 3: Con system_instruction + safety_settings nel costruttore")
    print("="*80)
    print(f"📝 Prompt: {prompt}")
    print(f"🤖 Model: {model_name}")
    
    try:
        system_instruction = "You are a helpful assistant. Respond clearly and factually to user questions."
        safety_settings = create_safety_settings(block_none=False)
        
        # CRITICAL: Pass system_instruction e safety_settings al costruttore (schema Gemini 3)
        model = genai.GenerativeModel(
            model_name,
            system_instruction=system_instruction,
            safety_settings=safety_settings
        )
        
        print(f"✅ Modello creato con system_instruction e safety_settings (BLOCK_ONLY_HIGH)")
        print(f"   System instruction: {system_instruction[:50]}...")
        
        response = model.generate_content(prompt)
        
        if response.candidates:
            candidate = response.candidates[0]
            finish_reason = getattr(candidate, 'finish_reason', None)
            
            if finish_reason == 1:  # SAFETY
                print("❌ BLOCCATO: finish_reason=1 (SAFETY)")
                if hasattr(candidate, 'safety_ratings'):
                    print("   Safety ratings:")
                    for rating in candidate.safety_ratings:
                        cat = getattr(rating.category, 'name', str(rating.category))
                        prob = getattr(rating.probability, 'name', str(rating.probability))
                        blocked = getattr(rating, 'blocked', False)
                        print(f"   - {cat}: {prob} (blocked={blocked})")
                
                # Controlla prompt_feedback
                if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                    pf = response.prompt_feedback
                    block_reason = getattr(pf, 'block_reason', None)
                    if block_reason:
                        block_reason_name = getattr(block_reason, 'name', str(block_reason))
                        print(f"   Prompt feedback block_reason: {block_reason_name}")
                
                return None
            else:
                text = response.text
                print(f"✅ SUCCESS: {text[:200]}")
                return text
        else:
            print("❌ Nessun candidato nella risposta")
            return None
    except Exception as e:
        print(f"❌ ERRORE: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_gemini_with_chat(prompt: str, model_name: str = "gemini-2.5-pro"):
    """
    Test 4: Con chat history (simula generate_with_context)
    """
    print("\n" + "="*80)
    print("TEST 4: Con chat history (simula generate_with_context)")
    print("="*80)
    print(f"📝 Prompt: {prompt}")
    print(f"🤖 Model: {model_name}")
    
    try:
        system_instruction = "You are a helpful assistant. Respond clearly and factually to user questions."
        safety_settings = create_safety_settings(block_none=False)
        
        # CRITICAL: Pass system_instruction e safety_settings al costruttore
        model = genai.GenerativeModel(
            model_name,
            system_instruction=system_instruction,
            safety_settings=safety_settings
        )
        
        print(f"✅ Modello creato con system_instruction e safety_settings")
        
        # Crea chat con history vuota
        chat = model.start_chat(history=[])
        
        # Invia messaggio
        response = chat.send_message(prompt)
        
        if response.candidates:
            candidate = response.candidates[0]
            finish_reason = getattr(candidate, 'finish_reason', None)
            
            if finish_reason == 1:  # SAFETY
                print("❌ BLOCCATO: finish_reason=1 (SAFETY)")
                if hasattr(candidate, 'safety_ratings'):
                    print("   Safety ratings:")
                    for rating in candidate.safety_ratings:
                        cat = getattr(rating.category, 'name', str(rating.category))
                        prob = getattr(rating.probability, 'name', str(rating.probability))
                        blocked = getattr(rating, 'blocked', False)
                        print(f"   - {cat}: {prob} (blocked={blocked})")
                
                return None
            else:
                text = response.text
                print(f"✅ SUCCESS: {text[:200]}")
                return text
        else:
            print("❌ Nessun candidato nella risposta")
            return None
    except Exception as e:
        print(f"❌ ERRORE: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Esegue tutti i test"""
    print("="*80)
    print("🧪 TEST STANDALONE GEMINI API - Schema Gemini 3")
    print("="*80)
    print(f"🔑 API Key: {'✅ Configurata' if GEMINI_API_KEY else '❌ Non trovata'}")
    
    # Prompt di test semplice
    prompt = "Parlami un po' di te"
    
    # Esegui tutti i test
    results = {}
    
    results['test1_basic'] = test_gemini_basic(prompt)
    results['test2_safety_block_only_high'] = test_gemini_with_safety_settings(prompt, block_none=False)
    results['test3_system_instruction'] = test_gemini_with_system_instruction(prompt)
    results['test4_chat'] = test_gemini_with_chat(prompt)
    
    # Riepilogo
    print("\n" + "="*80)
    print("📊 RIEPILOGO TEST")
    print("="*80)
    for test_name, result in results.items():
        status = "✅ SUCCESS" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    # Conta successi
    success_count = sum(1 for r in results.values() if r)
    total_count = len(results)
    print(f"\n✅ Successi: {success_count}/{total_count}")
    
    if success_count == 0:
        print("\n⚠️  Tutti i test sono falliti. Questo suggerisce un problema a livello infrastrutturale")
        print("   (richiesta allowlist per BLOCK_NONE) o un problema con l'API key/configurazione.")


if __name__ == "__main__":
    main()

