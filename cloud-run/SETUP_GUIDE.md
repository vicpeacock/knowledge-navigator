# Setup Guide - Punti 2-4

Guida passo-passo per configurare progetto GCP, database e Gemini API key.

---

## 📋 Punto 2: Creare Progetto GCP

### Opzione A: Creare Nuovo Progetto (Consigliato per Kaggle)

1. **Vai alla Console Google Cloud**
   - Link: https://console.cloud.google.com/
   - Login con il tuo account Google

2. **Crea Nuovo Progetto**
   - Link diretto: https://console.cloud.google.com/projectcreate
   - **Nome progetto**: `knowledge-navigator-kaggle` (o qualsiasi nome)
   - **Organizzazione**: Lascia default o seleziona la tua
   - Clicca **"Crea"**

3. **Abilita Billing** (NECESSARIO per Cloud Run)
   - Link: https://console.cloud.google.com/billing
   - Se non hai billing account, creane uno:
     - Link: https://console.cloud.google.com/billing/create
     - Segui la procedura (richiede carta di credito)
   - **Nota**: Cloud Run ha free tier generoso, ma billing è necessario

4. **Collega Billing al Progetto**
   - Vai su: https://console.cloud.google.com/billing
   - Seleziona il tuo billing account
   - Clicca **"Modifica associazioni progetto"**
   - Aggiungi il progetto appena creato

5. **Configura gcloud CLI**
   ```bash
   # Imposta progetto corrente
   export GCP_PROJECT_ID="knowledge-navigator-kaggle"  # o il nome che hai scelto
   gcloud config set project ${GCP_PROJECT_ID}
   
   # Verifica
   gcloud config get-value project
   ```

6. **Abilita API Necessarie**
   ```bash
   # Cloud Run API
   gcloud services enable run.googleapis.com
   
   # Container Registry API
   gcloud services enable containerregistry.googleapis.com
   
   # Secret Manager API (per Gemini API key)
   gcloud services enable secretmanager.googleapis.com
   
   # Cloud SQL API (solo se usi Cloud SQL)
   gcloud services enable sqladmin.googleapis.com
   ```

   **Oppure via Console Web**:
   - Link: https://console.cloud.google.com/apis/library
   - Cerca e abilita:
     - "Cloud Run API"
     - "Container Registry API"
     - "Secret Manager API"
     - "Cloud SQL Admin API" (solo se usi Cloud SQL)

### Opzione B: Usare Progetto Esistente

Se hai già un progetto GCP:

```bash
# Lista progetti esistenti
gcloud projects list

# Imposta progetto esistente
export GCP_PROJECT_ID="your-existing-project-id"
gcloud config set project ${GCP_PROJECT_ID}

# Abilita API (vedi sopra)
```

---

## 📋 Punto 3: Configurare Database

### Opzione A: Database Esterno (Consigliato - Più Veloce) ⚡

**Vantaggi**: Setup veloce, free tier disponibile, no configurazione Cloud SQL

#### Supabase (Consigliato)

1. **Crea Account Supabase**
   - Link: https://supabase.com/
   - Clicca **"Start your project"**
   - Login con GitHub o email

2. **Crea Nuovo Progetto**
   - Link: https://app.supabase.com/project/_/settings/database
   - Clicca **"New Project"**
   - **Nome**: `knowledge-navigator-kaggle`
   - **Database Password**: Genera password sicura (salvala!)
   - **Region**: Scegli la più vicina (es. `us-east-1`)
   - Clicca **"Create new project"**
   - Attendi 2-3 minuti per il setup

3. **Ottieni Connection String**
   - Vai su: https://app.supabase.com/project/_/settings/database
   - Seleziona il tuo progetto
   - Vai su **"Settings"** → **"Database"**
   - Scrolla fino a **"Connection string"**
   - Seleziona **"URI"** tab
   - Copia la connection string (formato: `postgresql://postgres:[PASSWORD]@[HOST]:5432/postgres`)
   - **Modifica per asyncpg**: Sostituisci `postgresql://` con `postgresql+asyncpg://`
   - Esempio: `postgresql+asyncpg://postgres:password@db.xxxxx.supabase.co:5432/postgres`

4. **Test Connection** (opzionale)
   ```bash
   # Installa psql se non ce l'hai
   # Mac: brew install postgresql
   
   # Test connection
   psql "postgresql://postgres:password@db.xxxxx.supabase.co:5432/postgres"
   ```

#### Neon (Alternativa)

1. **Crea Account Neon**
   - Link: https://neon.tech/
   - Clicca **"Sign Up"**
   - Login con GitHub o email

2. **Crea Nuovo Progetto**
   - Link: https://console.neon.tech/
   - Clicca **"New Project"**
   - **Nome**: `knowledge-navigator-kaggle`
   - **Region**: Scegli la più vicina
   - Clicca **"Create Project"**

3. **Ottieni Connection String**
   - Nel dashboard, vai su **"Connection Details"**
   - Copia la connection string
   - **Modifica per asyncpg**: Sostituisci `postgresql://` con `postgresql+asyncpg://`

#### Altri Database Esterni

- **Railway**: https://railway.app/ (free tier)
- **Render**: https://render.com/ (free tier limitato)
- **ElephantSQL**: https://www.elephantsql.com/ (free tier)

### Opzione B: Cloud SQL (Più Integrato ma Più Lento) 🐌

**Vantaggi**: Integrato con GCP, gestione automatica, backup automatici  
**Svantaggi**: Setup più lungo (10-15 minuti), configurazione più complessa

