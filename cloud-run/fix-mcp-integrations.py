#!/usr/bin/env python3
"""
Script per verificare e correggere le integrazioni MCP con URL localhost o vuoti
"""

import os
import sys
import asyncio
import httpx
import json
from typing import Dict, Any, Optional, List

BACKEND_URL = os.getenv('BACKEND_URL', 'https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app')
GOOGLE_WORKSPACE_MCP_URL = os.getenv('GOOGLE_WORKSPACE_MCP_URL', 'https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app')

async def fix_mcp_integrations():
    """Verifica e corregge le integrazioni MCP con URL non validi"""
    
    print("🔍 Verifica e Correzione Integrazioni MCP")
    print("=" * 80)
    print()
    
    # 0. Crea admin user se necessario
    print("0️⃣ Login...")
    email = os.getenv('TEST_EMAIL', 'admin@example.com').strip()
    password = os.getenv('TEST_PASSWORD', 'admin123').strip()
    
    if len(sys.argv) >= 3:
        email = sys.argv[1].strip()
        password = sys.argv[2].strip()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Create admin user
            init_response = await client.post(
                f"{BACKEND_URL}/api/init/admin",
                json={
                    "email": email,
                    "password": password,
                    "name": "Admin User"
                }
            )
            init_response.raise_for_status()
            print(f"✅ Admin user creato/aggiornato: {email}")
            print()
        except Exception as e:
            print(f"⚠️  Errore nella creazione admin (potrebbe già esistere): {e}")
            print()
        
        # 1. Login
        print("1️⃣ Login per ottenere token JWT...")
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
            print()
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
        except Exception as e:
            print(f"❌ Errore nel login: {e}")
            if hasattr(e, 'response'):
                print(f"   Response: {e.response.text[:500]}")
            return False
        
        # 2. Lista integrazioni MCP
        print("2️⃣ Recupero integrazioni MCP esistenti...")
        try:
            integrations_response = await client.get(
                f"{BACKEND_URL}/api/integrations/mcp/integrations",
                headers=headers
            )
            integrations_response.raise_for_status()
            integrations_data = integrations_response.json()
            integrations = integrations_data.get("integrations", [])
            
            print(f"✅ Trovate {len(integrations)} integrazione/i MCP")
            print()
            
            if not integrations:
                print("   ℹ️  Nessuna integrazione MCP trovata. Niente da correggere.")
                return True
            
            # 3. Identifica integrazioni con problemi
            print("3️⃣ Analisi integrazioni...")
            problematic_integrations = []
            valid_integrations = []
            
            for integration in integrations:
                integration_id = integration.get("id")
                server_url = integration.get("server_url", "")
                name = integration.get("name", "Unknown")
                
                # Check if URL is problematic
                is_problematic = (
                    not server_url or
                    "localhost" in server_url.lower() or
                    "127.0.0.1" in server_url or
                    "host.docker.internal" in server_url.lower()
                )
                
                if is_problematic:
                    problematic_integrations.append({
                        "id": integration_id,
                        "name": name,
                        "server_url": server_url,
                        "current_url": server_url or "(vuoto)"
                    })
                    print(f"   ⚠️  Problema trovato:")
                    print(f"      ID: {integration_id}")
                    print(f"      Name: {name}")
                    print(f"      URL attuale: {server_url or '(vuoto)'}")
                    print()
                else:
                    valid_integrations.append(integration)
                    print(f"   ✅ OK:")
                    print(f"      ID: {integration_id}")
                    print(f"      Name: {name}")
                    print(f"      URL: {server_url}")
                    print()
            
            if not problematic_integrations:
                print("✅ Tutte le integrazioni hanno URL validi!")
                return True
            
            # 4. Correggi integrazioni problematiche
            print(f"4️⃣ Correzione {len(problematic_integrations)} integrazione/i...")
            print()
            
            # For each problematic integration, we need to:
            # 1. Delete it
            # 2. Recreate it with correct URL
            
            # But first, let's check if we can update the URL directly
            # Actually, looking at the API, there's no endpoint to update server_url
            # So we need to delete and recreate
            
            corrected_count = 0
            failed_count = 0
            
            for integration in problematic_integrations:
                integration_id = integration["id"]
                name = integration["name"]
                
                print(f"   🔧 Correggendo integrazione {integration_id} ({name})...")
                
                try:
                    # Delete the problematic integration
                    delete_response = await client.delete(
                        f"{BACKEND_URL}/api/integrations/mcp/integrations/{integration_id}",
                        headers=headers
                    )
                    delete_response.raise_for_status()
                    print(f"      ✅ Integrazione eliminata")
                    
                    # Recreate with correct URL
                    # Use Google Workspace MCP URL as default
                    correct_url = GOOGLE_WORKSPACE_MCP_URL
                    
                    connect_response = await client.post(
                        f"{BACKEND_URL}/api/integrations/mcp/connect",
                        headers=headers,
                        json={
                            "server_url": correct_url,
                            "name": name
                        }
                    )
                    connect_response.raise_for_status()
                    connect_data = connect_response.json()
                    new_integration_id = connect_data.get("integration_id")
                    
                    print(f"      ✅ Integrazione ricreata con ID: {new_integration_id}")
                    print(f"      ✅ URL corretto: {correct_url}")
                    corrected_count += 1
                    print()
                    
                except Exception as e:
                    print(f"      ❌ Errore nella correzione: {e}")
                    if hasattr(e, 'response'):
                        print(f"         Status: {e.response.status_code}")
                        print(f"         Response: {e.response.text[:500]}")
                    failed_count += 1
                    print()
            
            # 5. Verifica finale
            print("5️⃣ Verifica finale...")
            try:
                integrations_response = await client.get(
                    f"{BACKEND_URL}/api/integrations/mcp/integrations",
                    headers=headers
                )
                integrations_response.raise_for_status()
                integrations_data = integrations_response.json()
                final_integrations = integrations_data.get("integrations", [])
                
                print(f"✅ Trovate {len(final_integrations)} integrazione/i MCP")
                
                problematic_final = []
                for integration in final_integrations:
                    server_url = integration.get("server_url", "")
                    if not server_url or "localhost" in server_url.lower() or "127.0.0.1" in server_url:
                        problematic_final.append(integration)
                
                if problematic_final:
                    print(f"   ⚠️  Ancora {len(problematic_final)} integrazione/i con problemi:")
                    for integration in problematic_final:
                        print(f"      - {integration.get('name')}: {integration.get('server_url') or '(vuoto)'}")
                else:
                    print(f"   ✅ Tutte le integrazioni hanno URL validi!")
                print()
                
            except Exception as e:
                print(f"❌ Errore nella verifica finale: {e}")
                print()
            
            print("=" * 80)
            print(f"✅ Correzione completata:")
            print(f"   Corrette: {corrected_count}")
            print(f"   Fallite: {failed_count}")
            print(f"   Totali problematiche: {len(problematic_integrations)}")
            
            return failed_count == 0
            
        except Exception as e:
            print(f"❌ Errore generale: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = asyncio.run(fix_mcp_integrations())
    sys.exit(0 if success else 1)

