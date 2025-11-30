# Cloud Storage Implementation - File Persistenti su Cloud Run

## 📋 Riepilogo

Implementazione completa di **Google Cloud Storage** per rendere i file caricati permanenti su Cloud Run, risolvendo il problema del filesystem ephemeral.

## ✅ Implementazione

### 1. Nuovo Servizio: `cloud_storage_service.py`

Servizio dedicato per gestire upload/download/delete da Cloud Storage:

- **`upload_file_to_cloud_storage()`**: Carica file su Cloud Storage
- **`download_file_from_cloud_storage()`**: Scarica file da Cloud Storage  
- **`delete_file_from_cloud_storage()`**: Elimina file da Cloud Storage
- **`is_cloud_storage_path()`**: Verifica se un filepath è un path Cloud Storage

**Caratteristiche**:
- Lazy initialization del client Cloud Storage
- Fallback automatico se Cloud Storage non è disponibile
- Gestione errori completa
- Logging dettagliato

### 2. Estensioni FileProcessor

Aggiunto supporto per estrarre testo da **bytes** invece che solo da filepath:

- **`extract_text_from_bytes()`**: Estrae testo da file bytes
- Metodi helper per ogni formato (PDF, DOCX, XLSX, TXT)
- Utilizzato quando i file vengono scaricati da Cloud Storage

### 3. Modifiche API Files

**Upload** (`POST /api/files/upload`):
- Se `USE_CLOUD_STORAGE=true` → Carica su Cloud Storage
- Se `USE_CLOUD_STORAGE=false` → Usa filesystem locale
- Fallback automatico se Cloud Storage fallisce

**Delete** (`DELETE /api/files/id/{file_id}`):
- Rileva se filepath è `gs://...` o filesystem
- Elimina da Cloud Storage o filesystem di conseguenza

### 4. Modifiche Memory Manager

**Recupero File** (`retrieve_file_content()`):
- Rileva se filepath è Cloud Storage (`gs://...`)
- Se sì → Scarica da Cloud Storage e estrae testo
- Se no → Legge dal filesystem locale
- Fallback: Se embeddings mancano, cerca file nel database e ricrea embeddings

### 5. Configurazione

**Nuove variabili d'ambiente**:
```bash
USE_CLOUD_STORAGE=false  # true per Cloud Run, false per locale
CLOUD_STORAGE_BUCKET_NAME=your-project-id-knowledge-navigator-files
```

**Config in `config.py`**:
```python
use_cloud_storage: bool = False
cloud_storage_bucket_name: Optional[str] = None
```

### 6. Dipendenze

Aggiunto a `requirements.txt`:
```txt
google-cloud-storage>=2.10.0
```

## 🔄 Comportamento

### Locale (Default)
- `USE_CLOUD_STORAGE=false` o non impostato
- File salvati in `./uploads/users/{user_id}/`
- Nessun cambiamento rispetto a prima

### Cloud Run
- `USE_CLOUD_STORAGE=true` e `CLOUD_STORAGE_BUCKET_NAME` configurato
- File salvati in `gs://bucket-name/users/{user_id}/{file_id}.ext`
- Filepath nel database: `gs://bucket-name/...`
- File persistono anche quando container si riavvia

## 📁 Struttura Filepath

### Locale
```
./uploads/users/{user_id}/{file_id}.pdf
```

### Cloud Run
```
gs://bucket-name/users/{user_id}/{file_id}.pdf
```

Il sistema rileva automaticamente il tipo di filepath e usa il metodo appropriato.

## 🚀 Setup Cloud Run

1. **Crea bucket**:
   ```bash
   ./cloud-run/setup-cloud-storage.sh
   ```

2. **Configura env vars** in Cloud Run:
   ```bash
   USE_CLOUD_STORAGE=true
   CLOUD_STORAGE_BUCKET_NAME=your-project-id-knowledge-navigator-files
   ```

3. **Rideploy backend**:
   ```bash
   ./cloud-run/deploy-enhanced.sh backend
   ```

## ✅ Vantaggi

1. **Persistenza**: File non vengono persi quando container si riavvia
2. **Scalabilità**: Cloud Storage scala automaticamente
3. **Affidabilità**: Storage gestito da Google
4. **Costi**: Free tier generoso (5GB, 50k operazioni/giorno)
5. **Trasparenza**: Locale continua a funzionare come prima

## 🔒 Sicurezza

- File isolati per user (`users/{user_id}/`)
- Permessi IAM solo al service account di Cloud Run
- Nessun accesso pubblico di default
- Filepath nel database non contiene dati sensibili

## 📊 Migrazione

I file esistenti:
- **Locale**: Continuano a funzionare (filepath locale)
- **Cloud**: Devono essere re-uploadati per essere salvati in Cloud Storage

Nuovi file:
- **Locale**: Salvati nel filesystem
- **Cloud**: Salvati in Cloud Storage se configurato

## 🧪 Testing

1. **Test locale**: Verifica che i file vengano salvati in `./uploads/`
2. **Test Cloud**: 
   - Carica un file
   - Verifica che appaia nel bucket: `gsutil ls gs://bucket-name/users/{user_id}/`
   - Chiedi un riassunto del file
   - Verifica che il contenuto sia recuperato correttamente

## 📝 Note

- Il fallback a filesystem su Cloud Run è ancora supportato ma **non è consigliato** (file saranno persi)
- I file in Cloud Storage sono accessibili solo dal backend (nessun accesso diretto da browser)
- Per accesso diretto da browser, configurare CORS e signed URLs (non implementato)

---

**Ultimo aggiornamento**: 2025-11-30

