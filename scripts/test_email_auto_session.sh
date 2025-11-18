#!/bin/bash

# Script per testare la creazione automatica di sessioni da email
# Usage: ./scripts/test_email_auto_session.sh

set -e

API_URL="${API_URL:-http://localhost:8000}"
API_KEY="${API_KEY:-}"

echo "🧪 Test Email Auto-Session Creation"
echo "===================================="
echo ""

# Check if backend is running
echo "1️⃣  Verificando che il backend sia in esecuzione..."
if ! curl -s -f "${API_URL}/health" > /dev/null 2>&1; then
    echo "❌ Backend non raggiungibile su ${API_URL}"
    echo "   Assicurati che il backend sia in esecuzione"
    exit 1
fi
echo "✅ Backend raggiungibile"
echo ""

# Check health
echo "2️⃣  Verificando stato servizi..."
HEALTH=$(curl -s "${API_URL}/health" | python3 -m json.tool 2>/dev/null || echo "{}")
echo "$HEALTH" | grep -q "status" && echo "✅ Health check OK" || echo "⚠️  Health check non disponibile"
echo ""

# Trigger email check
echo "3️⃣  Triggerando controllo email..."
if [ -n "$API_KEY" ]; then
    RESPONSE=$(curl -s -X POST "${API_URL}/api/notifications/check-events" \
        -H "X-API-Key: ${API_KEY}" \
        -H "Content-Type: application/json")
else
    echo "⚠️  API_KEY non impostata, usando endpoint senza autenticazione..."
    RESPONSE=$(curl -s -X POST "${API_URL}/api/notifications/check-events" \
        -H "Content-Type: application/json")
fi

echo "Risposta:"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""

# Check notifications
echo "4️⃣  Verificando notifiche create..."
if [ -n "$API_KEY" ]; then
    NOTIFICATIONS=$(curl -s "${API_URL}/api/notifications/" \
        -H "X-API-Key: ${API_KEY}")
else
    NOTIFICATIONS=$(curl -s "${API_URL}/api/notifications/")
fi

NOTIF_COUNT=$(echo "$NOTIFICATIONS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data) if isinstance(data, list) else 0)" 2>/dev/null || echo "0")
echo "Notifiche trovate: $NOTIF_COUNT"
echo ""

if [ "$NOTIF_COUNT" -gt 0 ]; then
    echo "📧 Ultime notifiche email:"
    echo "$NOTIFICATIONS" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if isinstance(data, list):
        email_notifs = [n for n in data if n.get('type') == 'email_received']
        for n in email_notifs[:3]:
            print(f\"  - {n.get('content', {}).get('subject', 'N/A')} (priority: {n.get('priority', 'N/A')})\")
            if n.get('content', {}).get('has_session'):
                print(f\"    ✅ Sessione creata: {n.get('content', {}).get('session_id', 'N/A')}\")
            else:
                print(f\"    ℹ️  Nessuna sessione (email informativa)\")
except:
    pass
" 2>/dev/null || echo "  (Errore nel parsing)"
fi

echo ""
echo "✅ Test completato!"
echo ""
echo "📝 Prossimi passi:"
echo "   1. Controlla la campanella 🔔 nel frontend"
echo "   2. Verifica se è stata creata una nuova sessione"
echo "   3. Controlla i log del backend per dettagli"
echo ""

