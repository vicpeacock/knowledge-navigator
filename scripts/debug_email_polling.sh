#!/bin/bash

# Script per debug del polling email
# Usage: ./scripts/debug_email_polling.sh

set -e

API_URL="${API_URL:-http://localhost:8000}"

echo "🔍 Email Polling Debug"
echo "====================="
echo ""

# Check backend
echo "1️⃣  Verificando backend..."
if ! curl -s -f "${API_URL}/health" > /dev/null 2>&1; then
    echo "❌ Backend non raggiungibile"
    exit 1
fi
echo "✅ Backend OK"
echo ""

# Trigger email check manually
echo "2️⃣  Triggerando controllo email manuale..."
echo "   POST ${API_URL}/api/notifications/check-events"
echo ""

RESPONSE=$(curl -s -X POST "${API_URL}/api/notifications/check-events" \
    -H "Content-Type: application/json" \
    -w "\nHTTP_CODE:%{http_code}")

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
BODY=$(echo "$RESPONSE" | sed '/HTTP_CODE/d')

echo "HTTP Status: $HTTP_CODE"
echo "Response:"
echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
echo ""

# Instructions
echo "📋 Prossimi passi:"
echo ""
echo "1. Controlla i log del backend per vedere:"
echo "   - 🔍 Checking for new emails..."
echo "   - 📧 Gmail API returned X unread emails"
echo "   - 📊 Deduplication: Found X already processed emails"
echo "   - ✅ New email found: ..."
echo ""
echo "2. Se vedi 'No unread emails found', verifica:"
echo "   - L'email è arrivata?"
echo "   - L'email è marcata come 'unread' in Gmail?"
echo "   - L'email è arrivata nelle ultime 24 ore?"
echo ""
echo "3. Se vedi email ma vengono filtrate, controlla:"
echo "   - Se esistono già notifiche per quelle email"
echo "   - Se esistono sessioni create da quelle email"
echo ""
echo "4. Per vedere i log in tempo reale:"
echo "   tail -f backend/backend.log | grep -E '(🔍|📧|📋|✅|⏭️|❌|⚠️|ℹ️|Email|email|Gmail|gmail)'"
echo "   oppure tutti i log:"
echo "   tail -f backend/backend.log"
echo ""

