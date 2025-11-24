#!/bin/bash
# Deployment script for Google Workspace MCP Server on Cloud Run
# Usage: ./cloud-run/deploy-workspace-mcp.sh

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env.cloud-run"

# Colori per output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

function log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

function log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

function log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

function log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

# Load environment variables
if [ -f "$ENV_FILE" ]; then
    log_info "Loading environment variables from .env.cloud-run..."
    set -a
    source "$ENV_FILE"
    set +a
else
    log_error "File .env.cloud-run not found"
    exit 1
fi

# Set defaults
GCP_PROJECT_ID="${GCP_PROJECT_ID:-knowledge-navigator-477022}"
GCP_REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="google-workspace-mcp"

log_info "🚀 Deploying Google Workspace MCP Server to Cloud Run..."
log_info "Project: $GCP_PROJECT_ID"
log_info "Region: $GCP_REGION"

# Check prerequisites
if ! command -v gcloud &> /dev/null; then
    log_error "gcloud CLI not found. Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    log_error "Docker not found. Install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Set GCP project
gcloud config set project "$GCP_PROJECT_ID"

# Enable required APIs
log_info "Enabling required GCP APIs..."
gcloud services enable run.googleapis.com containerregistry.googleapis.com --project="$GCP_PROJECT_ID" 2>/dev/null || true

# Configure Docker for GCR
log_info "Configuring Docker for Google Container Registry..."
gcloud auth configure-docker gcr.io --quiet 2>/dev/null || true

# Build Docker image
log_info "Building Google Workspace MCP Docker image..."
cd "$PROJECT_ROOT"

# Check if patches directory exists
if [ ! -d "backend/patches" ]; then
    log_error "backend/patches directory not found! Patches are required for the build."
    exit 1
fi

docker build \
    --platform linux/amd64 \
    -f Dockerfile.workspace-mcp \
    -t gcr.io/${GCP_PROJECT_ID}/${SERVICE_NAME}:latest .

docker tag gcr.io/${GCP_PROJECT_ID}/${SERVICE_NAME}:latest \
    gcr.io/${GCP_PROJECT_ID}/${SERVICE_NAME}:$(date +%Y%m%d-%H%M%S)

log_info "✅ Image built"

# Push to GCR
log_info "Pushing image to Google Container Registry..."
docker push gcr.io/${GCP_PROJECT_ID}/${SERVICE_NAME}:latest
log_info "✅ Image pushed"

# Get OAuth redirect URI (will be set after deployment)
# We'll use a placeholder for now and update it after deployment
DEPLOYED_URL=""
REDIRECT_URI_PLACEHOLDER="https://PLACEHOLDER.run.app/oauth2callback"

# Build environment variables
ENV_VARS="PORT=8000"

# Add OAuth credentials if available
if [ -n "$GOOGLE_OAUTH_CLIENT_ID" ]; then
    ENV_VARS="${ENV_VARS},GOOGLE_OAUTH_CLIENT_ID=${GOOGLE_OAUTH_CLIENT_ID}"
fi

if [ -n "$GOOGLE_OAUTH_CLIENT_SECRET" ]; then
    ENV_VARS="${ENV_VARS},GOOGLE_OAUTH_CLIENT_SECRET=${GOOGLE_OAUTH_CLIENT_SECRET}"
fi

# Add OAuth redirect URI (will be updated after deployment)
ENV_VARS="${ENV_VARS},GOOGLE_OAUTH_REDIRECT_URI=${REDIRECT_URI_PLACEHOLDER}"

# Add server configuration
ENV_VARS="${ENV_VARS},MCP_ENABLE_OAUTH21=true"
ENV_VARS="${ENV_VARS},EXTERNAL_OAUTH21_PROVIDER=true"
ENV_VARS="${ENV_VARS},WORKSPACE_MCP_STATELESS_MODE=true"

# Deploy to Cloud Run
log_info "Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --image gcr.io/${GCP_PROJECT_ID}/${SERVICE_NAME}:latest \
    --platform managed \
    --region "$GCP_REGION" \
    --allow-unauthenticated \
    --port 8000 \
    --memory 512Mi \
    --cpu 1 \
    --timeout 300 \
    --max-instances 10 \
    --set-env-vars "$ENV_VARS"

# Get deployed URL
DEPLOYED_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --region "$GCP_REGION" \
    --format 'value(status.url)')

log_info "✅ Service deployed: $DEPLOYED_URL"

# Update redirect URI in the service
if [ -n "$DEPLOYED_URL" ]; then
    REDIRECT_URI="${DEPLOYED_URL}/oauth2callback"
    log_info "Updating OAuth redirect URI to: $REDIRECT_URI"
    
    # Update environment variable
    ENV_VARS_UPDATED="${ENV_VARS},GOOGLE_OAUTH_REDIRECT_URI=${REDIRECT_URI}"
    
    gcloud run services update ${SERVICE_NAME} \
        --region "$GCP_REGION" \
        --update-env-vars "$ENV_VARS_UPDATED" \
        --quiet
    
    log_info "✅ OAuth redirect URI updated"
    
    log_warn "⚠️  IMPORTANT: Update Google Cloud Console OAuth credentials:"
    log_warn "   1. Go to: https://console.cloud.google.com/apis/credentials"
    log_warn "   2. Edit your OAuth 2.0 Client ID"
    log_warn "   3. Add to 'Authorized redirect URIs': $REDIRECT_URI"
fi

log_info "🎉 Deployment completed!"
log_info "Service URL: $DEPLOYED_URL"
log_info ""
log_info "Next steps:"
log_info "1. Update OAuth redirect URI in Google Cloud Console (see warning above)"
log_info "2. Connect the server in the frontend using URL: $DEPLOYED_URL"
log_info "3. Authorize OAuth in your Profile page"

