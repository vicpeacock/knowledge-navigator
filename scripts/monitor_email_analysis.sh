#!/bin/bash

# Script per monitorare i log durante il test email auto-session
# Usage: ./scripts/monitor_email_analysis.sh

echo "🔍 Monitoraggio Log Email Analysis"
echo "=================================="
echo ""
echo "Cerca nei log del backend:"
echo "  - Email analysis for..."
echo "  - Created automatic session..."
echo "  - Created notification..."
echo ""
echo "Premi Ctrl+C per fermare il monitoraggio"
echo ""

# Monitor backend logs
if command -v docker-compose &> /dev/null; then
    echo "📋 Monitorando log backend (docker-compose)..."
    docker-compose logs -f backend 2>/dev/null | grep -E "(Email analysis|Created automatic session|Created notification|email_analysis|EmailPoller)" || echo "⚠️  Nessun log trovato. Verifica che il backend sia in esecuzione."
elif [ -f "backend/logs/app.log" ]; then
    echo "📋 Monitorando log backend (file)..."
    tail -f backend/logs/app.log | grep -E "(Email analysis|Created automatic session|Created notification|email_analysis|EmailPoller)" || echo "⚠️  Nessun log trovato."
else
    echo "⚠️  Impossibile trovare i log. Monitora manualmente i log del backend."
    echo ""
    echo "Per vedere i log:"
    echo "  - Se usi docker-compose: docker-compose logs -f backend"
    echo "  - Se backend locale: tail -f backend/logs/app.log"
fi

