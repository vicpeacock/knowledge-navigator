#!/bin/bash
# Script per verificare lo stato dell'autorizzazione OAuth MCP per un utente

set -e

BACKEND_URL="${BACKEND_URL:-https://knowledge-navigator-backend-osbdwu5a7q-uc.a.run.app}"

echo "🔍 Verifica Stato Autorizzazione OAuth MCP"
echo "=========================================="
echo ""
echo "Backend URL: $BACKEND_URL"
echo ""

# Chiedi all'utente di inserire le credenziali
read -p "Email utente: " USER_EMAIL
read -sp "Password: " USER_PASSWORD
echo ""

# 1. Login e ottieni JWT token
echo "1. Login..."
LOGIN_RESPONSE=$(curl -s -X POST "${BACKEND_URL}/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\": \"${USER_EMAIL}\", \"password\": \"${USER_PASSWORD}\"}")

ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

if [ -z "$ACCESS_TOKEN" ]; then
    echo "❌ Login fallito!"
    echo "Response: $LOGIN_RESPONSE"
    exit 1
fi

echo "✅ Login riuscito"
echo ""

# 2. Ottieni tenant_id e user_id dal token (o dalle API)
echo "2. Recupero informazioni utente..."
USER_INFO=$(curl -s -X GET "${BACKEND_URL}/api/v1/users/me" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}")

USER_ID=$(echo "$USER_INFO" | grep -o '"id":"[^"]*' | cut -d'"' -f4)
TENANT_ID=$(echo "$USER_INFO" | grep -o '"tenant_id":"[^"]*' | cut -d'"' -f4)

echo "   User ID: $USER_ID"
echo "   Tenant ID: $TENANT_ID"
echo ""

# 3. Lista integrazioni MCP
echo "3. Recupero integrazioni MCP..."
MCP_INTEGRATIONS=$(curl -s -X GET "${BACKEND_URL}/api/integrations/mcp/integrations" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}")

echo "$MCP_INTEGRATIONS" | python3 -m json.tool 2>/dev/null || echo "$MCP_INTEGRATIONS"
echo ""

# 4. Per ogni integrazione, verifica OAuth status
INTEGRATION_IDS=$(echo "$MCP_INTEGRATIONS" | grep -o '"id":"[^"]*' | cut -d'"' -f4)

if [ -z "$INTEGRATION_IDS" ]; then
    echo "⚠️  Nessuna integrazione MCP trovata!"
    echo "   Connetti un server MCP dalla pagina Integrations nel frontend"
    exit 0
fi

for INTEGRATION_ID in $INTEGRATION_IDS; do
    echo "4. Verifica integrazione: $INTEGRATION_ID"
    
    # Test connessione
    echo "   Test connessione..."
    TEST_RESPONSE=$(curl -s -X POST "${BACKEND_URL}/api/integrations/mcp/${INTEGRATION_ID}/test" \
      -H "Authorization: Bearer ${ACCESS_TOKEN}")
    
    echo "$TEST_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$TEST_RESPONSE"
    echo ""
    
    # Debug info
    echo "   Debug info..."
    DEBUG_RESPONSE=$(curl -s -X GET "${BACKEND_URL}/api/integrations/mcp/${INTEGRATION_ID}/debug" \
      -H "Authorization: Bearer ${ACCESS_TOKEN}")
    
    echo "$DEBUG_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$DEBUG_RESPONSE"
    echo ""
    
    # Tools disponibili
    echo "   Tools disponibili..."
    TOOLS_RESPONSE=$(curl -s -X GET "${BACKEND_URL}/api/integrations/mcp/${INTEGRATION_ID}/tools" \
      -H "Authorization: Bearer ${ACCESS_TOKEN}")
    
    TOOLS_COUNT=$(echo "$TOOLS_RESPONSE" | grep -o '"available_tools":\[.*\]' | grep -o '{"name"' | wc -l || echo "0")
    echo "   Tools trovati: $TOOLS_COUNT"
    
    if [ "$TOOLS_COUNT" -gt 0 ]; then
        echo "   ✅ OAuth autorizzato - Tools disponibili!"
    else
        echo "   ⚠️  Nessun tool disponibile - potrebbe richiedere autorizzazione OAuth"
        echo "   Vai a Profile → Google Workspace MCP → Authorize OAuth"
    fi
    echo ""
done

echo "✅ Verifica completata!"

