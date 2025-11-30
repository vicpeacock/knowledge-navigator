#!/bin/bash
# Script per fare rollback del backend Cloud Run all'ultima revisione funzionante

set -e

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PROJECT_ID="${GCP_PROJECT_ID:-526374196058}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="knowledge-navigator-backend"

function log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

function log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

function log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verifica che gcloud sia configurato
if ! command -v gcloud &> /dev/null; then
    log_error "gcloud CLI non trovato"
    exit 1
fi

log_info "🔄 Rollback Cloud Run Service: ${SERVICE_NAME}"
log_info "📋 Elenco revisioni disponibili:"
echo ""

# Lista tutte le revisioni (ultime 10)
REVISIONS=$(gcloud run revisions list \
    --service="${SERVICE_NAME}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --format="table(metadata.name,status.conditions[0].status,metadata.creationTimestamp)" \
    --limit=10 \
    --sort-by="metadata.creationTimestamp")

if [ -z "$REVISIONS" ]; then
    log_error "Nessuna revisione trovata per il servizio ${SERVICE_NAME}"
    exit 1
fi

echo "$REVISIONS"
echo ""

# Ottieni revisioni come array (escludi header)
REVISION_NAMES=($(gcloud run revisions list \
    --service="${SERVICE_NAME}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --format="value(metadata.name)" \
    --limit=10 \
    --sort-by="~metadata.creationTimestamp"))

if [ ${#REVISION_NAMES[@]} -lt 2 ]; then
    log_error "Non ci sono abbastanza revisioni per fare rollback (serve almeno 2)"
    exit 1
fi

# La prima è la corrente, la seconda è quella precedente (target per rollback)
CURRENT_REVISION="${REVISION_NAMES[0]}"
PREVIOUS_REVISION="${REVISION_NAMES[1]}"

log_info "📊 Situazione attuale:"
log_info "   Revisione corrente: ${CURRENT_REVISION}"
log_info "   Revisione precedente: ${PREVIOUS_REVISION}"
echo ""

# Chiedi conferma
read -p "⚠️  Vuoi fare rollback alla revisione ${PREVIOUS_REVISION}? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_warn "Rollback annullato"
    exit 0
fi

log_info "🔄 Eseguendo rollback alla revisione ${PREVIOUS_REVISION}..."

# Rollback alla revisione precedente
gcloud run services update-traffic "${SERVICE_NAME}" \
    --to-revisions="${PREVIOUS_REVISION}=100" \
    --region="${REGION}" \
    --project="${PROJECT_ID}"

if [ $? -eq 0 ]; then
    log_info "✅ Rollback completato!"
    log_info "   Il servizio ora usa la revisione: ${PREVIOUS_REVISION}"
    echo ""
    log_info "📋 Per tornare alla revisione corrente:"
    log_info "   gcloud run services update-traffic ${SERVICE_NAME} --to-revisions=${CURRENT_REVISION}=100 --region=${REGION}"
else
    log_error "❌ Errore durante il rollback"
    exit 1
fi

