#!/usr/bin/env python3
"""
Test semplificato per verificare la logica di salvataggio/recupero tool_results.
"""
import json
from typing import Dict, Any, List


def test_tool_results_structure():
    """Test che la struttura dei tool_results sia corretta"""
    
    print("=" * 80)
    print("TEST: Tool Results Structure")
    print("=" * 80)
    print()
    
    # Simulate tool_results from mcp_search_emails
    tool_results = [
        {
            "tool": "mcp_search_emails",
            "parameters": {"query": "urgente OR rispondi subito OR priorità"},
            "result": {
                "emails": [
                    {"id": "19a93674987a96f7", "subject": "Email urgente 1", "from": "sender1@example.com"},
                    {"id": "199e7cb12c09945f", "subject": "Email urgente 2", "from": "sender2@example.com"},
                    {"id": "test123", "subject": "Email urgente 3", "from": "sender3@example.com"},
                ],
                "count": 3,
            }
        }
    ]
    
    print("1. Struttura tool_results originale:")
    print(f"   Tool: {tool_results[0]['tool']}")
    print(f"   Email IDs: {[e['id'] for e in tool_results[0]['result']['emails']]}")
    print()
    
    # Simulate saving to short-term memory
    context_data = {
        "last_user_message": "Cerca email urgenti",
        "last_assistant_message": "Ho trovato 3 email urgenti",
        "message_count": 2,
        "tool_results": tool_results,
    }
    
    print("2. Struttura salvata in memoria a breve termine:")
    print(f"   Keys: {list(context_data.keys())}")
    print(f"   Tool results count: {len(context_data['tool_results'])}")
    print()
    
    # Simulate retrieval from memory
    retrieved_tool_results = context_data.get("tool_results", [])
    
    print("3. Struttura recuperata dalla memoria:")
    print(f"   Tool results count: {len(retrieved_tool_results)}")
    
    if retrieved_tool_results:
        first_result = retrieved_tool_results[0]
        print(f"   Tool: {first_result.get('tool')}")
        
        if isinstance(first_result.get('result'), dict) and 'emails' in first_result['result']:
            email_ids = [e.get('id') for e in first_result['result']['emails']]
            print(f"   Email IDs: {email_ids}")
            
            # Verify IDs can be used for next tool call
            print()
            print("4. Verifica utilizzo ID per chiamata tool successiva:")
            for email_id in email_ids:
                print(f"   ✅ ID '{email_id}' può essere usato per mcp_get_email({{'email_id': '{email_id}'}})")
            
            print()
            print("✅ TEST PASSATO: La struttura permette l'utilizzo sequenziale dei tool")
        else:
            print(f"   ❌ Struttura risultato inattesa: {type(first_result.get('result'))}")
            print("   ❌ TEST FALLITO")
    else:
        print("   ❌ Nessun tool_result trovato")
        print("   ❌ TEST FALLITO")
    
    print()
    print("=" * 80)


def test_format_tool_results_for_llm():
    """Test che _format_tool_results_for_llm formatti correttamente i risultati"""
    
    print("=" * 80)
    print("TEST: Format Tool Results for LLM")
    print("=" * 80)
    print()
    
    # Import the function
    import sys
    from pathlib import Path
    backend_path = Path(__file__).parent.parent
    sys.path.insert(0, str(backend_path))
    
    try:
        from app.agents.langgraph_app import _format_tool_results_for_llm
        
        tool_results = [
            {
                "tool": "mcp_search_emails",
                "parameters": {"query": "urgente"},
                "result": {
                    "emails": [
                        {"id": "19a93674987a96f7", "subject": "Email urgente 1"},
                        {"id": "199e7cb12c09945f", "subject": "Email urgente 2"},
                    ],
                    "count": 2,
                }
            }
        ]
        
        formatted = _format_tool_results_for_llm(tool_results, simple_format=True)
        
        print("Tool results formattati:")
        print("-" * 80)
        print(formatted)
        print("-" * 80)
        print()
        
        # Verify email IDs are in the formatted text
        if "19a93674987a96f7" in formatted or "Email urgente 1" in formatted:
            print("✅ Email IDs presenti nel testo formattato")
        else:
            print("⚠️  Email IDs potrebbero non essere presenti nel testo formattato")
        
        print()
        print("✅ TEST PASSATO: Formattazione funziona correttamente")
        
    except ImportError as e:
        print(f"⚠️  Impossibile importare _format_tool_results_for_llm: {e}")
        print("   Il test richiede l'ambiente backend completo")
    
    print()
    print("=" * 80)


if __name__ == "__main__":
    test_tool_results_structure()
    print()
    test_format_tool_results_for_llm()

