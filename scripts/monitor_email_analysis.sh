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
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ -f "$PROJECT_ROOT/backend/backend.log" ]; then
    echo "📋 Monitorando log backend (backend/backend.log)..."
    tail -f "$PROJECT_ROOT/backend/backend.log" | grep -E "(🔍|📧|📋|✅|⏭️|❌|⚠️|ℹ️|Email analysis|Created automatic session|Created notification|email_analysis|EmailPoller|Gmail API)" || echo "⚠️  Nessun log trovato. Verifica che il backend sia in esecuzione."
elif [ -f "$PROJECT_ROOT/backend/logs/backend.log" ]; then
    echo "📋 Monitorando log backend (backend/logs/backend.log)..."
    tail -f "$PROJECT_ROOT/backend/logs/backend.log" | grep -E "(🔍|📧|📋|✅|⏭️|❌|⚠️|ℹ️|Email analysis|Created automatic session|Created notification|email_analysis|EmailPoller|Gmail API)" || echo "⚠️  Nessun log trovato."
else
    echo "⚠️  Impossibile trovare i log. Monitora manualmente i log del backend."
    echo ""
    echo "Per vedere i log:"
    echo "  tail -f backend/backend.log"
    echo "  oppure"
    echo "  tail -f backend/logs/backend.log"
fi

