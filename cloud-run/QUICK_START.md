# Cloud Run Quick Start - Kaggle Submission

Guida rapida per deployare Knowledge Navigator su Cloud Run per la submission Kaggle.

## 🚀 Prerequisiti Rapidi

1. **Google Cloud Account** con billing abilitato
2. **Google Cloud SDK** installato (`gcloud`)
3. **Docker** installato e funzionante

## ⚡ Setup Veloce (30 minuti)

### 1. Verifica Prerequisiti

```bash
# Verifica gcloud
gcloud --version

# Verifica docker
docker --version

# Se mancano, installa:
# - gcloud: https://cloud.google.com/sdk/docs/install
# - docker: https://docs.docker.com/get-docker/
```

### 2. Login e Setup Progetto

```bash
# Login a Google Cloud
gcloud auth login

# Crea nuovo progetto (o usa esistente)
export GCP_PROJECT_ID="knowledge-navigator-kaggle-$(date +%s)"
gcloud projects create ${GCP_PROJECT_ID} --name="Knowledge Navigator Kaggle"

# Imposta progetto corrente
gcloud config set project ${GCP_PROJECT_ID}

# Abilita API necessarie
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable secretmanager.googleapis.com

# Configura Docker per GCR
gcloud auth configure-docker
```

### 3. Database Setup (Opzione Veloce: Database Esterno)

**Per velocità, usa un database esterno** (Supabase, Neon, etc.) invece di Cloud SQL:

1. Crea account su [Supabase](https://supabase.com) o [Neon](https://neon.tech)
2. Crea nuovo progetto
3. Copia connection string (formato: `postgresql+asyncpg://user:pass@host:port/dbname`)

**Oppure usa Cloud SQL** (più lento ma più integrato):

```bash
# Crea istanza Cloud SQL (richiede 5-10 minuti)
gcloud sql instances create knowledge-navigator-db \
    --database-version=POSTGRES_16 \
    --tier=db-f1-micro \
    --region=us-central1

# Crea database
gcloud sql databases create knowledge_navigator \
    --instance=knowledge-navigator-db

# Crea utente
gcloud sql users create knavigator \
    --instance=knowledge-navigator-db \
    --password=YOUR_SECURE_PASSWORD
```

### 4. Gemini API Key

1. Vai su https://aistudio.google.com/app/apikey
2. Crea nuova API key
3. Copia la chiave

### 5. Configura Variabili Ambiente

Crea file `.env.cloud-run`:

```bash
cd /path/to/knowledge-navigator
cp cloud-run/env.example .env.cloud-run
```

Modifica `.env.cloud-run` con i tuoi valori:

```bash
# LLM Provider - MUST be "gemini" for cloud
LLM_PROVIDER=gemini

# Gemini API Key (usa Secret Manager per produzione)
GEMINI_API_KEY=your-gemini-api-key-here
GEMINI_MODEL=gemini-1.5-pro

# Database (usa connection string del tuo database)
DATABASE_URL=postgresql+asyncpg://user:pass@host:port/dbname

# Security Keys (GENERA VALORI SICURI!)
SECRET_KEY=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(openssl rand -hex 16)  # 32 chars
JWT_SECRET_KEY=$(openssl rand -hex 32)

# Port
PORT=8000
```

### 6. Deploy Backend

```bash
# Imposta variabili
export GCP_PROJECT_ID="your-project-id"
export GCP_REGION="us-central1"
export GEMINI_API_KEY="your-gemini-api-key"

# Deploy
./cloud-run/deploy.sh backend
```

### 7. Deploy Frontend

```bash
# Deploy (usa URL backend automaticamente)
./cloud-run/deploy.sh frontend
```

### 8. Test

```bash
# Ottieni URL
BACKEND_URL=$(gcloud run services describe knowledge-navigator-backend \
    --region us-central1 \
    --format 'value(status.url)')

FRONTEND_URL=$(gcloud run services describe knowledge-navigator-frontend \
    --region us-central1 \
    --format 'value(status.url)')

# Test health check
curl ${BACKEND_URL}/health

# Apri frontend
open ${FRONTEND_URL}
```

## 🎯 Checklist Veloce

- [ ] gcloud installato e configurato
- [ ] Docker installato e funzionante
- [ ] Progetto GCP creato
- [ ] API abilitate (Run, Container Registry, Secret Manager)
- [ ] Database configurato (esterno o Cloud SQL)
- [ ] Gemini API key ottenuta
- [ ] File `.env.cloud-run` creato e configurato
- [ ] Backend deployato
- [ ] Frontend deployato
- [ ] Test end-to-end completati

## ⚠️ Note Importanti

1. **Database**: Per velocità, usa database esterno (Supabase/Neon). Cloud SQL richiede più tempo.
2. **Gemini API Key**: Puoi usarla come env var per demo, ma usa Secret Manager per produzione.
3. **Costi**: Cloud Run scala a zero quando non usato. Database esterno può essere gratuito (tier free).
4. **Migrations**: Esegui migrations dopo il deploy (vedi README.md completo).

## 🔗 Link Utili

- [Cloud Run Pricing](https://cloud.google.com/run/pricing)
- [Supabase Free Tier](https://supabase.com/pricing)
- [Neon Free Tier](https://neon.tech/pricing)
- [Gemini API Key](https://aistudio.google.com/app/apikey)

---

**Tempo stimato**: 30-60 minuti per setup completo

