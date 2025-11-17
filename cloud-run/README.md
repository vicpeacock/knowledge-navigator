# Cloud Run Deployment Guide

Guida completa per deployare Knowledge Navigator su Google Cloud Run.

## 📋 Prerequisiti

1. **Google Cloud Account** con progetto attivo
2. **Google Cloud SDK** installato e configurato (`gcloud`)
3. **Docker** installato e funzionante
4. **Billing** abilitato sul progetto GCP

## 🚀 Quick Start

### 1. Configurazione Iniziale

```bash
# Imposta variabili ambiente
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"

# Login a Google Cloud
gcloud auth login

# Imposta progetto corrente
gcloud config set project ${GCP_PROJECT_ID}

# Abilita API necessarie
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable sqladmin.googleapis.com  # Per Cloud SQL (opzionale)
```

### 2. Database Setup

#### Opzione A: Cloud SQL (Consigliato per produzione)

```bash
# Crea istanza Cloud SQL PostgreSQL
gcloud sql instances create knowledge-navigator-db \
    --database-version=POSTGRES_16 \
    --tier=db-f1-micro \
    --region=${GCP_REGION}

# Crea database
gcloud sql databases create knowledge_navigator \
    --instance=knowledge-navigator-db

# Crea utente
gcloud sql users create knavigator \
    --instance=knowledge-navigator-db \
    --password=YOUR_SECURE_PASSWORD

# Ottieni connection name per Cloud Run
gcloud sql instances describe knowledge-navigator-db \
    --format="value(connectionName)"
```

#### Opzione B: Database Esterno

Se usi un database esterno (es. Supabase, Neon, etc.), configura solo le variabili ambiente.

### 3. ChromaDB Setup

ChromaDB può essere deployato separatamente o usato come servizio esterno. Per semplicità iniziale, puoi:

1. **Opzione A**: Deploy ChromaDB su Cloud Run separato
2. **Opzione B**: Usa ChromaDB cloud service (se disponibile)
3. **Opzione C**: Usa database esterno per embeddings (meno performante)

### 4. Variabili Ambiente

Crea file `.env.cloud-run` con le variabili necessarie:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://knavigator:PASSWORD@/knowledge_navigator?host=/cloudsql/PROJECT_ID:REGION:INSTANCE_NAME
POSTGRES_HOST=/cloudsql/PROJECT_ID:REGION:INSTANCE_NAME
POSTGRES_USER=knavigator
POSTGRES_PASSWORD=YOUR_PASSWORD
POSTGRES_DB=knowledge_navigator

# ChromaDB (se esterno)
CHROMADB_HOST=your-chromadb-host.com
CHROMADB_PORT=443

# Security
SECRET_KEY=your-secret-key-min-32-chars
ENCRYPTION_KEY=your-32-byte-encryption-key
JWT_SECRET_KEY=your-jwt-secret-key-min-32-chars

# Ollama (se usi servizio esterno)
OLLAMA_BASE_URL=https://your-ollama-service.com
OLLAMA_API_KEY=your-ollama-api-key

# Google OAuth (per Calendar/Email)
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# MCP Gateway (se deployato separatamente)
MCP_GATEWAY_URL=https://your-mcp-gateway.run.app
```

### 5. Deploy Backend

```bash
# Build e push immagine
cd /path/to/knowledge-navigator
./cloud-run/deploy.sh backend
```

Oppure manualmente:

```bash
# Build
docker build -f Dockerfile.backend -t gcr.io/${GCP_PROJECT_ID}/knowledge-navigator-backend:latest .

# Push
docker push gcr.io/${GCP_PROJECT_ID}/knowledge-navigator-backend:latest

# Deploy con variabili ambiente
gcloud run deploy knowledge-navigator-backend \
    --image gcr.io/${GCP_PROJECT_ID}/knowledge-navigator-backend:latest \
    --platform managed \
    --region ${GCP_REGION} \
    --allow-unauthenticated \
    --port 8000 \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --max-instances 10 \
    --set-env-vars-file .env.cloud-run \
    --add-cloudsql-instances ${PROJECT_ID}:${REGION}:knowledge-navigator-db
```

### 6. Deploy Frontend

```bash
# Assicurati che BACKEND_URL sia configurato
export BACKEND_URL=$(gcloud run services describe knowledge-navigator-backend \
    --region ${GCP_REGION} \
    --format 'value(status.url)')

# Deploy
./cloud-run/deploy.sh frontend
```

Oppure manualmente:

```bash
# Build
docker build -f Dockerfile.frontend -t gcr.io/${GCP_PROJECT_ID}/knowledge-navigator-frontend:latest .

# Push
docker push gcr.io/${GCP_PROJECT_ID}/knowledge-navigator-frontend:latest

