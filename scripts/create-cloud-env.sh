#!/bin/bash
# Script per creare .env.cloud-run con i valori forniti
# 
# ⚠️  IMPORTANTE: Questo script NON contiene segreti hardcoded.
# Tutti i segreti devono essere forniti tramite variabili d'ambiente
# o Google Secret Manager.
#
# Per usare questo script:
#   1. Esporta le variabili d'ambiente necessarie
#   2. Oppure modifica questo script per leggere da Secret Manager
#   3. NON committare mai segreti in questo file!

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

CLOUD_ENV_FILE=".env.cloud-run"

# Security keys - MUST BE SET FROM ENVIRONMENT OR SECRETS
# DO NOT HARDCODE SECRETS IN THIS FILE!
# Use environment variables or Google Secret Manager
SECRET_KEY="${SECRET_KEY:-CHANGE_ME_GENERATE_SECURE_KEY}"
ENCRYPTION_KEY="${ENCRYPTION_KEY:-CHANGE_ME_GENERATE_32_BYTE_KEY}"
JWT_SECRET_KEY="${JWT_SECRET_KEY:-CHANGE_ME_GENERATE_SECURE_KEY}"

# Gemini API Key - MUST BE SET FROM ENVIRONMENT
GEMINI_API_KEY="${GEMINI_API_KEY:-CHANGE_ME_YOUR_GEMINI_API_KEY}"

# Google OAuth - MUST BE SET FROM ENVIRONMENT
GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-CHANGE_ME_YOUR_GOOGLE_CLIENT_ID}"
GOOGLE_CLIENT_SECRET="${GOOGLE_CLIENT_SECRET:-CHANGE_ME_YOUR_GOOGLE_CLIENT_SECRET}"
GOOGLE_OAUTH_CLIENT_ID="${GOOGLE_OAUTH_CLIENT_ID:-${GOOGLE_CLIENT_ID}}"
GOOGLE_OAUTH_CLIENT_SECRET="${GOOGLE_OAUTH_CLIENT_SECRET:-${GOOGLE_CLIENT_SECRET}}"

# Google Custom Search - MUST BE SET FROM ENVIRONMENT
GOOGLE_PSE_API_KEY="${GOOGLE_PSE_API_KEY:-CHANGE_ME_YOUR_GOOGLE_PSE_API_KEY}"
GOOGLE_PSE_CX="${GOOGLE_PSE_CX:-CHANGE_ME_YOUR_GOOGLE_PSE_CX}"

# MCP Gateway - MUST BE SET FROM ENVIRONMENT
MCP_GATEWAY_URL="${MCP_GATEWAY_URL:-http://localhost:8080}"
MCP_GATEWAY_AUTH_TOKEN="${MCP_GATEWAY_AUTH_TOKEN:-CHANGE_ME_YOUR_MCP_GATEWAY_TOKEN}"

cat > "$CLOUD_ENV_FILE" << EOF
# Google Cloud Run Environment Variables
# Preparato automaticamente per deployment Cloud Run
# Data: 2025-11-24
#
# ⚠️  IMPORTANTE: Completa tutti i valori CHANGE_ME_* con i valori reali
# prima di usare questo file per il deployment.

# ============================================
# DATABASE CONFIGURATION - SUPABASE
# ============================================
# IMPORTANTE: Ottieni la connection string completa da Supabase Dashboard
# Vai su: https://app.supabase.com/project/YOUR_PROJECT_ID/settings/database
# Copia la connection string URI completa e usala come DATABASE_URL
# NON committare mai la password reale in questo file!
# Formato: postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT_ID].supabase.co:5432/postgres
# NOTA: Sostituisci [PASSWORD] e [PROJECT_ID] con i tuoi valori reali
DATABASE_URL=postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT_ID].supabase.co:5432/postgres
POSTGRES_HOST=db.[PROJECT_ID].supabase.co
POSTGRES_USER=postgres
POSTGRES_PASSWORD=[PASSWORD]
POSTGRES_DB=postgres
POSTGRES_PORT=5432

