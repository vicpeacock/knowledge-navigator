#!/bin/bash
# Script per vedere i log del frontend su Cloud Run

echo "📋 Log del Frontend su Cloud Run"
echo "=================================="
echo ""
echo "Ultimi 100 log del frontend:"
echo ""

gcloud run services logs read knowledge-navigator-frontend \
  --region=us-central1 \
  --project=knowledge-navigator-477022 \
  --limit=100 \
  2>&1 | tail -100

echo ""
echo "💡 Per vedere i log in tempo reale, usa:"
echo "   gcloud run services logs tail knowledge-navigator-frontend --region=us-central1 --project=knowledge-navigator-477022"
echo ""
echo "💡 Per vedere gli errori JavaScript nel browser:"
echo "   1. Apri il frontend nel browser"
echo "   2. Premi F12 (o Cmd+Option+I su Mac)"
echo "   3. Vai alla tab 'Console'"
echo "   4. Cerca errori con 'gmail' o 'mcp_get_gmail'"

