#!/bin/bash
# Script per esportare dati dal backend Cloud Run
# Usa l'API del backend stesso per recuperare i dati

set -e

CLOUD_BACKEND_URL="https://knowledge-navigator-backend-526374196058.us-central1.run.app"

echo "🔄 Export dati dal backend Cloud Run"
echo "===================================="
echo ""

# Accetta credenziali da variabili d'ambiente o chiedile
if [ -z "$ADMIN_EMAIL" ]; then
    read -p "Email admin sul cloud: " ADMIN_EMAIL
fi

if [ -z "$ADMIN_PASSWORD" ]; then
    read -sp "Password admin sul cloud: " ADMIN_PASSWORD
    echo ""
fi

if [ -z "$ADMIN_EMAIL" ] || [ -z "$ADMIN_PASSWORD" ]; then
    echo "❌ Email e password richieste"
    exit 1
fi

# Login
echo "🔐 Login..."
LOGIN_RESPONSE=$(curl -s -X POST "$CLOUD_BACKEND_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}")

ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

if [ -z "$ACCESS_TOKEN" ]; then
    echo "❌ Login fallito. Verifica le credenziali."
    echo "Response: $LOGIN_RESPONSE"
    exit 1
fi

echo "✅ Login riuscito"
echo ""

# Export users
echo "👥 Esportazione users..."
curl -s -X GET "$CLOUD_BACKEND_URL/api/v1/users" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    > /tmp/cloud_users.json

USER_COUNT=$(cat /tmp/cloud_users.json | python3 -c "import sys, json; d=json.load(sys.stdin); print(len(d) if isinstance(d, list) else 0)" 2>/dev/null || echo "0")
echo "   ✅ $USER_COUNT users esportati"

# Export sessions
echo "💬 Esportazione sessions..."
curl -s -X GET "$CLOUD_BACKEND_URL/api/v1/sessions/" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    > /tmp/cloud_sessions.json

SESSION_COUNT=$(cat /tmp/cloud_sessions.json | python3 -c "import sys, json; d=json.load(sys.stdin); print(len(d) if isinstance(d, list) else 0)" 2>/dev/null || echo "0")
echo "   ✅ $SESSION_COUNT sessions esportate"

echo ""
echo "✅ Export completato!"
echo "   Files:"
echo "   - /tmp/cloud_users.json"
echo "   - /tmp/cloud_sessions.json"
echo ""
echo "Ora puoi importare questi dati nel database locale."