# ============================================
# SECURITY KEYS (GENERATE SICURE)
# ============================================
SECRET_KEY=${SECRET_KEY}
ENCRYPTION_KEY=${ENCRYPTION_KEY}
JWT_SECRET_KEY=${JWT_SECRET_KEY}
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# ============================================
# LLM PROVIDER - GEMINI (Cloud)
# ============================================
LLM_PROVIDER=gemini
GEMINI_API_KEY=${GEMINI_API_KEY}
GEMINI_MODEL=gemini-2.5-flash
# GEMINI_BACKGROUND_MODEL=gemini-1.5-flash  # Optional: faster model for background tasks
# GEMINI_PLANNER_MODEL=gemini-1.5-flash  # Optional: faster model for planning

# ============================================
# GOOGLE OAUTH (Calendar/Email)
# ============================================
GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}
GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}

# ============================================
# GOOGLE WORKSPACE MCP SERVER OAUTH
# ============================================
GOOGLE_OAUTH_CLIENT_ID=${GOOGLE_OAUTH_CLIENT_ID}
GOOGLE_OAUTH_CLIENT_SECRET=${GOOGLE_OAUTH_CLIENT_SECRET}

# ============================================
# GOOGLE CUSTOM SEARCH
# ============================================
GOOGLE_PSE_API_KEY=${GOOGLE_PSE_API_KEY}
GOOGLE_PSE_CX=${GOOGLE_PSE_CX}

# ============================================
# CHROMADB CONFIGURATION
# ============================================
# ATTENZIONE: ChromaDB deve essere deployato separatamente su Cloud Run
# O usa un servizio esterno. Per ora lasciato come placeholder.
# TODO: Deploy ChromaDB su Cloud Run o configura servizio esterno
CHROMADB_HOST=localhost
CHROMADB_PORT=8001

# ============================================
# MCP GATEWAY CONFIGURATION
# ============================================
# ATTENZIONE: MCP Gateway deve essere deployato separatamente su Cloud Run
# O usa un servizio esterno. Per ora lasciato come placeholder.
# TODO: Deploy MCP Gateway su Cloud Run o configura URL esterno
MCP_GATEWAY_URL=${MCP_GATEWAY_URL}
MCP_GATEWAY_AUTH_TOKEN=${MCP_GATEWAY_AUTH_TOKEN}

# ============================================
# FEATURE FLAGS
# ============================================
USE_LANGGRAPH_PROTOTYPE=true

# ============================================
# MEMORY SETTINGS
# ============================================
SHORT_TERM_MEMORY_TTL=3600
MEDIUM_TERM_MEMORY_DAYS=30
LONG_TERM_IMPORTANCE_THRESHOLD=0.7
MAX_CONTEXT_TOKENS=8000
CONTEXT_KEEP_RECENT_MESSAGES=10

# ============================================
# SEMANTIC INTEGRITY
# ============================================
INTEGRITY_CONFIDENCE_THRESHOLD=0.85
INTEGRITY_MAX_SIMILAR_MEMORIES=5
INTEGRITY_CHECK_EXHAUSTIVE=false
INTEGRITY_MIN_IMPORTANCE=0.7

# ============================================
# FILE UPLOAD
# ============================================
MAX_FILE_SIZE=10485760

# ============================================
# PORT (Cloud Run usa PORT env var automaticamente)
# ============================================
PORT=8000
EOF

echo "✅ File .env.cloud-run creato!"
echo ""
echo "⚠️  IMPORTANTE: Completa la password del database Supabase:"
echo "   1. Vai su: https://app.supabase.com/project/YOUR_PROJECT_ID/settings/database"
echo "   2. Copia la connection string URI completa"
echo "   3. Sostituisci [PASSWORD] e [PROJECT_ID] in DATABASE_URL e POSTGRES_PASSWORD con i valori reali"
echo "   4. NON committare mai il file .env.cloud-run con password reali!"
echo ""
echo "⚠️  IMPORTANTE: Assicurati di aver esportato tutte le variabili d'ambiente necessarie:"
echo "   - SECRET_KEY, ENCRYPTION_KEY, JWT_SECRET_KEY"
echo "   - GEMINI_API_KEY"
echo "   - GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET"
echo "   - GOOGLE_PSE_API_KEY, GOOGLE_PSE_CX"
echo "   - MCP_GATEWAY_AUTH_TOKEN (se necessario)"
echo ""

