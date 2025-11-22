#!/bin/bash

# Script per abilitare tutte le API Google Workspace necessarie
# Uso: ./enable-google-apis.sh [PROJECT_ID]

PROJECT_ID="${1:-526374196058}"

echo "🔧 Abilitazione API Google Workspace per progetto: $PROJECT_ID"
echo ""

APIS=(
  "drive.googleapis.com"
  "gmail.googleapis.com"
  "calendar-json.googleapis.com"  # Nome corretto per Calendar API
  "sheets.googleapis.com"
  "docs.googleapis.com"
  "slides.googleapis.com"
)

for api in "${APIS[@]}"; do
  echo "📦 Abilitazione $api..."
  gcloud services enable "$api" --project="$PROJECT_ID" 2>&1 | grep -E "(enabled|already|ERROR)" || echo "   ✅ $api"
done

echo ""
echo "✅ Completato!"
echo ""
echo "Verifica con:"
echo "  gcloud services list --enabled --project=$PROJECT_ID | grep googleapis"
