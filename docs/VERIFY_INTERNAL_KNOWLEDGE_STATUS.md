# Verifica Stato Indicizzazione Documenti Auto-Coscienza

## 🔍 Metodo Rapido: Verifica Tramite Log

Il modo più semplice per verificare se i documenti sono indicizzati è controllare i log di Cloud Run:

```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=knowledge-navigator-backend AND textPayload=~'internal.*knowledge'" \
  --limit 20 \
  --project knowledge-navigator-477022 \
  --freshness 7d
```

**Cosa cercare:**
- `🔍 Retrieved X internal knowledge chunks` - significa che sono indicizzati e recuperati
- Nessun risultato = probabilmente non indicizzati

## 📋 Documenti Attesi

7 documenti dovrebbero essere indicizzati:
1. INTERNAL_KNOWLEDGE_NAVIGATOR_ARCHITECTURE.md
2. INTERNAL_MEMORY_SYSTEM.md
3. INTERNAL_MULTI_AGENT_SYSTEM.md
4. INTERNAL_TOOL_SYSTEM.md
5. INTERNAL_RAG_IMPLEMENTATION.md
6. INTERNAL_OBSERVABILITY.md
7. INTERNAL_DEPLOYMENT_ARCHITECTURE.md

## 🚀 Indicizzazione

Se i documenti NON sono indicizzati, devono essere indicizzati in ChromaDB Cloud.

### Opzione 1: Indicizzazione Manuale (Locale)

Esegui lo script di indicizzazione localmente (richiede connessione a ChromaDB Cloud):

```bash
cd backend/scripts
python3 index_internal_knowledge.py
```

**Prerequisiti:**
- Python ambiente con dipendenze installate
- Variabili d'ambiente ChromaDB Cloud configurate nel `.env`:
  - `CHROMADB_USE_CLOUD=true`
  - `CHROMADB_CLOUD_API_KEY=...`
  - `CHROMADB_CLOUD_TENANT=...`
  - `CHROMADB_CLOUD_DATABASE=...`

### Opzione 2: Indicizzazione Tramite Backend API (Cloud)

Puoi creare un endpoint temporaneo nel backend per indicizzare, oppure eseguire lo script nel container Cloud Run.

## ✅ Verifica Post-Indicizzazione

Dopo l'indicizzazione, verifica con:

1. **Log Cloud Run**: Cerca messaggi di recupero
2. **Test Chat**: Fai una domanda meta come "Come funziona il sistema di memoria?"
3. **Verifica Risultati**: La risposta dovrebbe includere informazioni dalla documentazione interna

## 📊 Risultato Verifica Attuale

Esegui il comando sopra per vedere lo stato corrente. Se non ci sono log di recupero, i documenti probabilmente non sono indicizzati.

