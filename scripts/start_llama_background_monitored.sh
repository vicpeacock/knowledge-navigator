#!/bin/bash
# Script per avviare llama-server con monitoraggio automatico

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MONITOR_SCRIPT="$SCRIPT_DIR/monitor_llama_background.sh"

# Avvia llama-server
"$SCRIPT_DIR/start_llama_background.sh"

# Avvia il monitor in background
nohup bash "$MONITOR_SCRIPT" > /tmp/llama-monitor.log 2>&1 &
MONITOR_PID=$!

echo "✅ Monitor avviato (PID: $MONITOR_PID)"
echo "📝 Monitor log: /tmp/llama-monitor.log"
echo ""
echo "Per fermare tutto:"
echo "  kill $MONITOR_PID"
echo "  lsof -ti:11435 | xargs kill -9"

