#!/bin/bash

# Script per verificare quali API Google Workspace sono abilitate
# Uso: ./check-google-apis.sh [PROJECT_ID]

PROJECT_ID="${1:-526374196058}"

echo "🔍 Verifica API Google Workspace abilitate per progetto: $PROJECT_ID"
echo ""

# Lista delle API necessarie (formato: API_ID|API_NAME)
APIS=(
  "drive.googleapis.com|Google Drive API"
  "gmail.googleapis.com|Gmail API"
  "calendar-json.googleapis.com|Google Calendar API"
  "sheets.googleapis.com|Google Sheets API"
  "docs.googleapis.com|Google Docs API"
  "slides.googleapis.com|Google Slides API"
)

# Verifica se gcloud è installato
if ! command -v gcloud &> /dev/null; then
  echo "⚠️  gcloud CLI non è installato."
  echo ""
  echo "Verifica manuale tramite Console Web:"
  echo "  https://console.cloud.google.com/apis/library?project=$PROJECT_ID"
  echo ""
  echo "Oppure verifica ogni API:"
  for api_entry in "${APIS[@]}"; do
    IFS='|' read -r api_id api_name <<< "$api_entry"
    echo "  - $api_name: https://console.cloud.google.com/apis/library/$api_id?project=$PROJECT_ID"
  done
  exit 0
fi

# Verifica se il progetto esiste e è accessibile
if ! gcloud projects describe "$PROJECT_ID" &> /dev/null; then
  echo "❌ Errore: Impossibile accedere al progetto $PROJECT_ID"
  echo "   Verifica che:"
  echo "   1. Il Project ID sia corretto"
  echo "   2. Tu abbia i permessi necessari"
  echo "   3. gcloud sia autenticato: gcloud auth login"
  exit 1
fi

echo "✅ Progetto accessibile: $PROJECT_ID"
echo ""

# Ottieni lista API abilitate
ENABLED_APIS=$(gcloud services list --enabled --project="$PROJECT_ID" --format="value(config.name)" 2>/dev/null)

if [ -z "$ENABLED_APIS" ]; then
  echo "⚠️  Nessuna API abilitata trovata (o errore nel recupero)"
  echo ""
  echo "Verifica manuale:"
  echo "  https://console.cloud.google.com/apis/library?project=$PROJECT_ID"
  exit 1
fi

# Verifica ogni API
ALL_ENABLED=true
MISSING_APIS=()

echo "📋 Stato API:"
echo ""

for api_entry in "${APIS[@]}"; do
  IFS='|' read -r api_id api_name <<< "$api_entry"
  if echo "$ENABLED_APIS" | grep -q "^$api_id$"; then
    echo "  ✅ $api_name ($api_id)"
  else
    echo "  ❌ $api_name ($api_id) - NON ABILITATA"
    ALL_ENABLED=false
    MISSING_APIS+=("$api_id|$api_name")
  fi
done

echo ""

if [ "$ALL_ENABLED" = true ]; then
  echo "✅ Tutte le API sono abilitate!"
else
  echo "⚠️  Alcune API non sono abilitate:"
  echo ""
  for api_entry in "${MISSING_APIS[@]}"; do
    IFS='|' read -r api_id api_name <<< "$api_entry"
    echo "  - $api_name:"
    echo "    Link: https://console.cloud.google.com/flows/enableapi?apiid=$api_id&project=$PROJECT_ID"
  done
  echo ""
  echo "Per abilitarle, usa:"
  echo "  ./enable-google-apis.sh $PROJECT_ID"
  echo ""
  echo "Oppure abilita manualmente tramite i link sopra."
fi

