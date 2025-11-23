#!/bin/bash
# Script per verificare quali chiavi/credenziali sono già configurate

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "🔍 Verifica Chiavi e Credenziali Configurate"
echo "=============================================="
echo ""

# Colori
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Funzione per verificare se una variabile è presente
check_var() {
    local var_name=$1
    local description=$2
    local required=$3  # "required" o "optional"
    
    # Controlla in .env file
    if [ -f .env ]; then
        if grep -q "^${var_name}=" .env 2>/dev/null; then
            value=$(grep "^${var_name}=" .env | cut -d'=' -f2- | sed 's/^"//;s/"$//')
            var_name_lower=$(echo "$var_name" | tr '[:upper:]' '[:lower:]')
            var_name_upper=$(echo "$var_name" | tr '[:lower:]' '[:upper:]')
            if [ -n "$value" ] && [ "$value" != "your-${var_name_lower}" ] && [ "$value" != "YOUR_${var_name_upper}" ]; then
                echo -e "${GREEN}✅${NC} ${var_name}: ${description}"
                echo "   Valore: ${value:0:20}... (nascosto per sicurezza)"
                return 0
            fi
        fi
    fi
    
    # Controlla in variabili ambiente
    if [ -n "${!var_name}" ]; then
        echo -e "${GREEN}✅${NC} ${var_name}: ${description} (da env var)"
        return 0
    fi
    
    # Variabile non trovata
    if [ "$required" = "required" ]; then
        echo -e "${RED}❌${NC} ${var_name}: ${description} (MANCANTE - RICHIESTA)"
        return 1
    else
        echo -e "${YELLOW}⚠️${NC}  ${var_name}: ${description} (opzionale)"
        return 0
    fi
}

# Conta variabili mancanti
missing_count=0

echo "📋 CHIAVI PER CLOUD RUN DEPLOYMENT"
echo "-----------------------------------"
echo ""

# Database (richiesto)
echo "🗄️  Database:"
check_var "DATABASE_URL" "Database connection string" "required" || missing_count=$((missing_count + 1))
check_var "POSTGRES_HOST" "PostgreSQL host" "optional"
check_var "POSTGRES_USER" "PostgreSQL user" "optional"
check_var "POSTGRES_PASSWORD" "PostgreSQL password" "optional"
check_var "POSTGRES_DB" "PostgreSQL database name" "optional"
echo ""

# LLM Provider (richiesto per cloud)
echo "🤖 LLM Configuration:"
check_var "LLM_PROVIDER" "LLM provider (ollama/gemini)" "required" || missing_count=$((missing_count + 1))
check_var "GEMINI_API_KEY" "Gemini API key (richiesta se LLM_PROVIDER=gemini)" "required" || missing_count=$((missing_count + 1))
check_var "GEMINI_MODEL" "Gemini model name" "optional"
echo ""

# Security Keys (richieste)
echo "🔐 Security Keys:"
check_var "SECRET_KEY" "Secret key per applicazione" "required" || missing_count=$((missing_count + 1))
check_var "ENCRYPTION_KEY" "Encryption key (32 bytes)" "required" || missing_count=$((missing_count + 1))
check_var "JWT_SECRET_KEY" "JWT secret key" "required" || missing_count=$((missing_count + 1))
echo ""

# Google OAuth (opzionale ma utile)
echo "🔑 Google OAuth (per Calendar/Email):"
check_var "GOOGLE_CLIENT_ID" "Google OAuth Client ID" "optional"
check_var "GOOGLE_CLIENT_SECRET" "Google OAuth Client Secret" "optional"
check_var "GOOGLE_OAUTH_CLIENT_ID" "Google Workspace OAuth Client ID" "optional"
check_var "GOOGLE_OAUTH_CLIENT_SECRET" "Google Workspace OAuth Client Secret" "optional"
echo ""

# Google Custom Search (opzionale)
echo "🔍 Google Custom Search:"
check_var "GOOGLE_PSE_API_KEY" "Google Custom Search API key" "optional"
check_var "GOOGLE_PSE_CX" "Google Custom Search Engine ID" "optional"
check_var "GOOGLE_CSE_API_KEY" "Google Custom Search API key (alias)" "optional"
check_var "GOOGLE_CSE_CX" "Google Custom Search Engine ID (alias)" "optional"
echo ""

# ChromaDB (opzionale per cloud)
echo "💾 ChromaDB:"
check_var "CHROMADB_HOST" "ChromaDB host" "optional"
check_var "CHROMADB_PORT" "ChromaDB port" "optional"
echo ""

# MCP Gateway (opzionale)
echo "🔌 MCP Gateway:"
check_var "MCP_GATEWAY_URL" "MCP Gateway URL" "optional"
check_var "MCP_GATEWAY_AUTH_TOKEN" "MCP Gateway auth token" "optional"
echo ""

# SMTP (opzionale)
echo "📧 SMTP (opzionale):"
check_var "SMTP_HOST" "SMTP host" "optional"
check_var "SMTP_USER" "SMTP user" "optional"
check_var "SMTP_PASSWORD" "SMTP password" "optional"
echo ""

# Riepilogo
echo ""
echo "=============================================="
if [ $missing_count -eq 0 ]; then
    echo -e "${GREEN}✅ Tutte le chiavi richieste sono configurate!${NC}"
    echo ""
    echo "📝 Prossimi passi:"
    echo "   1. Verifica che i valori siano corretti per Cloud Run"
    echo "   2. Crea file .env.cloud-run con i valori per deployment"
    echo "   3. Procedi con deploy: ./cloud-run/deploy.sh backend"
else
    echo -e "${RED}❌ Mancano ${missing_count} chiavi richieste${NC}"
    echo ""
    echo "📝 Cosa fare:"
    echo "   1. Aggiungi le chiavi mancanti al file .env"
    echo "   2. Vedi cloud-run/SETUP_GUIDE.md per istruzioni dettagliate"
    echo "   3. Vedi cloud-run/env.example per template completo"
fi
echo ""

