#!/usr/bin/env python3
"""
Script per debuggare la connessione MCP dopo autorizzazione OAuth
"""
import asyncio
import sys
import os
from pathlib import Path

# Aggiungi il path del backend
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from app.models.database import Integration, User
from app.core.config import settings
from app.api.integrations.mcp import _get_oauth_token_for_user, _get_mcp_client_for_integration
from app.core.mcp_client import MCPClient
import json

async def debug_mcp_connection():
    """Debug MCP connection after OAuth authorization"""
    
    # Database connection
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        # 1. Trova tutte le integrazioni MCP
        print("=" * 80)
        print("1. INTEGRAZIONI MCP NEL DATABASE")
        print("=" * 80)
        
        result = await db.execute(
            select(Integration)
            .where(Integration.service_type == "mcp_server")
            .where(Integration.enabled == True)
        )
        integrations = result.scalars().all()
        
        if not integrations:
            print("❌ Nessuna integrazione MCP trovata!")
            return
        
        for integration in integrations:
            print(f"\n📦 Integration ID: {integration.id}")
            print(f"   Tenant ID: {integration.tenant_id}")
            print(f"   User ID: {integration.user_id}")
            print(f"   Enabled: {integration.enabled}")
            
            session_metadata = integration.session_metadata or {}
            server_url = session_metadata.get("server_url", "")
            print(f"   Server URL: {server_url}")
            
            oauth_credentials = session_metadata.get("oauth_credentials", {})
            print(f"   OAuth Credentials Keys: {list(oauth_credentials.keys())}")
            
            oauth_user_emails = session_metadata.get("oauth_user_emails", {})
            print(f"   OAuth User Emails: {oauth_user_emails}")
            
            # 2. Per ogni integrazione, trova gli utenti associati
            if integration.user_id:
                print(f"\n   👤 User-specific integration:")
                user_result = await db.execute(
                    select(User).where(User.id == integration.user_id)
                )
                user = user_result.scalar_one_or_none()
                if user:
                    print(f"      User Email: {user.email}")
                    print(f"      User ID: {user.id}")
                    
                    # 3. Prova a recuperare OAuth token
                    print(f"\n   🔑 Recupero OAuth Token:")
                    try:
                        oauth_token = _get_oauth_token_for_user(integration, user)
                        if oauth_token:
                            print(f"      ✅ Token recuperato (length: {len(oauth_token)})")
                            print(f"      Token preview: {oauth_token[:30]}...")
                        else:
                            print(f"      ❌ Token non trovato o non valido")
                            print(f"      Verifica che l'utente abbia completato l'autorizzazione OAuth")
                    except Exception as e:
                        print(f"      ❌ Errore nel recupero token: {e}")
                    
                    # 4. Prova a creare MCP client
                    print(f"\n   🔌 Creazione MCP Client:")
                    try:
                        client = _get_mcp_client_for_integration(integration, current_user=user)
                        print(f"      ✅ Client creato")
                        print(f"      Base URL: {client.base_url}")
                        print(f"      OAuth Token presente: {bool(client.oauth_token)}")
                        
                        # 5. Prova a listare tools
                        print(f"\n   🛠️  Lista Tools:")
                        try:
                            tools = await client.list_tools()
                            print(f"      ✅ Tools recuperati: {len(tools)}")
                            if tools:
                                print(f"      Primi 3 tools:")
                                for tool in tools[:3]:
                                    print(f"         - {tool.get('name', 'Unknown')}")
                        except Exception as e:
                            print(f"      ❌ Errore nel listare tools: {e}")
                            import traceback
                            traceback.print_exc()
                            
                    except Exception as e:
                        print(f"      ❌ Errore nella creazione client: {e}")
                        import traceback
                        traceback.print_exc()
            else:
                print(f"\n   🌐 Global integration (no user_id)")
        
        # 6. Test connessione diretta al server MCP
        print("\n" + "=" * 80)
        print("2. TEST CONNESSIONE DIRETTA AL SERVER MCP")
        print("=" * 80)
        
        if integrations:
            integration = integrations[0]
            session_metadata = integration.session_metadata or {}
            server_url = session_metadata.get("server_url", "")
            
            if server_url:
                print(f"\n🔗 Test connessione a: {server_url}")
                
                # Test senza OAuth token (per vedere se il server risponde)
                try:
                    test_client = MCPClient(base_url=server_url, use_auth_token=False)
                    print(f"   ✅ Client creato (senza token)")
                    print(f"   Base URL finale: {test_client.base_url}")
                    
                    # Prova list_tools (potrebbe fallire senza OAuth, ma vediamo l'errore)
                    try:
                        tools = await test_client.list_tools()
                        print(f"   ✅ list_tools() riuscito: {len(tools)} tools")
                    except Exception as e:
                        print(f"   ⚠️  list_tools() fallito (atteso senza OAuth): {e}")
                        
                except Exception as e:
                    print(f"   ❌ Errore nella creazione client: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("   ❌ Nessun server_url trovato nell'integrazione")
    
    await engine.dispose()

if __name__ == "__main__":
    print("🔍 Debug MCP Connection")
    print("=" * 80)
    asyncio.run(debug_mcp_connection())

