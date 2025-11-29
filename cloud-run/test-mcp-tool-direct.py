#!/usr/bin/env python3
"""
Script per testare direttamente la chiamata di un tool MCP con OAuth token
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
from app.api.integrations.mcp import _get_mcp_client_for_integration
from app.services.oauth_token_manager import OAuthTokenManager
from app.core.mcp_client import MCPClient
import json

async def test_mcp_tool():
    """Test chiamata tool MCP con OAuth token"""
    
    # Database connection
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as db:
        print("=" * 80)
        print("TEST CHIAMATA TOOL MCP CON OAUTH TOKEN")
        print("=" * 80)
        print()
        
        # 1. Trova integrazione MCP per utente
        print("1. Ricerca integrazione MCP...")
        
        # Chiedi email utente
        user_email = input("Email utente: ").strip()
        
        # Trova utente
        user_result = await db.execute(
            select(User).where(User.email == user_email)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            print(f"❌ Utente non trovato: {user_email}")
            return
        
        print(f"✅ Utente trovato: {user.email} (ID: {user.id})")
        print()
        
        # Trova integrazione MCP per questo utente
        integration_result = await db.execute(
            select(Integration)
            .where(Integration.service_type == "mcp_server")
            .where(Integration.enabled == True)
            .where(Integration.user_id == user.id)
            .where(Integration.tenant_id == user.tenant_id)
        )
        integration = integration_result.scalar_one_or_none()
        
        if not integration:
            print("❌ Nessuna integrazione MCP trovata per questo utente")
            print("   Connetti un server MCP dalla pagina Integrations nel frontend")
            return
        
        print(f"✅ Integrazione trovata: {integration.id}")
        session_metadata = integration.session_metadata or {}
        server_url = session_metadata.get("server_url", "")
        print(f"   Server URL: {server_url}")
        print()
        
        # 2. Verifica OAuth credentials
        print("2. Verifica OAuth credentials...")
        oauth_credentials = session_metadata.get("oauth_credentials", {})
        user_id_str = str(user.id)
        
        if user_id_str not in oauth_credentials:
            print("❌ Nessuna OAuth credential trovata per questo utente")
            print("   Vai a Profile → Google Workspace MCP → Authorize OAuth")
            return
        
        print(f"✅ OAuth credentials trovate per user {user_id_str}")
        print()
        
        # 3. Recupera token OAuth con refresh
        print("3. Recupero token OAuth (con refresh automatico)...")
        try:
            oauth_token = await OAuthTokenManager.get_valid_token(
                integration=integration,
                user=user,
                db=db,
                auto_refresh=True
            )
            if oauth_token:
                print(f"✅ Token OAuth recuperato (length: {len(oauth_token)})")
                print(f"   Token preview: {oauth_token[:30]}...")
            else:
                print("❌ Token OAuth non disponibile")
                return
        except Exception as e:
            print(f"❌ Errore nel recupero token: {e}")
            import traceback
            traceback.print_exc()
            return
        print()
        
        # 4. Crea MCP client con token
        print("4. Creazione MCP client con token OAuth...")
        try:
            client = _get_mcp_client_for_integration(integration, current_user=user, oauth_token=oauth_token)
            print(f"✅ Client creato")
            print(f"   Base URL: {client.base_url}")
            print(f"   OAuth token presente: {bool(client.oauth_token)}")
        except Exception as e:
            print(f"❌ Errore nella creazione client: {e}")
            import traceback
            traceback.print_exc()
            return
        print()
        
        # 5. Test list_tools
        print("5. Test list_tools()...")
        try:
            tools = await client.list_tools()
            print(f"✅ list_tools() riuscito: {len(tools)} tools trovati")
            if tools:
                print("   Primi 5 tools:")
                for tool in tools[:5]:
                    print(f"      - {tool.get('name', 'Unknown')}")
        except Exception as e:
            print(f"⚠️  list_tools() fallito: {e}")
            print("   (Potrebbe essere normale per OAuth 2.1 servers)")
        print()
        
        # 6. Test call_tool (mcp_list_calendars)
        print("6. Test call_tool('list_calendars')...")
        try:
            result = await client.call_tool("list_calendars", {})
            print(f"✅ call_tool() riuscito!")
            print(f"   Result type: {type(result)}")
            if isinstance(result, dict):
                print(f"   Result keys: {list(result.keys())}")
                if "content" in result:
                    content_preview = str(result["content"])[:200]
                    print(f"   Content preview: {content_preview}")
                if "isError" in result:
                    print(f"   Is Error: {result.get('isError')}")
                if "error" in result:
                    print(f"   Error: {result.get('error')}")
            else:
                print(f"   Result: {str(result)[:200]}")
        except Exception as e:
            print(f"❌ call_tool() fallito: {e}")
            import traceback
            traceback.print_exc()
        print()
        
        # 7. Chiudi client
        try:
            await client.close()
            print("✅ Client chiuso correttamente")
        except Exception as e:
            print(f"⚠️  Errore nella chiusura client: {e}")
    
    await engine.dispose()

if __name__ == "__main__":
    print("🧪 Test Chiamata Tool MCP")
    print("=" * 80)
    asyncio.run(test_mcp_tool())

