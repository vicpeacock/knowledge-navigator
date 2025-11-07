#!/bin/bash
# Script per monitorare e riavviare automaticamente llama-server se si ferma

PORT=11435
LOG_FILE="/tmp/llama-background.log"
CHECK_INTERVAL=30  # Controlla ogni 30 secondi

while true; do
    # Verifica se llama-server è in esecuzione sulla porta 11435
    if ! lsof -ti:$PORT > /dev/null 2>&1; then
        echo "$(date): ⚠️ llama-server non è in esecuzione, riavvio..." >> "$LOG_FILE"
        # Riavvia llama-server
        cd "$(dirname "$0")/.."
        ./scripts/start_llama_background.sh >> "$LOG_FILE" 2>&1
        sleep 5  # Aspetta che si avvii
    fi
    sleep $CHECK_INTERVAL
done

