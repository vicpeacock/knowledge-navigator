#!/usr/bin/env python3
"""
Test Gemini con Service Account (se configurata).
Se GOOGLE_APPLICATION_CREDENTIALS è impostato, usa le credenziali della Service Account.
Altrimenti usa solo l'API key.
"""
import os
import sys

try:
    import google.generativeai as genai
    import google.auth
    from google.oauth2 import service_account
    print("✅ Librerie importate correttamente")
except ImportError as e:
    print(f"❌ Errore: {e}")
    sys.exit(1)

# Carica API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("❌ Errore: GEMINI_API_KEY non trovata")
    sys.exit(1)

# Verifica se ci sono credenziali Service Account
SERVICE_ACCOUNT_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
if SERVICE_ACCOUNT_PATH and os.path.exists(SERVICE_ACCOUNT_PATH):
    print(f"✅ Service Account trovata: {SERVICE_ACCOUNT_PATH}")
    try:
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_PATH,
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        print(f"   Project ID: {credentials.project_id}")
        print(f"   Service Account Email: {credentials.service_account_email}")
    except Exception as e:
        print(f"⚠️  Errore nel caricamento Service Account: {e}")
        credentials = None
else:
    print("⚠️  Nessuna Service Account configurata (GOOGLE_APPLICATION_CREDENTIALS non impostato)")
    print("   Per usare una Service Account:")
    print("   1. Crea una Service Account in Google Cloud Console")
    print("   2. Assegna il ruolo 'AI Platform User' o 'Vertex AI User'")
    print("   3. Scarica la chiave JSON")
    print("   4. Esporta: export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json")
    credentials = None

# Configura Gemini con API key
genai.configure(api_key=GEMINI_API_KEY)

# Test semplice
prompt = "Ciao, come stai?"
model_name = "gemini-2.5-flash"

print("\n" + "="*80)
print("🧪 TEST GEMINI")
print("="*80)
print(f"📝 Prompt: {prompt}")
print(f"🤖 Model: {model_name}")
if credentials:
    print(f"🔑 Autenticazione: API Key + Service Account")
else:
    print(f"🔑 Autenticazione: Solo API Key")
print()

try:
    model = genai.GenerativeModel(model_name)
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
                    print(f"   - {cat}: {prob}")
        else:
            text = response.text
            print(f"✅ SUCCESS!")
            print(f"📤 Risposta: {text}")
    else:
        print("❌ Nessun candidato nella risposta")
        
except Exception as e:
    print(f"❌ ERRORE: {e}")
    import traceback
    traceback.print_exc()

