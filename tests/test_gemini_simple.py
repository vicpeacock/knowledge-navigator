#!/usr/bin/env python3
"""
Test semplicissimo: una richiesta e una risposta a Gemini.
Nessun test sui safety settings, solo vedere se Gemini risponde.
"""
import os
import sys

# Verifica che google-generativeai sia installato
try:
    import google.generativeai as genai
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

# Prompt semplice
prompt = "Ciao, come stai?"

# Prova diversi modelli
models_to_try = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-pro"]

for model_name in models_to_try:
    print("="*80)
    print(f"🧪 TEST SEMPLICE GEMINI - {model_name}")
    print("="*80)
    print(f"📝 Prompt: {prompt}")
    print(f"🤖 Model: {model_name}")
    print()

    try:
        # Crea modello e genera risposta
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        
        # Mostra risposta
        if response.candidates:
            candidate = response.candidates[0]
            finish_reason = getattr(candidate, 'finish_reason', None)
            
            if finish_reason == 1:  # SAFETY
                print("❌ BLOCCATO: finish_reason=1 (SAFETY)")
                print()
            else:
                text = response.text
                print(f"✅ RISPOSTA:")
                print(f"{text}")
                print()
                break  # Se funziona, esci dal loop
        else:
            print("❌ Nessun candidato nella risposta")
            print()
            
    except Exception as e:
        print(f"❌ ERRORE: {e}")
        print()
        continue  # Prova il prossimo modello

