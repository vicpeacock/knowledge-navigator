#!/bin/bash
# Script per scaricare il dump completo del database dal backend Cloud Run
# Usa l'endpoint admin /api/init/export-database

set -e

CLOUD_BACKEND_URL="https://knowledge-navigator-backend-526374196058.us-central1.run.app"

echo "🔄 Download dump completo del database dal Cloud Run"
echo "===================================================="
echo ""

# Credenziali admin
ADMIN_EMAIL=${ADMIN_EMAIL:-"admin@example.com"}
ADMIN_PASSWORD=${ADMIN_PASSWORD:-"admin123"}

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

# Download dump
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DUMP_FILE="knowledge_navigator_full_backup_${TIMESTAMP}.sql"

echo "📥 Download dump del database..."
echo "   Questo può richiedere alcuni minuti se il database è grande..."
echo ""

curl -X GET "$CLOUD_BACKEND_URL/api/init/export-database" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    --progress-bar \
    --output "$DUMP_FILE"

if [ $? -eq 0 ] && [ -s "$DUMP_FILE" ]; then
    DUMP_SIZE=$(du -h "$DUMP_FILE" | cut -f1)
    echo ""
    echo "✅ Dump scaricato con successo!"
    echo "   File: $DUMP_FILE"
    echo "   Dimensione: $DUMP_SIZE"
    echo ""
    echo "📥 Ora puoi importare questo dump nel database locale:"
    echo "   ./scripts/import-full-database-to-local.sh $DUMP_FILE"
else
    echo ""
    echo "❌ Errore durante il download del dump"
    exit 1
fi

