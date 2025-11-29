#!/usr/bin/env python3
"""
Test script per verificare il tool mcp_get_gmail_messages_content_batch via API
"""

import os
import sys
import asyncio
import httpx
import json
from typing import Dict, Any, List, Optional

BACKEND_URL = os.getenv('BACKEND_URL', 'https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app')

async def test_gmail_batch_tool_via_api():
    """Test del tool mcp_get_gmail_messages_content_batch via API"""
    
    print("🔍 Test del tool mcp_get_gmail_messages_content_batch via API")
    print("=" * 80)
    print()
    
    # 0. Crea admin user se necessario
    print("0️⃣ Creazione/aggiornamento admin user...")
    email = os.getenv('TEST_EMAIL', 'admin@example.com').strip()
    password = os.getenv('TEST_PASSWORD', 'admin123').strip()
    
    if len(sys.argv) >= 3:
        email = sys.argv[1].strip()
        password = sys.argv[2].strip()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            init_response = await client.post(
                f"{BACKEND_URL}/api/init/admin",
                json={
                    "email": email,
                    "password": password,
                    "name": "Test Admin"
                }
            )
            init_response.raise_for_status()
            init_data = init_response.json()
            print(f"✅ Admin user creato/aggiornato: {init_data.get('email')}")
            print()
        except Exception as e:
            print(f"⚠️  Errore nella creazione admin (potrebbe già esistere): {e}")
            print()
        
        # 1. Login per ottenere token
        print("1️⃣ Login per ottenere token JWT...")
        print(f"   Email: {email}")
        print(f"   Password: {'*' * len(password)}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            login_response = await client.post(
                f"{BACKEND_URL}/api/v1/auth/login",
                json={"email": email, "password": password}
            )
            login_response.raise_for_status()
            login_data = login_response.json()
            access_token = login_data.get("access_token")
            
            if not access_token:
                print("❌ Token non ricevuto dal login")
                return False
            
            print(f"✅ Login riuscito")
            print(f"   Token length: {len(access_token)}")
            print()
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # 2. Ottieni informazioni utente
            print("2️⃣ Recupero informazioni utente...")
            try:
                user_response = await client.get(
                    f"{BACKEND_URL}/api/v1/users/me",
                    headers=headers
                )
                user_response.raise_for_status()
                user_data = user_response.json()
                print(f"✅ Utente: {user_data.get('email')}")
                print()
            except Exception as e:
                print(f"⚠️  Errore nel recupero utente: {e}")
                print()
            
            # 3. Lista integrazioni MCP
            print("3️⃣ Recupero integrazioni MCP...")
            try:
                integrations_response = await client.get(
                    f"{BACKEND_URL}/api/integrations/mcp/integrations",
                    headers=headers
                )
                integrations_response.raise_for_status()
                integrations_data = integrations_response.json()
                
                # La risposta potrebbe essere una lista direttamente o un oggetto con 'integrations'
                if isinstance(integrations_data, list):
                    integrations = integrations_data
                elif isinstance(integrations_data, dict) and 'integrations' in integrations_data:
                    integrations = integrations_data['integrations']
                else:
                    integrations = []
                
                if not integrations or len(integrations) == 0:
                    print("❌ Nessuna integrazione MCP trovata")
                    print("   Connetti un server MCP dalla pagina Integrations nel frontend")
                    return False
                
                print(f"✅ Trovate {len(integrations)} integrazione/i MCP:")
                for integration in integrations:
                    if isinstance(integration, dict):
                        print(f"   - ID: {integration.get('id')}")
                        metadata = integration.get('session_metadata', {})
                        if isinstance(metadata, dict):
                            print(f"     Server URL: {metadata.get('server_url', 'N/A')}")
                        print(f"     Enabled: {integration.get('enabled')}")
                    else:
                        print(f"   - {integration}")
                
                integration_id = integrations[0].get('id') if isinstance(integrations[0], dict) else None
                if not integration_id:
                    print("❌ Impossibile ottenere integration_id")
                    return False
                print()
            except Exception as e:
                print(f"❌ Errore nel recupero integrazioni: {e}")
                return False
            
            # 4. Lista tool disponibili dal server MCP
            print("4️⃣ Recupero tool disponibili dal server MCP...")
            try:
                tools_response = await client.get(
                    f"{BACKEND_URL}/api/integrations/mcp/{integration_id}/tools",
                    headers=headers
                )
                tools_response.raise_for_status()
                tools_data = tools_response.json()
                tools = tools_data.get('tools', [])
                
                print(f"✅ Trovati {len(tools)} tool disponibili")
                
                # Cerca tool Gmail
                gmail_tools = [t for t in tools if 'gmail' in t.get('name', '').lower()]
                print(f"   Tool Gmail trovati: {len(gmail_tools)}")
                
                batch_tools = [t for t in gmail_tools if 'batch' in t.get('name', '').lower()]
                print(f"   Tool batch Gmail trovati: {len(batch_tools)}")
                
                if batch_tools:
                    print("   ⭐ Tool batch trovati:")
                    for tool in batch_tools:
                        tool_name = tool.get('name', 'Unknown')
                        print(f"      - {tool_name}")
                        if 'inputSchema' in tool:
                            schema = tool['inputSchema']
                            if 'properties' in schema:
                                props = schema['properties']
                                print(f"        Parametri: {list(props.keys())}")
                                if 'message_ids' in props:
                                    print(f"        message_ids type: {props['message_ids']}")
                else:
                    print("   ⚠️  Nessun tool batch trovato")
                    print("   Tool Gmail disponibili:")
                    for tool in gmail_tools[:10]:  # Mostra primi 10
                        print(f"      - {tool.get('name', 'Unknown')}")
                
                print()
            except Exception as e:
                print(f"⚠️  Errore nel recupero tool: {e}")
                print("   (Potrebbe essere normale per OAuth 2.1 servers)")
                print()
            
            # 5. Test chiamata tool diretto
            print("5️⃣ Test chiamata tool mcp_get_gmail_messages_content_batch...")
            message_ids = ["19a93674987a96f7", "199e7cb12c09945f", "199c0b0a8c2f12f9"]
            print(f"   Message IDs: {message_ids}")
            
            try:
                # Chiama il tool via API
                tool_call_response = await client.post(
                    f"{BACKEND_URL}/api/tools/call",
                    headers=headers,
                    json={
                        "tool_name": "mcp_get_gmail_messages_content_batch",
                        "parameters": {
                            "message_ids": message_ids
                        }
                    }
                )
                
                print(f"   Status code: {tool_call_response.status_code}")
                
                if tool_call_response.status_code == 200:
                    result = tool_call_response.json()
                    print(f"✅ Tool chiamato con successo!")
                    print(f"   Result type: {type(result)}")
                    if isinstance(result, dict):
                        print(f"   Result keys: {list(result.keys())}")
                        if "error" in result:
                            print(f"   ❌ Error: {result.get('error')}")
                        if "success" in result:
                            print(f"   Success: {result.get('success')}")
                        if "result" in result:
                            tool_result = result.get('result', {})
                            if isinstance(tool_result, dict):
                                if "isError" in tool_result:
                                    print(f"   ⚠️  Is Error: {tool_result.get('isError')}")
                                if "content" in tool_result:
                                    content = tool_result.get('content', '')
                                    print(f"   Content preview: {str(content)[:500]}")
                else:
                    error_text = tool_call_response.text
                    print(f"❌ Tool chiamata fallita: {tool_call_response.status_code}")
                    print(f"   Error: {error_text[:500]}")
                    
            except Exception as e:
                print(f"❌ Errore nella chiamata tool: {e}")
                import traceback
                traceback.print_exc()
            
            print()
            print("=" * 80)
            print("✅ Test completato")
            
            return True
            
        except httpx.HTTPStatusError as e:
            print(f"❌ HTTP Error: {e.response.status_code}")
            print(f"   Response: {e.response.text[:500]}")
            return False
        except Exception as e:
            print(f"❌ Errore: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = asyncio.run(test_gmail_batch_tool_via_api())
    sys.exit(0 if success else 1)

