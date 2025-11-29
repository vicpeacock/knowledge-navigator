# Debug File Retrieval su Cloud Run

## Problema

Il riassunto dei file funziona in locale ma non su Cloud Run.

## Possibili Cause

### 1. **File non caricati correttamente su ChromaDB Cloud**

Quando un file viene caricato, deve essere:
- Salvato nel database PostgreSQL (Supabase)
- Processato per estrarre il testo
- Generato l'embedding con SentenceTransformer
- Salvato in ChromaDB Cloud nella collezione `file_embeddings_{tenant_id}`

**Verifica**:
```bash
# Controlla i log durante l'upload del file
gcloud logging tail "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"knowledge-navigator-backend\" AND textPayload:\"File embedding stored\""
```

### 2. **Problema con la query `where` su ChromaDB Cloud**

ChromaDB Cloud potrebbe avere problemi con la sintassi della query `where` quando si cerca per `session_id`.

**Soluzione implementata**: 
- Aggiunto fallback che recupera tutti i file e filtra manualmente
- Aggiunto logging dettagliato per capire dove fallisce

### 3. **Tenant ID non corrispondente**

Il `tenant_id` usato per creare la collezione potrebbe non corrispondere a quello usato per recuperare i file.

**Verifica**:
- Controlla i log per vedere quale `tenant_id` viene usato
- Verifica che il file nel database abbia lo stesso `tenant_id` della sessione

### 4. **Collezione ChromaDB non trovata**

La collezione potrebbe non esistere o avere un nome diverso su ChromaDB Cloud.

**Verifica**:
- Controlla i log per vedere se la collezione viene creata/recuperata correttamente
- Verifica il nome della collezione: dovrebbe essere `file_embeddings_{tenant_id}`

## Log da Controllare

### Durante l'Upload del File

```bash
gcloud logging tail "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"knowledge-navigator-backend\" AND (textPayload:\"File embedding stored\" OR textPayload:\"Error storing file embedding\" OR textPayload:\"No text extracted\")"
```

Cerca:
- ✅ `File embedding stored: {filename}, session: {session_id}, text length: {length}`
- ❌ `Error storing file embedding: {error}`
- ❌ `No text extracted from file: {filename}`

### Durante il Recupero del File

```bash
gcloud logging tail "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"knowledge-navigator-backend\" AND (textPayload:\"Retrieving files\" OR textPayload:\"ChromaDB query\" OR textPayload:\"No files found\" OR textPayload:\"file_embeddings\")"
```

Cerca:
- ✅ `✅ ChromaDB query successful: found {N} embeddings for session {session_id}`
- ❌ `❌ Error querying ChromaDB collection: {error}`
- ❌ `⚠️  No files found in ChromaDB for session {session_id}`
- ❌ `⚠️  Found {N} files in database but 0 embeddings in ChromaDB`

## Test Manuale

### 1. Verifica che il file esista nel database

```bash
# Usa l'API per verificare i file della sessione
curl -H "Authorization: Bearer {token}" \
  https://knowledge-navigator-backend-{project}.us-central1.run.app/api/files/session/{session_id}
```

### 2. Verifica che l'embedding esista in ChromaDB Cloud

Non c'è un endpoint diretto, ma puoi verificare tramite i log quando provi a recuperare il file.

### 3. Test di recupero file

```bash
# Invia un messaggio che richiede il riassunto del file
curl -X POST \
  -H "Authorization: Bearer {token}" \
  -H "Content-Type: application/json" \
  -d '{"message": "Riassumi il file", "session_id": "{session_id}", "use_memory": true}' \
  https://knowledge-navigator-backend-{project}.us-central1.run.app/api/sessions/{session_id}/chat
```

## Soluzioni Implementate

### 1. **Migliorato il riconoscimento ID file**

- Riconosce UUID nella query
- Verifica che il file esista nel database
- Prova multiple sintassi per la query ChromaDB
- Fallback a filtro manuale se la query fallisce

### 2. **Logging dettagliato**

- Log quando si recupera un file per ID
- Log quando si recuperano tutti i file della sessione
- Log degli errori con stack trace completo
- Log quando ci sono file nel database ma non in ChromaDB

### 3. **Gestione errori migliorata**

- Try/catch per ogni operazione ChromaDB
- Fallback a query senza `where` clause se quella con `where` fallisce
- Filtro manuale se ChromaDB Cloud non supporta la sintassi `where`

## Prossimi Passi per Debug

1. **Controlla i log durante l'upload**:
   - Verifica che l'embedding venga salvato correttamente
   - Verifica che non ci siano errori durante il salvataggio

2. **Controlla i log durante il recupero**:
   - Verifica quale errore si verifica quando si cerca di recuperare i file
   - Verifica se la collezione viene trovata correttamente
   - Verifica se ci sono file nel database ma non in ChromaDB

3. **Verifica la configurazione ChromaDB Cloud**:
   - Verifica che `CHROMADB_USE_CLOUD=true`
   - Verifica che le credenziali siano corrette
   - Verifica che il tenant e database siano corretti

4. **Test con file ID specifico**:
   - Prova a chiedere il riassunto menzionando l'ID del file
   - Verifica se il riconoscimento dell'ID funziona

## Comandi Utili

### Monitora tutti i log relativi ai file

```bash
gcloud logging tail "resource.type=\"cloud_run_revision\" AND resource.labels.service_name=\"knowledge-navigator-backend\" AND (textPayload:\"file\" OR textPayload:\"File\" OR textPayload:\"embedding\" OR textPayload:\"ChromaDB\")" \
  --project=knowledge-navigator-477022 \
  --format="value(textPayload)"
```

### Verifica la configurazione ChromaDB

```bash
gcloud run services describe knowledge-navigator-backend \
  --region=us-central1 \
  --project=knowledge-navigator-477022 \
  --format="value(spec.template.spec.containers[0].env)"
```

## Note

- ChromaDB Cloud potrebbe avere limitazioni diverse rispetto alla versione locale
- Le query `where` potrebbero richiedere sintassi diversa
- Il tenant_id deve corrispondere tra database e ChromaDB
- I file devono essere caricati nella stessa sessione per essere recuperati

