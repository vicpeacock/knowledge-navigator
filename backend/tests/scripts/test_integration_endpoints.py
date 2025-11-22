#!/usr/bin/env python3
"""
Test script per verificare gli endpoint delle integrazioni (user vs service).
"""
import asyncio
import sys
import os
from pathlib import Path
from uuid import uuid4

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import httpx
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default port is 8000, can be overridden by environment
import os
PORT = int(os.getenv("PORT", "8000"))
BASE_URL = f"http://localhost:{PORT}"


async def get_auth_token(email: str, password: str) -> str:
    """Ottieni token di autenticazione"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/v1/auth/login",
            json={"email": email, "password": password}
        )
        if response.status_code != 200:
            raise Exception(f"Login failed: {response.status_code} - {response.text}")
        return response.json()["access_token"]


async def test_user_integrations_endpoint(token: str):
    """Test endpoint /integrations per utenti (solo user_*)"""
    logger.info("\n🧪 Test endpoint /integrations (utente)")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test email integrations
        response = await client.get(
            f"{BASE_URL}/api/integrations/emails/integrations",
            headers=headers
        )
        
        if response.status_code != 200:
            logger.error(f"❌ Errore: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        integrations = data.get("integrations", [])
        
        logger.info(f"   Email integrations trovate: {len(integrations)}")
        for integration in integrations:
            purpose = integration.get("purpose", "N/A")
            if purpose != "user_email":
                logger.error(f"❌ Trovata integrazione con purpose={purpose}, atteso user_email")
                return False
            logger.info(f"   ✅ {integration.get('provider')} - {purpose}")
        
        # Test calendar integrations
        response = await client.get(
            f"{BASE_URL}/api/integrations/calendars/integrations",
            headers=headers
        )
        
        if response.status_code != 200:
            logger.error(f"❌ Errore: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        integrations = data.get("integrations", [])
        
        logger.info(f"   Calendar integrations trovate: {len(integrations)}")
        for integration in integrations:
            purpose = integration.get("purpose", "N/A")
            if purpose != "user_calendar":
                logger.error(f"❌ Trovata integrazione con purpose={purpose}, atteso user_calendar")
                return False
            logger.info(f"   ✅ {integration.get('provider')} - {purpose}")
    
    return True


async def test_admin_service_integrations_endpoint(admin_token: str):
    """Test endpoint /admin/integrations per admin (solo service_*)"""
    logger.info("\n🧪 Test endpoint /admin/integrations (admin)")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Test email service integrations
        response = await client.get(
            f"{BASE_URL}/api/integrations/emails/admin/integrations",
            headers=headers
        )
        
        if response.status_code != 200:
            logger.error(f"❌ Errore: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        integrations = data.get("integrations", [])
        
        logger.info(f"   Service email integrations trovate: {len(integrations)}")
        for integration in integrations:
            purpose = integration.get("purpose", "N/A")
            if purpose != "service_email":
                logger.error(f"❌ Trovata integrazione con purpose={purpose}, atteso service_email")
                return False
            logger.info(f"   ✅ {integration.get('provider')} - {purpose}")
        
        # Test calendar service integrations
        response = await client.get(
            f"{BASE_URL}/api/integrations/calendars/admin/integrations",
            headers=headers
        )
        
        if response.status_code != 200:
            logger.error(f"❌ Errore: {response.status_code} - {response.text}")
            return False
        
        data = response.json()
        integrations = data.get("integrations", [])
        
        logger.info(f"   Service calendar integrations trovate: {len(integrations)}")
        for integration in integrations:
            purpose = integration.get("purpose", "N/A")
            if purpose != "service_calendar":
                logger.error(f"❌ Trovata integrazione con purpose={purpose}, atteso service_calendar")
                return False
            logger.info(f"   ✅ {integration.get('provider')} - {purpose}")
    
    return True


async def test_non_admin_cannot_access_service_endpoint(user_token: str):
    """Test che utenti non-admin non possano accedere agli endpoint service"""
    logger.info("\n🧪 Test accesso negato a endpoint service (non-admin)")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        headers = {"Authorization": f"Bearer {user_token}"}
        
        # Test email service integrations (should fail)
        response = await client.get(
            f"{BASE_URL}/api/integrations/emails/admin/integrations",
            headers=headers
        )
        
        if response.status_code == 403:
            logger.info("   ✅ Accesso negato correttamente (403 Forbidden)")
        elif response.status_code == 200:
            logger.warning("   ⚠️  Endpoint accessibile anche a non-admin (dovrebbe essere 403)")
        else:
            logger.error(f"   ❌ Status code inatteso: {response.status_code}")
            return False
    
    return True


async def main():
    """Main test function"""
    logger.info("🧪 Test endpoint integrazioni\n")
    
    # Check if backend is running
    logger.info(f"🔍 Verifica backend su {BASE_URL}...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{BASE_URL}/health")
            if response.status_code != 200:
                logger.error(f"❌ Backend non risponde correttamente: {response.status_code}")
                logger.error("   Avvia il backend: cd backend && uvicorn app.main:app --reload")
                return 1
            logger.info("✅ Backend raggiungibile\n")
    except (httpx.ConnectTimeout, httpx.ConnectError) as e:
        logger.error(f"❌ Backend non raggiungibile su {BASE_URL}")
        logger.error(f"   Errore: {e}")
        logger.error("   Verifica che il backend sia in esecuzione:")
        logger.error("   cd backend && uvicorn app.main:app --reload")
        logger.error("   Oppure verifica che il backend sia in ascolto su localhost:8000")
        return 1
    except Exception as e:
        logger.error(f"❌ Errore nel verificare il backend: {e}")
        logger.error("   Avvia il backend: cd backend && uvicorn app.main:app --reload")
        return 1
    
    try:
        # Get admin token with correct password
        try:
            admin_token = await get_auth_token("admin@example.com", "AdminPassword123!")
            logger.info("✅ Login admin riuscito")
        except Exception as e:
            logger.error(f"❌ Impossibile fare login come admin: {e}")
            logger.error("   Password corretta: AdminPassword123!")
            logger.error("   Esegui: python3 tests/scripts/reset_admin_password.py")
            return 1
        
        # Get user token (if exists) - use admin token for user tests if user doesn't exist
        user_token = admin_token
        try:
            user_token = await get_auth_token("user@example.com", "user123")
            logger.info("✅ Login utente riuscito")
        except:
            logger.warning("⚠️  Utente user@example.com non trovato o password errata, uso admin per test utente")
        
        # Run tests
        tests = [
            ("User integrations endpoint", test_user_integrations_endpoint(user_token)),
            ("Admin service integrations endpoint", test_admin_service_integrations_endpoint(admin_token)),
            ("Non-admin access denied", test_non_admin_cannot_access_service_endpoint(user_token)),
        ]
        
        results = []
        for test_name, test_coro in tests:
            try:
                result = await test_coro
                results.append((test_name, result))
            except Exception as e:
                logger.error(f"❌ Errore in {test_name}: {e}")
                results.append((test_name, False))
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("📊 Riepilogo test:")
        all_passed = True
        for test_name, result in results:
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"   {status}: {test_name}")
            if not result:
                all_passed = False
        
        if all_passed:
            logger.info("\n✅ Tutti i test sono passati!")
            return 0
        else:
            logger.error("\n❌ Alcuni test sono falliti!")
            return 1
            
    except Exception as e:
        logger.error(f"❌ Errore durante i test: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

