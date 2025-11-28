#!/usr/bin/env python3
"""
Test semplice per Vertex AI - verifica connessione base
"""
import os
import sys

# Aggiungi backend al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from app.core.config import settings
from app.core.vertex_ai_client import VertexAIClient

def test_vertex_ai_simple():
    """Test semplice di Vertex AI con una richiesta base"""
    
    print("=" * 80)
    print("🧪 Test Vertex AI - Richiesta Semplice")
    print("=" * 80)
    
    # Verifica configurazione
    if not settings.google_cloud_project_id:
        print("❌ Errore: GOOGLE_CLOUD_PROJECT_ID non configurato")
        print("   Configura in .env: GOOGLE_CLOUD_PROJECT_ID=your-project-id")
        return False
    
    if not settings.gemini_model:
        print("❌ Errore: GEMINI_MODEL non configurato")
        return False
    
    print(f"✅ Configurazione:")
    print(f"   Project ID: {settings.google_cloud_project_id}")
    print(f"   Location: {settings.google_cloud_location}")
    print(f"   Model: {settings.gemini_model}")
    print()
    
    try:
        # Inizializza client
        print("🔧 Inizializzazione Vertex AI client...")
        client = VertexAIClient(model=settings.gemini_model)
        print("✅ Client inizializzato")
        print()
        
        # Test semplice
        print("📤 Invio richiesta: 'Parlami di te'")
        import asyncio
        
        async def test():
            response = await client.generate(
                prompt="Parlami di te",
                context=None,
                system=None,
            )
            return response
        
        result = asyncio.run(test())
        
        print("✅ Risposta ricevuta:")
        print("-" * 80)
        print(result.get("response", "Nessuna risposta"))
        print("-" * 80)
        print()
        
        if result.get("response"):
            print("✅ Test completato con successo!")
            return True
        else:
            print("❌ Test fallito: nessuna risposta")
            return False
    
    except ImportError as e:
        print(f"❌ Errore di importazione: {e}")
        print("   Installa con: pip install google-genai")
        return False
    except ValueError as e:
        print(f"❌ Errore di configurazione: {e}")
        return False
    except Exception as e:
        print(f"❌ Errore durante il test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_vertex_ai_simple()
    sys.exit(0 if success else 1)
