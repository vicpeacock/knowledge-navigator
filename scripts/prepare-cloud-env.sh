#!/bin/bash
# Script per preparare .env.cloud-run da .env esistente
# Modifica i valori necessari per Cloud Run deployment

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

ENV_FILE=".env"
CLOUD_ENV_FILE=".env.cloud-run"

# Colori
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "🔧 Preparazione .env.cloud-run per Cloud Run Deployment"
echo "======================================================"
echo ""

# Verifica che .env esista
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ File .env non trovato!${NC}"
    exit 1
fi

# Copia .env come base
cp "$ENV_FILE" "$CLOUD_ENV_FILE"

echo -e "${GREEN}✅ File base creato: ${CLOUD_ENV_FILE}${NC}"
echo ""

# Funzione per chiedere input all'utente
ask_input() {
    local prompt=$1
    local var_name=$2
    local default_value=$3
    local current_value=$(grep "^${var_name}=" "$CLOUD_ENV_FILE" | cut -d'=' -f2- | sed 's/^"//;s/"$//' || echo "")
    
    if [ -z "$current_value" ] || [ "$current_value" = "your-${var_name,,}" ] || [ "$current_value" = "YOUR_${var_name^^}" ]; then
        current_value="$default_value"
    fi
    
    echo -e "${YELLOW}${prompt}${NC}"
    echo -e "   Valore attuale: ${current_value:0:50}..."
    read -p "   Nuovo valore (Enter per mantenere): " new_value
    
    if [ -n "$new_value" ]; then
        # Sostituisci o aggiungi la variabile
        if grep -q "^${var_name}=" "$CLOUD_ENV_FILE"; then
            sed -i.bak "s|^${var_name}=.*|${var_name}=${new_value}|" "$CLOUD_ENV_FILE"
        else
            echo "${var_name}=${new_value}" >> "$CLOUD_ENV_FILE"
        fi
    fi
}

# Modifiche necessarie per Cloud Run
echo "📝 Configurazione per Cloud Run"
echo ""

# 1. LLM Provider - DEVE essere gemini
echo "🤖 LLM Provider:"
sed -i.bak "s|^LLM_PROVIDER=.*|LLM_PROVIDER=gemini|" "$CLOUD_ENV_FILE"
echo -e "${GREEN}✅ LLM_PROVIDER impostato a 'gemini'${NC}"
echo ""

# 2. Security Keys - Genera se sono default
echo "🔐 Security Keys:"
generate_security_keys=false

if grep -q "^SECRET_KEY=.*your-secret-key" "$CLOUD_ENV_FILE"; then
    echo -e "${YELLOW}⚠️  SECRET_KEY usa valore default. Genero valore sicuro...${NC}"
    NEW_SECRET_KEY=$(openssl rand -hex 32)
    sed -i.bak "s|^SECRET_KEY=.*|SECRET_KEY=${NEW_SECRET_KEY}|" "$CLOUD_ENV_FILE"
    echo -e "${GREEN}✅ SECRET_KEY generato${NC}"
    generate_security_keys=true
fi

if grep -q "^ENCRYPTION_KEY=.*your-32-byte" "$CLOUD_ENV_FILE"; then
    echo -e "${YELLOW}⚠️  ENCRYPTION_KEY usa valore default. Genero valore sicuro...${NC}"
    NEW_ENCRYPTION_KEY=$(openssl rand -hex 16)
    sed -i.bak "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=${NEW_ENCRYPTION_KEY}|" "$CLOUD_ENV_FILE"
    echo -e "${GREEN}✅ ENCRYPTION_KEY generato${NC}"
    generate_security_keys=true
fi

if grep -q "^JWT_SECRET_KEY=.*your-jwt-secret" "$CLOUD_ENV_FILE"; then
    echo -e "${YELLOW}⚠️  JWT_SECRET_KEY usa valore default. Genero valore sicuro...${NC}"
    NEW_JWT_SECRET_KEY=$(openssl rand -hex 32)
    sed -i.bak "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=${NEW_JWT_SECRET_KEY}|" "$CLOUD_ENV_FILE"
    echo -e "${GREEN}✅ JWT_SECRET_KEY generato${NC}"
    generate_security_keys=true
fi

if [ "$generate_security_keys" = false ]; then
    echo -e "${GREEN}✅ Security keys già configurate${NC}"
fi
echo ""

# 3. Database - Chiedi all'utente
echo "🗄️  Database Configuration:"
echo -e "${YELLOW}⚠️  ATTENZIONE: Il database attuale punta a localhost${NC}"
echo "   Per Cloud Run, serve database esterno (Supabase/Neon) o Cloud SQL"
echo ""
read -p "Hai già configurato DATABASE_URL per Cloud Run? (y/n): " db_configured

if [ "$db_configured" != "y" ]; then
    echo ""
    echo "Opzioni:"
    echo "  1. Database esterno (Supabase/Neon) - Consigliato"
    echo "  2. Cloud SQL - Richiede setup GCP"
    echo "  3. Salta per ora (configurare manualmente dopo)"
    read -p "Scegli opzione (1/2/3): " db_option
    
    if [ "$db_option" = "1" ]; then
        ask_input "Inserisci DATABASE_URL per database esterno:" "DATABASE_URL" ""
    elif [ "$db_option" = "2" ]; then
        echo "Per Cloud SQL, usa formato:"
        echo "postgresql+asyncpg://user:pass@/dbname?host=/cloudsql/PROJECT:REGION:INSTANCE"
        ask_input "Inserisci DATABASE_URL per Cloud SQL:" "DATABASE_URL" ""
    fi
fi
echo ""

# 4. ChromaDB - Chiedi all'utente
echo "💾 ChromaDB Configuration:"
if grep -q "^CHROMADB_HOST=localhost" "$CLOUD_ENV_FILE"; then
    echo -e "${YELLOW}⚠️  ChromaDB attualmente punta a localhost${NC}"
    echo "   Per Cloud Run, ChromaDB deve essere deployato separatamente o esterno"
    ask_input "Inserisci CHROMADB_HOST (o lascia vuoto per configurare dopo):" "CHROMADB_HOST" ""
fi
echo ""

# 5. MCP Gateway - Chiedi all'utente
echo "🔌 MCP Gateway Configuration:"
if grep -q "^MCP_GATEWAY_URL=http://localhost" "$CLOUD_ENV_FILE"; then
    echo -e "${YELLOW}⚠️  MCP Gateway attualmente punta a localhost${NC}"
    echo "   Per Cloud Run, MCP Gateway deve essere deployato separatamente"
    ask_input "Inserisci MCP_GATEWAY_URL (o lascia vuoto per configurare dopo):" "MCP_GATEWAY_URL" ""
fi
echo ""

# 6. Port - Cloud Run usa PORT automaticamente
if ! grep -q "^PORT=" "$CLOUD_ENV_FILE"; then
    echo "PORT=8000" >> "$CLOUD_ENV_FILE"
fi

# Rimuovi file backup
rm -f "${CLOUD_ENV_FILE}.bak"

echo ""
echo "======================================================"
echo -e "${GREEN}✅ File .env.cloud-run preparato!${NC}"
echo ""
echo "📝 Prossimi passi:"
echo "   1. Verifica i valori in .env.cloud-run"
echo "   2. Completa le configurazioni mancanti (Database, ChromaDB, MCP Gateway)"
echo "   3. Aggiorna Google OAuth redirect URIs per Cloud Run"
echo "   4. Procedi con deployment: ./cloud-run/deploy.sh backend"
echo ""