# Deploy
gcloud run deploy knowledge-navigator-frontend \
    --image gcr.io/${GCP_PROJECT_ID}/knowledge-navigator-frontend:latest \
    --platform managed \
    --region ${GCP_REGION} \
    --allow-unauthenticated \
    --port 3000 \
    --memory 512Mi \
    --cpu 1 \
    --timeout 60 \
    --set-env-vars "NEXT_PUBLIC_API_URL=${BACKEND_URL}"
```

## 🔧 Configurazione Avanzata

### Health Checks

Entrambi i servizi includono health checks:
- Backend: `GET /health`
- Frontend: `GET /api/health` (se configurato)

### Scaling

Cloud Run scala automaticamente da 0 a max-instances basandosi sul traffico.

**Backend:**
- Min instances: 0 (scala da zero)
- Max instances: 10
- Memory: 2Gi
- CPU: 2

**Frontend:**
- Min instances: 0
- Max instances: 5
- Memory: 512Mi
- CPU: 1

### Database Migrations

Esegui migrations dopo il deploy:

```bash
# Ottieni shell nel container backend
gcloud run services update knowledge-navigator-backend \
    --region ${GCP_REGION} \
    --update-env-vars "RUN_MIGRATIONS=true"

# Oppure esegui manualmente
gcloud run jobs create run-migrations \
    --image gcr.io/${GCP_PROJECT_ID}/knowledge-navigator-backend:latest \
    --region ${GCP_REGION} \
    --set-env-vars-file .env.cloud-run \
    --command "alembic" \
    --args "upgrade head"
```

### Secrets Management

Per produzione, usa Google Secret Manager invece di variabili ambiente:

```bash
# Crea secret
echo -n "your-secret-value" | gcloud secrets create secret-name --data-file=-

# Grant access al service account Cloud Run
gcloud secrets add-iam-policy-binding secret-name \
    --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"

# Usa secret in Cloud Run
gcloud run services update knowledge-navigator-backend \
    --update-secrets SECRET_KEY=secret-name:latest
```

## 🧪 Testing

### Test Locale

```bash
# Test backend
docker run -p 8000:8000 \
    -e DATABASE_URL="your-db-url" \
    gcr.io/${GCP_PROJECT_ID}/knowledge-navigator-backend:latest

# Test frontend
docker run -p 3000:3000 \
    -e NEXT_PUBLIC_API_URL="http://localhost:8000" \
    gcr.io/${GCP_PROJECT_ID}/knowledge-navigator-frontend:latest
```

### Test su Cloud Run

```bash
# Ottieni URL
BACKEND_URL=$(gcloud run services describe knowledge-navigator-backend \
    --region ${GCP_REGION} \
    --format 'value(status.url)')

# Test health check
curl ${BACKEND_URL}/health

# Test API
curl ${BACKEND_URL}/api/sessions
```

## 📊 Monitoring

### Logs

```bash
# Visualizza logs backend
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=knowledge-navigator-backend" \
    --limit 50 \
    --format json

# Logs in tempo reale
gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=knowledge-navigator-backend"
```

### Metrics

Le metriche Prometheus sono disponibili su `/metrics` endpoint. Configura Cloud Monitoring per scraping.

## 🔒 Sicurezza

1. **HTTPS**: Cloud Run fornisce HTTPS automaticamente
2. **Authentication**: Configura IAM per limitare accesso se necessario
3. **Secrets**: Usa Secret Manager per credenziali sensibili
4. **CORS**: Configura CORS nel backend per il dominio frontend

## 🐛 Troubleshooting

### Backend non si avvia

1. Verifica logs: `gcloud logging read ...`
2. Verifica variabili ambiente
3. Verifica connessione database
4. Verifica health check endpoint

### Frontend non si connette al backend

1. Verifica `NEXT_PUBLIC_API_URL`
2. Verifica CORS nel backend
3. Verifica che backend sia accessibile pubblicamente

### Database connection errors

1. Verifica Cloud SQL connection name
2. Verifica che Cloud Run abbia accesso a Cloud SQL
3. Verifica credenziali database

## 📝 Checklist Pre-Deployment

- [ ] Database configurato (Cloud SQL o esterno)
- [ ] ChromaDB configurato
- [ ] Variabili ambiente preparate
- [ ] Secrets configurati (se usi Secret Manager)
- [ ] CORS configurato nel backend
- [ ] Health checks funzionanti
- [ ] Migrations eseguite
- [ ] Test locale completati
- [ ] Monitoring configurato

## 🔗 Link Utili

- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud SQL Documentation](https://cloud.google.com/sql/docs)
- [Secret Manager Documentation](https://cloud.google.com/secret-manager/docs)

## 📞 Support

Per problemi o domande, consulta:
- `docs/KAGGLE_SUBMISSION_ROADMAP.md` - Roadmap completa
- `docs/ARCHITECTURE_ANALYSIS.md` - Architettura sistema

---

**Ultimo aggiornamento**: 2025-11-17

