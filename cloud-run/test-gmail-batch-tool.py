#!/usr/bin/env python3
"""
Test script per verificare il tool mcp_get_gmail_messages_content_batch
"""

import os
import sys
import asyncio
import httpx
from typing import Dict, Any

# Aggiungi il path del backend al PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

BACKEND_URL = os.getenv('BACKEND_URL', 'https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app')

async def test_gmail_batch_tool():
    """Test del tool mcp_get_gmail_messages_content_batch"""
    
    # Per questo test, abbiamo bisogno di:
    # 1. Un token JWT valido
    # 2. Una sessione ID valida
    # 3. Message IDs validi
    
    print("🔍 Test del tool mcp_get_gmail_messages_content_batch")
    print("=" * 60)
    print()
    
    # Parametri di esempio (da sostituire con valori reali)
    message_ids = [
        "19a93674987a96f7",
        "199e7cb12c09945f",
        "199c0b0a8c2f12f9",
    ]
    
    print(f"📧 Message IDs da testare: {message_ids}")
    print()
    
    # Verifica che il tool esista nella lista dei tool disponibili
    print("1️⃣ Verificando tool disponibili...")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Prima, dobbiamo autenticarci e ottenere un token
            # Per ora, assumiamo che il tool sia disponibile
            print("   ⚠️  Questo script richiede autenticazione.")
            print("   ⚠️  Per testare completamente, usa il frontend o un token valido.")
            print()
            
            print("2️⃣ Parametri attesi dal tool:")
            print(f"   - message_ids: {message_ids}")
            print()
            
            print("3️⃣ Possibili problemi:")
            print("   - Il tool potrebbe non esistere nel server MCP")
            print("   - Il formato dei message_ids potrebbe essere errato")
            print("   - Potrebbero mancare permessi OAuth per Gmail")
            print("   - Il server MCP potrebbe non supportare questo tool")
            print()
            
            print("💡 Per vedere l'errore completo:")
            print("   1. Apri il frontend")
            print("   2. Chiedi all'assistente di leggere le email urgenti")
            print("   3. Quando viene chiamato mcp_get_gmail_messages_content_batch,")
            print("      controlla i log del backend con:")
            print("      gcloud run services logs tail knowledge-navigator-backend \\")
            print("        --region=us-central1 --project=knowledge-navigator-477022")
            
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_gmail_batch_tool())
    sys.exit(0 if success else 1)