1. **Crea Istanza Cloud SQL**
   - Link: https://console.cloud.google.com/sql/instances
   - Clicca **"Create Instance"**
   - Seleziona **"PostgreSQL"**
   - **Instance ID**: `knowledge-navigator-db`
   - **Password**: Genera password sicura (salvala!)
   - **Region**: Scegli la stessa del Cloud Run (es. `us-central1`)
   - **Database Version**: PostgreSQL 16
   - **Machine Type**: 
     - **Development**: `db-f1-micro` (shared-core, ~$7/mese)
     - **Production**: `db-g1-small` (1 vCPU, ~$25/mese)
   - Clicca **"Create"**
   - **Attendi 5-10 minuti** per il provisioning

2. **Crea Database**
   - Link: https://console.cloud.google.com/sql/instances
   - Seleziona l'istanza appena creata
   - Vai su **"Databases"** tab
   - Clicca **"Create Database"**
   - **Nome**: `knowledge_navigator`
   - Clicca **"Create"**

3. **Crea Utente**
   - Nella stessa pagina, vai su **"Users"** tab
   - Clicca **"Add User Account"**
   - **Username**: `knavigator`
   - **Password**: Genera password sicura (salvala!)
   - Clicca **"Add"**

4. **Ottieni Connection Name**
   ```bash
   # Via CLI
   gcloud sql instances describe knowledge-navigator-db \
       --format="value(connectionName)"
   
   # Output: PROJECT_ID:REGION:INSTANCE_NAME
   ```

5. **Connection String per Cloud SQL**
   - Formato: `postgresql+asyncpg://USER:PASSWORD@/DATABASE?host=/cloudsql/CONNECTION_NAME`
   - Esempio: `postgresql+asyncpg://knavigator:password@/knowledge_navigator?host=/cloudsql/my-project:us-central1:knowledge-navigator-db`

---

## 📋 Punto 4: Ottenere Gemini API Key

### Step 1: Vai a Google AI Studio

- Link: https://aistudio.google.com/app/apikey
- Login con il tuo account Google

### Step 2: Crea API Key

1. **Crea Nuova API Key**
   - Clicca **"Create API Key"** (o **"Get API Key"**)
   - Seleziona il progetto GCP (o creane uno nuovo)
   - Clicca **"Create API key in new project"** o seleziona progetto esistente
   - **API key creata!** Copia la chiave (inizia con `AIza...`)

2. **Salva API Key in Posto Sicuro**
   - ⚠️ **IMPORTANTE**: Non condividere questa chiave pubblicamente
   - Salvala in un file sicuro (es. `.env.cloud-run` - già nel .gitignore)
   - Non committarla su GitHub!

### Step 3: Configura API Key in Cloud Run (Opzionale - Per Produzione)

Per maggiore sicurezza, usa Google Secret Manager invece di variabile ambiente:

```bash
# Crea secret
echo -n "your-gemini-api-key-here" | gcloud secrets create gemini-api-key \
    --data-file=- \
    --project=${GCP_PROJECT_ID}

# Grant access al service account Cloud Run
PROJECT_NUMBER=$(gcloud projects describe ${GCP_PROJECT_ID} --format="value(projectNumber)")
gcloud secrets add-iam-policy-binding gemini-api-key \
    --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --project=${GCP_PROJECT_ID}
```

**Per ora, puoi usarla come variabile ambiente** (più semplice per demo).

### Step 4: Verifica API Key

```bash
# Test API key (opzionale)
curl "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key=YOUR_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"contents":[{"parts":[{"text":"Hello"}]}]}'
```

---

## ✅ Checklist Completa

### Punto 2: Progetto GCP
- [ ] Account Google Cloud attivo
- [ ] Progetto GCP creato
- [ ] Billing account collegato
- [ ] API abilitate (Run, Container Registry, Secret Manager)
- [ ] gcloud configurato con progetto

### Punto 3: Database
- [ ] Database esterno creato (Supabase/Neon) **O** Cloud SQL istanza creata
- [ ] Connection string ottenuta
- [ ] Database creato (se Cloud SQL)
- [ ] Utente creato (se Cloud SQL)
- [ ] Connection string testata (opzionale)

### Punto 4: Gemini API Key
- [ ] API key ottenuta da Google AI Studio
- [ ] API key salvata in posto sicuro
- [ ] Secret Manager configurato (opzionale, per produzione)

---

## 🔗 Link Utili Riepilogo

### Google Cloud
- Console: https://console.cloud.google.com/
- Creazione Progetto: https://console.cloud.google.com/projectcreate
- Billing: https://console.cloud.google.com/billing
- API Library: https://console.cloud.google.com/apis/library
- Cloud SQL: https://console.cloud.google.com/sql/instances

### Database Esterni
- Supabase: https://supabase.com/
- Neon: https://neon.tech/
- Railway: https://railway.app/
- Render: https://render.com/

### Gemini API
- Google AI Studio: https://aistudio.google.com/app/apikey
- Gemini API Docs: https://ai.google.dev/docs

---

## 📝 Prossimo Passo

Una volta completati i punti 2-4, procedi con:
- Configurazione variabili ambiente (`.env.cloud-run`)
- Deploy backend su Cloud Run
- Deploy frontend su Cloud Run

Vedi `cloud-run/QUICK_START.md` per i prossimi passi.

---

**Ultimo aggiornamento**: 2025-11-22

