# Fix: File Non Persistono su Cloud Run

## 🔍 Problema Identificato

I file caricati su Cloud Run non persistevano perché:
1. Il bucket Cloud Storage esisteva (`knowledge-navigator-477022-knowledge-navigator-files`)
2. Ma le variabili d'ambiente `USE_CLOUD_STORAGE` e `CLOUD_STORAGE_BUCKET_NAME` **non erano configurate** su Cloud Run
3. Il backend quindi usava il filesystem ephemeral (che viene cancellato quando il container si riavvia)

## ✅ Soluzione Applicata

### 1. Aggiunte Variabili d'Ambiente

Aggiornato il servizio Cloud Run con:

```bash
gcloud run services update knowledge-navigator-backend \
    --region us-central1 \
    --project knowledge-navigator-477022 \
    --update-env-vars USE_CLOUD_STORAGE=true,CLOUD_STORAGE_BUCKET_NAME=knowledge-navigator-477022-knowledge-navigator-files
```

**Variabili aggiunte**:
- `USE_CLOUD_STORAGE=true` - Abilita Cloud Storage
- `CLOUD_STORAGE_BUCKET_NAME=knowledge-navigator-477022-knowledge-navigator-files` - Nome del bucket

### 2. Verificati Permessi IAM

Il service account di Cloud Run (`{PROJECT_NUMBER}@appspot.gserviceaccount.com`) deve avere il ruolo `roles/storage.objectAdmin` sul bucket.

Verificato e configurato con:
```bash
gcloud storage buckets add-iam-policy-binding gs://knowledge-navigator-477022-knowledge-navigator-files \
    --member="serviceAccount:${PROJECT_NUMBER}@appspot.gserviceaccount.com" \
    --role="roles/storage.objectAdmin"
```

## 📋 Come Funziona Ora

### Upload File
1. Quando un utente carica un file, il backend controlla `USE_CLOUD_STORAGE`
2. Se `true`, carica il file su Cloud Storage: `gs://bucket/users/{user_id}/{file_id}.ext`
3. Salva il filepath GCS nel database: `gs://bucket/...`
4. Il file **persiste** anche quando il container si riavvia

### Recupero File
1. Il backend legge il filepath dal database
2. Se inizia con `gs://`, scarica da Cloud Storage
3. Estrae il testo e lo usa per RAG/chat

### File Esistenti
- I file caricati **prima** di questa fix sono andati persi (filesystem ephemeral)
- Gli utenti devono **re-uploadare** i file
- I **nuovi file** vengono salvati in Cloud Storage e persistono

## 🔍 Verifica

### Verifica Variabili d'Ambiente

```bash
gcloud run services describe knowledge-navigator-backend \
    --region us-central1 \
    --project knowledge-navigator-477022 \
    --format="value(spec.template.spec.containers[0].env)" | grep CLOUD_STORAGE
```

Dovresti vedere:
- `USE_CLOUD_STORAGE=true`
- `CLOUD_STORAGE_BUCKET_NAME=knowledge-navigator-477022-knowledge-navigator-files`

### Verifica Log Upload

Controlla i log di Cloud Run quando carichi un file:

```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=knowledge-navigator-backend AND textPayload=~'Cloud Storage'" --limit 5 --project knowledge-navigator-477022 --freshness 10m
```

Dovresti vedere messaggi come:
- `☁️  Using Cloud Storage for file upload (Cloud Run deployment)`
- `✅ File uploaded to Cloud Storage: gs://bucket/...`

### Verifica Bucket

```bash
gcloud storage ls gs://knowledge-navigator-477022-knowledge-navigator-files/users/ --project knowledge-navigator-477022
```

Dovresti vedere file organizzati per user ID: `users/{user_id}/{file_id}.ext`

## 🚨 Troubleshooting

### File Non Si Caricano

1. **Verifica variabili d'ambiente**: Vedi sopra
2. **Verifica permessi IAM**: 
   ```bash
   gcloud storage buckets get-iam-policy gs://knowledge-navigator-477022-knowledge-navigator-files --project knowledge-navigator-477022
   ```
3. **Controlla log errori**:
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=knowledge-navigator-backend AND severity>=ERROR" --limit 10 --project knowledge-navigator-477022
   ```

### File Non Si Recuperano

1. **Verifica filepath nel database**: Deve essere `gs://bucket/...`
2. **Verifica che il file esista nel bucket**:
   ```bash
   gcloud storage ls gs://knowledge-navigator-477022-knowledge-navigator-files/users/{user_id}/ --project knowledge-navigator-477022
   ```
3. **Controlla log di download**:
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=knowledge-navigator-backend AND textPayload=~'download.*Cloud Storage'" --limit 5 --project knowledge-navigator-477022
   ```

## 📝 Note Importanti

1. **File Precedenti**: I file caricati prima di questa fix sono andati persi e devono essere re-uploadati
2. **Embeddings**: Gli embeddings in ChromaDB potrebbero riferirsi a file che non esistono più. Il sistema tenta di recuperare il contenuto dal bucket, ma se il file non esiste, l'utente deve re-uploadarlo
3. **Costi**: Cloud Storage ha un free tier generoso (5GB, 50k operazioni/giorno). Per progetti più grandi, considera un lifecycle policy per eliminare file vecchi

## 🔗 Link Utili

- **Cloud Run Logs**: https://console.cloud.google.com/run/detail/us-central1/knowledge-navigator-backend/logs?project=knowledge-navigator-477022
- **Cloud Storage Console**: https://console.cloud.google.com/storage/browser/knowledge-navigator-477022-knowledge-navigator-files?project=knowledge-navigator-477022
- **Documentazione Cloud Storage**: `docs/CLOUD_STORAGE_SETUP.md`
