# Deployment Cloud Run - Senza MCP Gateway

Questa guida spiega come deployare Knowledge Navigator su Cloud Run **senza MCP Gateway** ma **con ChromaDB** (necessario).

## 📋 Prerequisiti

- ✅ GCP Project configurato
- ✅ Database Supabase configurato
- ✅ `.env.cloud-run` preparato

## 🚀 Deployment Step-by-Step

### Step 1: Deploy ChromaDB (NECESSARIO)

ChromaDB è necessario per la memoria long-term. Deployalo come servizio separato:

```bash
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"

# Deploy ChromaDB
./cloud-run/deploy-chromadb.sh
```

Questo creerà un servizio Cloud Run chiamato `knowledge-navigator-chromadb`.

### Step 2: Aggiorna Configurazione ChromaDB

Dopo il deployment, aggiorna `.env.cloud-run` con l'URL di ChromaDB:

```bash
# Aggiorna automaticamente .env.cloud-run
./cloud-run/update-chromadb-config.sh
```

Oppure manualmente:
1. Ottieni URL ChromaDB:
   ```bash
   gcloud run services describe knowledge-navigator-chromadb \
       --region us-central1 \
       --format 'value(status.url)'
   ```

2. Aggiorna `.env.cloud-run`:
   ```bash
   CHROMADB_HOST=knowledge-navigator-chromadb-xxxxx.run.app
   CHROMADB_PORT=443
   ```

### Step 3: Disabilita MCP Gateway (Opzionale)

MCP Gateway non è necessario. Puoi lasciare la configurazione come `localhost` - l'app funzionerà senza MCP tools.

Se vuoi essere esplicito, puoi commentare o rimuovere:
```bash
# MCP_GATEWAY_URL=http://localhost:8080
# MCP_GATEWAY_AUTH_TOKEN=...
```

### Step 4: Deploy Backend

```bash
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"

# Deploy backend
./cloud-run/deploy.sh backend
```

Il backend userà:
- ✅ Database Supabase
- ✅ ChromaDB su Cloud Run
- ❌ MCP Gateway (non disponibile, ma non necessario)

### Step 5: Deploy Frontend

```bash
# Deploy frontend
./cloud-run/deploy.sh frontend
```

## ⚠️ Note Importanti

### ChromaDB Persistenza

**IMPORTANTE**: ChromaDB su Cloud Run **non è persistente** di default. I dati vengono persi quando il servizio scala a zero o viene riavviato.

**Opzioni per persistenza**:
1. **Cloud Storage** (consigliato): Monta un bucket Cloud Storage come volume
2. **Database esterno**: Usa ChromaDB con backend PostgreSQL (più complesso)
3. **Accettare perdita dati**: Per demo, può essere accettabile

**Per ora**: Per la demo Kaggle, possiamo accettare che i dati non siano persistenti. Per produzione, configura Cloud Storage.

### MCP Gateway

- **Non necessario** per funzionalità base
- L'app funzionerà senza MCP tools
- Gli utenti non potranno usare Google Workspace MCP tools
- Tutte le altre funzionalità funzioneranno normalmente

## ✅ Checklist Deployment

- [ ] ChromaDB deployato su Cloud Run
- [ ] `.env.cloud-run` aggiornato con URL ChromaDB
- [ ] Backend deployato
- [ ] Frontend deployato
- [ ] Test health check completati
- [ ] Test funzionalità base (chat, memoria)

## 🧪 Test

```bash
# Test ChromaDB
CHROMADB_URL=$(gcloud run services describe knowledge-navigator-chromadb \
    --region us-central1 \
    --format 'value(status.url)')
curl ${CHROMADB_URL}/api/v1/heartbeat

# Test Backend
BACKEND_URL=$(gcloud run services describe knowledge-navigator-backend \
    --region us-central1 \
    --format 'value(status.url)')
curl ${BACKEND_URL}/health

# Test Frontend
FRONTEND_URL=$(gcloud run services describe knowledge-navigator-frontend \
    --region us-central1 \
    --format 'value(status.url)')
open ${FRONTEND_URL}
```

## 📝 Configurazione Finale

Il tuo `.env.cloud-run` dovrebbe avere:

```bash
# Database
# IMPORTANTE: Ottieni la connection string completa da Supabase Dashboard
# Vai su: https://app.supabase.com/project/YOUR_PROJECT_ID/settings/database
# Copia la connection string URI completa e usala come DATABASE_URL
# Formato: postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres
# NOTA: Sostituisci [PASSWORD] e [PROJECT] con i tuoi valori reali
DATABASE_URL=postgresql+asyncpg://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres

# ChromaDB (da Cloud Run)
CHROMADB_HOST=knowledge-navigator-chromadb-xxxxx.run.app
CHROMADB_PORT=443

# MCP Gateway (non necessario, può essere localhost o commentato)
# MCP_GATEWAY_URL=http://localhost:8080
```

---

**Ultimo aggiornamento**: 2025-11-22

