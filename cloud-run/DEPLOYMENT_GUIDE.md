# Guida Deployment Cloud Run - Step by Step

## 🎯 Prerequisiti Verificati

- ✅ gcloud CLI installato
- ✅ Docker installato
- ✅ Progetti GCP disponibili

## 📋 Step 1: Scegli Progetto GCP

Hai questi progetti disponibili:
- `gen-lang-client-0919247386` - Knowledge Navigator
- `knowledge-navigator-477022` - Knowledge Navigator
- Altri progetti...

**Scegli quale progetto usare** o creane uno nuovo.

## 📋 Step 2: Verifica Configurazione

Lo script `deploy-enhanced.sh` carica automaticamente tutte le variabili da `.env.cloud-run`.

**Variabili richieste**:
- `GCP_PROJECT_ID` - ID progetto GCP
- `GCP_REGION` - Regione (default: us-central1)
- `DATABASE_URL` - Connection string Supabase
- `CHROMADB_USE_CLOUD=true`
- `CHROMADB_CLOUD_API_KEY`
- `CHROMADB_CLOUD_TENANT`
- `CHROMADB_CLOUD_DATABASE`
- `GEMINI_API_KEY`
- `SECRET_KEY`, `ENCRYPTION_KEY`, `JWT_SECRET_KEY`
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `GOOGLE_PSE_API_KEY`, `GOOGLE_PSE_CX`

## 📋 Step 3: Deploy

### Opzione A: Deploy Completo (Backend + Frontend)

```bash
# Imposta progetto GCP (se non già in .env.cloud-run)
export GCP_PROJECT_ID="knowledge-navigator-477022"
export GCP_REGION="us-central1"

# Deploy tutto
./cloud-run/deploy-enhanced.sh all
```

### Opzione B: Deploy Step by Step

```bash
# 1. Deploy Backend
./cloud-run/deploy-enhanced.sh backend

# 2. Attendi che backend sia ready (10-15 secondi)

# 3. Deploy Frontend
./cloud-run/deploy-enhanced.sh frontend
```

## 📋 Step 4: Verifica Deployment

Dopo il deployment, lo script mostrerà gli URL:
- Backend URL: `https://knowledge-navigator-backend-xxxxx.run.app`
- Frontend URL: `https://knowledge-navigator-frontend-xxxxx.run.app`

### Test Rapido

```bash
# Health check backend
curl https://knowledge-navigator-backend-xxxxx.run.app/health

# Apri frontend nel browser
open https://knowledge-navigator-frontend-xxxxx.run.app
```

## 🔧 Troubleshooting

### Errore: "Project not found"
```bash
# Verifica progetto
gcloud projects list

# Imposta progetto
gcloud config set project YOUR_PROJECT_ID
export GCP_PROJECT_ID="YOUR_PROJECT_ID"
```

### Errore: "Permission denied"
```bash
# Login
gcloud auth login

# Verifica permessi
gcloud projects get-iam-policy YOUR_PROJECT_ID
```

### Errore: "API not enabled"
```bash
# Abilita API necessarie
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
gcloud services enable secretmanager.googleapis.com
```

### Errore: "Docker build failed"
```bash
# Verifica Docker
docker --version
docker ps

# Verifica autenticazione GCR
gcloud auth configure-docker
```

## 📝 Note Importanti

1. **Prima volta**: Il build delle immagini Docker può richiedere 5-10 minuti
2. **Deploy successivi**: Più veloci (solo push immagine)
3. **Costi**: Cloud Run scala a zero quando non usato (gratis quando idle)
4. **Database**: Assicurati che Supabase sia accessibile da Cloud Run
5. **ChromaDB Cloud**: Già configurato e testato ✅

## 🚀 Prossimi Step

Dopo il deployment:
1. Test end-to-end
2. Verifica funzionalità principali
3. Preparazione video demo
4. Writeup finale

---

**Ultimo aggiornamento**: 2025-11-22

