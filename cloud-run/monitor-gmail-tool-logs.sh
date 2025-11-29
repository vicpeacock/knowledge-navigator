#!/bin/bash
# Script per monitorare i log del backend quando viene chiamato il tool Gmail batch

echo "🔍 Monitoraggio log per tool Gmail batch"
echo "=========================================="
echo ""
echo "Questo script monitora i log del backend in tempo reale"
echo "Premi Ctrl+C per interrompere"
echo ""
echo "Cerca pattern: get_gmail, gmail.*batch, message_ids, Error, ❌, Executing.*tool"
echo ""

# Usa gcloud logging tail per vedere i log in tempo reale
gcloud logging tail \
  "resource.type=cloud_run_revision AND resource.labels.service_name=knowledge-navigator-backend" \
  --project=knowledge-navigator-477022 \
  --format="value(textPayload,jsonPayload.message)" \
  2>&1 | grep --line-buffered -E '(get_gmail|gmail.*batch|message_ids|Error|❌|Executing.*tool|🔧 Tool|mcp_get_gmail|Tool.*failed|Exception.*gmail)'

