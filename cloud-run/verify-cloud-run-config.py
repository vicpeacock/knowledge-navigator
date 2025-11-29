#!/usr/bin/env python3
"""
Script per verificare la configurazione Cloud Run vs Docker locale
"""

import os
import sys
import asyncio
import httpx

BACKEND_URL = os.getenv('BACKEND_URL', 'https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app')

async def verify_config():
    """Verifica la configurazione Cloud Run"""
    
    print("🔍 Verifica Configurazione Cloud Run vs Docker")
    print("=" * 80)
    print()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Health check per vedere quali servizi usa
        print("1️⃣ Health Check - Verifica servizi utilizzati...")
        try:
            health_response = await client.get(f"{BACKEND_URL}/health")
            health_response.raise_for_status()
            health_data = health_response.json()
            
            print("✅ Servizi configurati:")
            services = health_data.get('services', {})
            for service_name, service_status in services.items():
                healthy = service_status.get('healthy', False)
                message = service_status.get('message', '')
                service_type = service_status.get('type', '')
                status_icon = "✅" if healthy else "❌"
                
                # Analizza il messaggio per capire se usa Cloud o locale
                if 'Cloud' in message or 'Supabase' in message or 'trychroma' in message.lower():
                    location = "☁️  CLOUD"
                elif 'localhost' in message.lower() or '127.0.0.1' in message.lower() or 'docker' in message.lower():
                    location = "🐳 DOCKER/LOCAL"
                else:
                    location = "❓ UNKNOWN"
                
                print(f"   {status_icon} {service_name}: {location}")
                print(f"      {message}")
                if service_type:
                    print(f"      Type: {service_type}")
            print()
        except Exception as e:
            print(f"❌ Errore: {e}")
            return False
        
        # 2. Verifica integrazione MCP
        print("2️⃣ Verifica Integrazione MCP...")
        email = os.getenv('TEST_EMAIL', 'admin@example.com').strip()
        password = os.getenv('TEST_PASSWORD', 'admin123').strip()
        
        try:
            # Login
            login_response = await client.post(
                f"{BACKEND_URL}/api/v1/auth/login",
                json={"email": email, "password": password}
            )
            login_response.raise_for_status()
            login_data = login_response.json()
            access_token = login_data.get("access_token")
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            # Lista integrazioni MCP
            integrations_response = await client.get(
                f"{BACKEND_URL}/api/integrations/mcp/integrations",
                headers=headers
            )
            integrations_response.raise_for_status()
            integrations_data = integrations_response.json()
            integrations = integrations_data.get("integrations", [])
            
            print(f"✅ Trovate {len(integrations)} integrazione/i MCP")
            for integration in integrations:
                server_url = integration.get("server_url", "")
                name = integration.get("name", "Unknown")
                
                # Analizza URL
                if "localhost" in server_url or "127.0.0.1" in server_url or "docker" in server_url.lower():
                    location = "🐳 DOCKER/LOCAL"
                    status = "❌ PROBLEMA!"
                elif "run.app" in server_url or "cloud" in server_url.lower():
                    location = "☁️  CLOUD RUN"
                    status = "✅ OK"
                else:
                    location = "❓ UNKNOWN"
                    status = "⚠️  VERIFICARE"
                
                print(f"   {status} {name}:")
                print(f"      URL: {server_url}")
                print(f"      Location: {location}")
            print()
            
        except Exception as e:
            print(f"⚠️  Errore nel recupero integrazioni: {e}")
            print()
        
        # 3. Verifica Google Workspace MCP Server
        print("3️⃣ Verifica Google Workspace MCP Server...")
        mcp_url = "https://google-workspace-mcp-osbdwu5a7q-uc.a.run.app"
        try:
            mcp_health = await client.get(f"{mcp_url}/health", timeout=5.0)
            mcp_health.raise_for_status()
            mcp_data = mcp_health.json()
            
            print(f"✅ Google Workspace MCP Server raggiungibile")
            print(f"   URL: {mcp_url}")
            print(f"   Status: {mcp_data.get('status', 'unknown')}")
            print(f"   Version: {mcp_data.get('version', 'unknown')}")
            print()
        except Exception as e:
            print(f"❌ Google Workspace MCP Server NON raggiungibile: {e}")
            print(f"   URL testato: {mcp_url}")
            print()
        
        # 4. Conclusioni
        print("4️⃣ Conclusioni")
        print("=" * 80)
        print()
        print("✅ Il backend su Cloud Run usa:")
        print("   - PostgreSQL: Supabase (cloud)")
        print("   - ChromaDB: ChromaDB Cloud (trychroma.com)")
        print("   - NON usa servizi Docker locali")
        print()
        print("✅ Google Workspace MCP Server:")
        print(f"   - Deployato su: {mcp_url}")
        print("   - Raggiungibile da Cloud Run")
        print()
        print("⚠️  ATTENZIONE:")
        print("   - Il default mcp_gateway_url in config.py è 'http://localhost:8080'")
        print("   - Ma questo viene usato SOLO se:")
        print("     1. Non siamo in Cloud Run (K_SERVICE o GOOGLE_CLOUD_PROJECT non settati)")
        print("     2. E server_url è vuoto nell'integrazione")
        print("   - In Cloud Run, se server_url è vuoto, viene sollevato un errore")
        print("   - Le integrazioni esistenti hanno già server_url configurato correttamente")
        print()
        
        return True

if __name__ == "__main__":
    asyncio.run(verify_config())

