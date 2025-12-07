# Stato Indicizzazione Documenti Auto-Coscienza

**Data Verifica**: 2025-12-03

## 📊 Risultato Verifica

### ❌ Documenti NON Indicizzati

La verifica dei log di Cloud Run (ultimi 30 giorni) **non ha trovato** alcun messaggio di recupero di `internal_knowledge`. Questo significa che:

1. I documenti INTERNAL_*.md **non sono ancora indicizzati** in ChromaDB Cloud
2. Il sistema **non può recuperare** la conoscenza interna durante le chat
3. Le domande meta (es. "come funziona X?") **non otterranno** informazioni dalla documentazione interna

## 📋 Documenti da Indicizzare

Sono presenti 7 documenti nella directory `docs/`:

1. ✅ `INTERNAL_KNOWLEDGE_NAVIGATOR_ARCHITECTURE.md`
2. ✅ `INTERNAL_MEMORY_SYSTEM.md`
3. ✅ `INTERNAL_MULTI_AGENT_SYSTEM.md`
4. ✅ `INTERNAL_TOOL_SYSTEM.md`
5. ✅ `INTERNAL_RAG_IMPLEMENTATION.md`
6. ✅ `INTERNAL_OBSERVABILITY.md`
7. ✅ `INTERNAL_DEPLOYMENT_ARCHITECTURE.md`

## 🚀 Come Indicizzare

### Opzione 1: Indicizzazione Locale (Consigliata)

Esegui lo script di indicizzazione dal tuo ambiente locale:

```bash
cd backend/scripts
python3 index_internal_knowledge.py
```

**Prerequisiti:**
- Ambiente Python con dipendenze installate (`pip install -r backend/requirements.txt`)
- File `.env` configurato con credenziali ChromaDB Cloud:
  ```
  CHROMADB_USE_CLOUD=true
  CHROMADB_CLOUD_API_KEY=ck-...
  CHROMADB_CLOUD_TENANT=c2c09e69-ec93-4583-960f-da6cc74bd1de
  CHROMADB_CLOUD_DATABASE=Knowledge Navigator
  ```

Lo script:
- Leggerà tutti i file `INTERNAL_*.md` da `docs/`
- Li chunkizzerà (1000 caratteri per chunk, 200 overlap)
- Genererà embeddings per ogni chunk
- Li salverà in ChromaDB Cloud nella collection `internal_knowledge` (condivisa tra tutti i tenant)

### Opzione 2: Indicizzazione Tramite Container Docker Locale

Se hai il backend locale in Docker:

```bash
docker-compose exec backend python backend/scripts/index_internal_knowledge.py
```

### Opzione 3: Indicizzazione su Cloud Run (Temporaneo)

Puoi creare un endpoint temporaneo nel backend per indicizzare, oppure eseguire lo script direttamente nel container Cloud Run (più complesso).

## ✅ Verifica Post-Indicizzazione

Dopo l'indicizzazione, verifica con:

### 1. Controlla i Log

```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=knowledge-navigator-backend AND textPayload=~'internal.*knowledge'" \
  --limit 10 \
  --project knowledge-navigator-477022 \
  --freshness 1h
```

Dovresti vedere messaggi come:
- `🔍 Retrieved X internal knowledge chunks`

### 2. Test Tramite Chat

Fai una domanda meta al sistema:
- "Come funziona il sistema di memoria?"
- "Spiegami l'architettura multi-agente"

La risposta dovrebbe includere informazioni dalla documentazione interna.

### 3. Verifica Script (Locale)

Esegui lo script di verifica:
```bash
python3 backend/scripts/verify_internal_knowledge_cloud.py
```

## 🔄 Note Importanti

1. **Collection Condivisa**: La collection `internal_knowledge` è condivisa tra tutti i tenant - indicizzare una volta sola è sufficiente

2. **ChromaDB Cloud**: Gli embeddings vengono salvati in ChromaDB Cloud, non nel deployment locale

3. **Re-indicizzazione**: Se modifichi un documento `INTERNAL_*.md`, devi re-indicizzarlo usando `reindex_internal_document()` o re-eseguendo lo script completo

4. **Auto-Recupero**: Il sistema cerca automaticamente nella conoscenza interna ad ogni chat (codice in `backend/app/api/sessions.py` riga 1289), quindi una volta indicizzati, verranno usati automaticamente quando rilevanti

## 📝 Prossimi Passi

1. ✅ Esegui `python3 backend/scripts/index_internal_knowledge.py` localmente
2. ✅ Verifica che lo script completi senza errori
3. ✅ Testa una domanda meta nel frontend
4. ✅ Controlla i log per confermare il recupero

