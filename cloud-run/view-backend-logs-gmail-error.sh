#!/bin/bash
# Script per cercare errori Gmail nei log del backend

echo "🔍 Cercando errori Gmail nei log del backend..."
echo "================================================"
echo ""

# Cerca errori specifici per get_gmail_messages_content_batch
echo "📧 Cercando errori per 'get_gmail_messages_content_batch':"
echo ""

gcloud run services logs read knowledge-navigator-backend \
  --region=us-central1 \
  --project=knowledge-navigator-477022 \
  --limit=2000 \
  2>&1 | grep -B 10 -A 20 "get_gmail_messages_content_batch\|Error calling.*gmail\|❌.*gmail\|Exception.*gmail\|message_ids.*19a93674987a96f7" | tail -100

echo ""
echo "================================================"
echo ""
echo "📧 Cercando tutte le chiamate a tool Gmail:"
echo ""

gcloud run services logs read knowledge-navigator-backend \
  --region=us-central1 \
  --project=knowledge-navigator-477022 \
  --limit=1000 \
  2>&1 | grep -E "(mcp_.*gmail|gmail.*tool|Executing.*gmail|Tool.*gmail)" | tail -50

echo ""
echo "================================================"
echo ""
echo "💡 Per vedere i log in tempo reale:"
echo "   gcloud run services logs tail knowledge-navigator-backend --region=us-central1 --project=knowledge-navigator-477022"

