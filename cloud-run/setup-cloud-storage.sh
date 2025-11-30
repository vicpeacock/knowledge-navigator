#!/bin/bash
# Script per configurare Cloud Storage per file persistenti su Cloud Run

set -e

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "☁️  Setup Cloud Storage per Knowledge Navigator"
echo "=============================================="
echo ""

# Verifica che gcloud sia installato
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI non trovato. Installa Google Cloud SDK:${NC}"
    echo "   https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Verifica che l'utente sia autenticato
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo -e "${YELLOW}⚠️  Non sei autenticato con gcloud${NC}"
    echo "   Eseguendo: gcloud auth login"
    gcloud auth login
fi

# Chiedi project ID
read -p "Inserisci il Google Cloud Project ID: " PROJECT_ID

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}❌ Project ID non può essere vuoto${NC}"
    exit 1
fi

# Imposta il project
gcloud config set project "$PROJECT_ID"

# Chiedi region
read -p "Inserisci la region (default: us-central1): " REGION
REGION=${REGION:-us-central1}

# Nome bucket
BUCKET_NAME="${PROJECT_ID}-knowledge-navigator-files"

echo ""
echo "📋 Configurazione:"
echo "   Project ID: $PROJECT_ID"
echo "   Region: $REGION"
echo "   Bucket Name: $BUCKET_NAME"
echo ""

read -p "Procedere con la creazione del bucket? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Annullato."
    exit 0
fi

# Crea il bucket
echo ""
echo "🔨 Creazione bucket Cloud Storage..."

if gsutil ls -b "gs://${BUCKET_NAME}" &>/dev/null; then
    echo -e "${YELLOW}⚠️  Bucket già esistente: ${BUCKET_NAME}${NC}"
else
    # Crea bucket con versione e lifecycle
    gsutil mb -p "$PROJECT_ID" -l "$REGION" "gs://${BUCKET_NAME}"
    echo -e "${GREEN}✅ Bucket creato: ${BUCKET_NAME}${NC}"
fi

# Configura CORS (se necessario per accesso diretto da browser)
echo ""
echo "🔧 Configurazione CORS..."

CORS_CONFIG="/tmp/cors-config.json"
cat > "$CORS_CONFIG" << EOF
[
  {
    "origin": ["*"],
    "method": ["GET", "HEAD", "PUT", "POST", "DELETE"],
    "responseHeader": ["Content-Type", "Authorization"],
    "maxAgeSeconds": 3600
  }
]
EOF

gsutil cors set "$CORS_CONFIG" "gs://${BUCKET_NAME}"
rm -f "$CORS_CONFIG"
echo -e "${GREEN}✅ CORS configurato${NC}"

# Configura lifecycle (opzionale - elimina file dopo X giorni)
read -p "Configurare lifecycle policy? (es. elimina file dopo 90 giorni) (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    read -p "Giorni prima dell'eliminazione (default: 90): " DAYS
    DAYS=${DAYS:-90}
    
    LIFECYCLE_CONFIG="/tmp/lifecycle-config.json"
    cat > "$LIFECYCLE_CONFIG" << EOF
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"age": $DAYS}
      }
    ]
  }
}
EOF
    
    gsutil lifecycle set "$LIFECYCLE_CONFIG" "gs://${BUCKET_NAME}"
    rm -f "$LIFECYCLE_CONFIG"
    echo -e "${GREEN}✅ Lifecycle policy configurata (elimina dopo ${DAYS} giorni)${NC}"
fi

# Configura IAM per Cloud Run service account
echo ""
echo "🔐 Configurazione permessi IAM..."

# Ottieni il service account di Cloud Run
SERVICE_ACCOUNT="${PROJECT_ID}@appspot.gserviceaccount.com"

# Verifica se esiste
if ! gcloud iam service-accounts describe "$SERVICE_ACCOUNT" &>/dev/null; then
    echo -e "${YELLOW}⚠️  Service account ${SERVICE_ACCOUNT} non trovato${NC}"
    echo "   Creazione service account..."
    gcloud iam service-accounts create knowledge-navigator \
        --display-name="Knowledge Navigator" \
        --project="$PROJECT_ID" 2>/dev/null || true
    
    # Usa il service account appena creato o quello di default
    if gcloud iam service-accounts describe "knowledge-navigator@${PROJECT_ID}.iam.gserviceaccount.com" &>/dev/null; then
        SERVICE_ACCOUNT="knowledge-navigator@${PROJECT_ID}.iam.gserviceaccount.com"
    fi
fi

# Concedi permessi per Cloud Storage
echo "   Concessione permessi per: $SERVICE_ACCOUNT"
gsutil iam ch "serviceAccount:${SERVICE_ACCOUNT}:roles/storage.objectAdmin" "gs://${BUCKET_NAME}"
echo -e "${GREEN}✅ Permessi IAM configurati${NC}"

echo ""
echo -e "${GREEN}✅ Setup completato!${NC}"
echo ""
echo "📝 Aggiungi queste variabili d'ambiente a Cloud Run:"
echo ""
echo "   USE_CLOUD_STORAGE=true"
echo "   CLOUD_STORAGE_BUCKET_NAME=${BUCKET_NAME}"
echo ""
echo "Puoi aggiungerle durante il deploy o aggiornando il servizio:"
echo "   gcloud run services update knowledge-navigator-backend \\"
echo "       --set-env-vars USE_CLOUD_STORAGE=true,CLOUD_STORAGE_BUCKET_NAME=${BUCKET_NAME} \\"
echo "       --region ${REGION}"
echo ""

