# Verifica Documenti Auto-Coscienza

## 📋 File Documentazione Interna

I seguenti documenti sono disponibili nella directory `docs/`:

1. **INTERNAL_KNOWLEDGE_NAVIGATOR_ARCHITECTURE.md** - Panoramica completa dell'architettura
2. **INTERNAL_MEMORY_SYSTEM.md** - Sistema memoria multi-livello dettagliato
3. **INTERNAL_MULTI_AGENT_SYSTEM.md** - Architettura multi-agente e LangGraph
4. **INTERNAL_TOOL_SYSTEM.md** - Sistema tool e integrazioni
5. **INTERNAL_RAG_IMPLEMENTATION.md** - Implementazione RAG e embeddings
6. **INTERNAL_OBSERVABILITY.md** - Sistema observability (tracing, metrics)
7. **INTERNAL_DEPLOYMENT_ARCHITECTURE.md** - Architettura deployment (Cloud Run, Docker)

## 🔍 Come Verificare se sono Indicizzati

### Metodo 1: Script di Verifica (Locale)

Esegui lo script di verifica (richiede ambiente Python configurato):

```bash
cd backend/scripts
python3 verify_internal_knowledge.py
```

Questo script verifica:
- Se la collection `internal_knowledge` esiste in ChromaDB
- Quanti chunks sono indicizzati per ogni documento
- Se tutti i documenti attesi sono presenti
- Test di recupero con query di esempio

### Metodo 2: Indicizzazione Manuale

Se i documenti non sono indicizzati, esegui:

```bash
cd backend/scripts
python3 index_internal_knowledge.py
```

Questo script:
- Legge tutti i file `INTERNAL_*.md` da `docs/`
- Li chunkizza in pezzi più piccoli
- Genera embeddings per ogni chunk
- Li salva in ChromaDB nella collection `internal_knowledge`

### Metodo 3: Test Tramite API

Quando fai una query che richiede conoscenza interna, il sistema dovrebbe recuperarla automaticamente.

Query di esempio che dovrebbero triggerare il recupero:
- "Come funziona il sistema di memoria?"
- "Spiegami l'architettura multi-agente"
- "Come vengono gestiti i tool?"

Controlla i log del backend per vedere se vengono recuperati risultati da `internal_knowledge`:
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=knowledge-navigator-backend AND textPayload=~'internal_knowledge'" --limit 10 --project knowledge-navigator-477022
```

### Metodo 4: Verifica Direct ChromaDB (Solo Locale)

Se hai accesso diretto a ChromaDB (locale), puoi verificare manualmente:

```python
from app.core.memory_manager import MemoryManager
from app.services.embedding_service import EmbeddingService

memory = MemoryManager(tenant_id=None)
collection = memory.internal_knowledge_collection()

# Get all data
all_data = collection.get(where={"type": {"$eq": "internal_knowledge"}})
print(f"Total chunks: {len(all_data.get('metadatas', []))}")

# Group by document
docs = {}
for metadata in all_data.get('metadatas', []):
    doc_name = metadata.get('document', 'unknown')
    docs[doc_name] = docs.get(doc_name, 0) + 1

for doc, count in sorted(docs.items()):
    print(f"{doc}: {count} chunks")
```

## 🚀 Come Funziona

### Indicizzazione

1. I file `INTERNAL_*.md` vengono letti da `docs/`
2. Ogni file viene chunkizzato (1000 caratteri per chunk, 200 caratteri di overlap)
3. Ogni chunk viene convertito in embedding usando `all-MiniLM-L6-v2`
4. Gli embeddings vengono salvati in ChromaDB nella collection **condivisa** `internal_knowledge`
5. Metadati includono:
   - `type: "internal_knowledge"` - Identifica come conoscenza interna
   - `document: "INTERNAL_XXX.md"` - Nome del documento
   - `chunk_index: N` - Indice del chunk nel documento
   - `importance_score: "1.0"` - Priorità massima

### Recupero (RAG)

Quando l'utente fa una query meta (es. "come funziona X?"), il sistema:

1. **Genera embedding della query**
2. **Cerca in ChromaDB** nella collection `internal_knowledge`
3. **Filtra per tipo**: `where={"type": {"$eq": "internal_knowledge"}}`
4. **Recupera top-K risultati** (default: 5) per similarità semantica
5. **Aggiunge al contesto LLM** insieme alle altre memorie recuperate

Il recupero è integrato in `backend/app/api/sessions.py` nel metodo `chat()`:
- Cerca keywords come "come funziona", "architettura", "perché", "come è stato costruito"
- Se trova, aggiunge risultati da `retrieve_internal_knowledge()` al retrieved_memory

### Collection Condivisa

La collection `internal_knowledge` è **condivisa tra tutti i tenant** perché contiene solo conoscenza del sistema (non dati utente).

Questo significa:
- Indicizzazione una volta sola (non per tenant)
- Accessibile a tutti i tenant
- Più efficiente (una sola collection invece di N)

## 🔄 Re-indicizzazione Automatica

Esiste anche uno script `watch_internal_knowledge.py` per re-indicizzare automaticamente i documenti quando vengono modificati (solo in sviluppo locale).

## ⚠️ Note Importanti

1. **ChromaDB Cloud vs Locale**: 
   - Se usi ChromaDB Cloud, gli embeddings sono nel cloud
   - Se usi locale, sono nel container/volume Docker

2. **Deployment Cloud**: 
   - I documenti devono essere indicizzati anche nel deployment cloud
   - Puoi eseguire lo script di indicizzazione nel container cloud o aggiungerlo allo startup

3. **Aggiornamenti**: 
   - Se modifichi un documento `INTERNAL_*.md`, devi re-indicizzarlo
   - Usa `reindex_internal_document()` per un singolo documento
   - Oppure re-esegui `index_internal_knowledge.py` per tutti

## 📊 Stato Attuale

Per verificare lo stato attuale, esegui il metodo 1 (script di verifica) o metodo 4 (verifica diretta ChromaDB).

