# Cloud Storage Setup per File Persistenti

## Panoramica

Su Cloud Run, il filesystem è **ephemeral** (temporaneo). Quando il container si riavvia o scala a zero, tutti i file salvati nel filesystem vengono persi.

Per rendere i file **permanenti**, usiamo **Google Cloud Storage** per salvare i file caricati dagli utenti.

## 🎯 Come Funziona

### Locale (Sviluppo)
- I file vengono salvati nel filesystem locale (`./uploads/users/{user_id}/`)
- Nessuna configurazione speciale richiesta
- Funziona come prima

### Cloud Run (Produzione)
- I file vengono salvati in Cloud Storage (`gs://bucket-name/users/{user_id}/{file_id}`)
- I file persistono anche quando il container si riavvia
- Configurazione richiesta (vedi sotto)

## 📋 Setup

### 1. Crea il Bucket Cloud Storage

Esegui lo script di setup:

```bash
cd cloud-run
chmod +x setup-cloud-storage.sh
./setup-cloud-storage.sh
```

Lo script:
- Crea il bucket Cloud Storage
- Configura CORS
- Configura permessi IAM per Cloud Run
- Opzionalmente configura lifecycle policy

**Oppure manualmente:**

```bash
# Imposta project
export PROJECT_ID="your-project-id"
export REGION="us-central1"
export BUCKET_NAME="${PROJECT_ID}-knowledge-navigator-files"

# Crea bucket
gsutil mb -p "$PROJECT_ID" -l "$REGION" "gs://${BUCKET_NAME}"

# Concedi permessi a Cloud Run service account
gsutil iam ch "serviceAccount:${PROJECT_ID}@appspot.gserviceaccount.com:roles/storage.objectAdmin" "gs://${BUCKET_NAME}"
```

### 2. Configura Variabili d'Ambiente

Aggiungi queste variabili al deployment Cloud Run:

```bash
USE_CLOUD_STORAGE=true
CLOUD_STORAGE_BUCKET_NAME=your-project-id-knowledge-navigator-files
```

**Durante il deploy:**

```bash
gcloud run deploy knowledge-navigator-backend \
    --set-env-vars USE_CLOUD_STORAGE=true,CLOUD_STORAGE_BUCKET_NAME=${BUCKET_NAME} \
    --region us-central1
```

**Oppure aggiorna il servizio esistente:**

```bash
gcloud run services update knowledge-navigator-backend \
    --set-env-vars USE_CLOUD_STORAGE=true,CLOUD_STORAGE_BUCKET_NAME=${BUCKET_NAME} \
    --region us-central1
```

### 3. Verifica Credenziali

Cloud Storage usa **Application Default Credentials (ADC)**:
- Su Cloud Run, le credenziali sono automatiche (service account)
- Per test locale, configura ADC:
  ```bash
  gcloud auth application-default login
  ```

## 🔄 Funzionamento

### Upload File

1. **Cloud Run** (`USE_CLOUD_STORAGE=true`):
   - File caricato → Salvato in Cloud Storage (`gs://bucket/users/{user_id}/{file_id}`)
   - Filepath nel database: `gs://bucket-name/users/{user_id}/{file_id}.pdf`

2. **Locale** (`USE_CLOUD_STORAGE=false` o non impostato):
   - File caricato → Salvato nel filesystem (`./uploads/users/{user_id}/{file_id}.pdf`)
   - Filepath nel database: `./uploads/users/{user_id}/{file_id}.pdf`

### Recupero File

1. Il sistema verifica se il filepath inizia con `gs://`
2. Se sì → Scarica da Cloud Storage
3. Se no → Legge dal filesystem locale

### Eliminazione File

1. Se filepath è `gs://` → Elimina da Cloud Storage
2. Se no → Elimina dal filesystem locale

## 📊 Struttura Bucket

```
gs://bucket-name/
└── users/
    └── {user_id}/
        ├── {file_id_1}.pdf
        ├── {file_id_2}.docx
        └── {file_id_3}.xlsx
```

## 🔒 Sicurezza

- I file sono isolati per user (`users/{user_id}/`)
- Cloud Run service account ha solo permessi sul bucket
- Nessun accesso pubblico ai file (opzionalmente configurabile)

## 💰 Costi

Cloud Storage ha un **free tier generoso**:
- 5GB storage gratuito
- 50,000 operazioni di lettura/scrittura al giorno gratuite

Per la maggior parte dei casi d'uso, i costi sono **minimali o zero**.

## ✅ Verifica Setup

Dopo il setup, verifica:

1. **Bucket creato:**
   ```bash
   gsutil ls -b gs://${BUCKET_NAME}
   ```

2. **Permessi corretti:**
   ```bash
   gsutil iam get gs://${BUCKET_NAME}
   ```

3. **Test upload** (carica un file tramite UI e verifica che appaia nel bucket)

4. **Test recupero** (chiedi un riassunto di un file caricato)

## 🐛 Troubleshooting

### Errore: "Bucket not found"
- Verifica che il bucket esista: `gsutil ls -b gs://${BUCKET_NAME}`
- Verifica che `CLOUD_STORAGE_BUCKET_NAME` sia corretto nelle env vars

### Errore: "Permission denied"
- Verifica permessi IAM: `gsutil iam get gs://${BUCKET_NAME}`
- Assicurati che il service account di Cloud Run abbia `roles/storage.objectAdmin`

### File non persistono
- Verifica che `USE_CLOUD_STORAGE=true` sia impostato
- Controlla i log per vedere se l'upload a Cloud Storage ha successo
- Verifica che il bucket esista e sia accessibile

## 📝 Note

- **Locale**: Continua a usare filesystem (nessun cambiamento)
- **Cloud**: Usa Cloud Storage solo se `USE_CLOUD_STORAGE=true`
- **Migrazione**: I file esistenti nel database con filepath locale rimangono come sono
- **Nuovi file**: Vengono salvati in Cloud Storage se abilitato

---

**Ultimo aggiornamento**: 2025-11-30

