# Problema Backend Locale - Spiegazione

## 🔍 Problema Identificato

Il backend locale non si avvia perché **ChromaDB locale non risponde correttamente**.

### Errore nei Log

```
ValueError: {"detail":"Not Found"}
```

Questo errore si verifica quando il backend cerca di connettersi a ChromaDB locale su `localhost:8001` durante l'inizializzazione.

### Stato ChromaDB Locale

- **Container**: `knowledge-navigator-chromadb` è in esecuzione
- **Status**: `unhealthy` (secondo Docker healthcheck)
- **Porta**: 8001
- **Versione**: `chromadb/chroma:0.4.18` (vecchia versione)

## 🎯 Perché Funziona su Cloud Run?

Su **Cloud Run** funziona perché:
- Usiamo **ChromaDB Cloud** (servizio gestito)
- Non dipende da ChromaDB locale
- Configurazione: `CHROMADB_USE_CLOUD=true` in `.env.cloud-run`

## 🔧 Soluzioni

### Opzione 1: Riavviare ChromaDB Locale (Consigliato per sviluppo locale)

```bash
# Ferma e rimuovi il container
docker stop knowledge-navigator-chromadb
docker rm knowledge-navigator-chromadb

# Riavvia con docker-compose
docker-compose up -d chromadb

# Verifica che sia healthy
docker ps | grep chromadb
curl http://localhost:8001/api/v1/heartbeat
```

### Opzione 2: Usare ChromaDB Cloud anche in Locale

Aggiungi al file `.env`:

```bash
CHROMADB_USE_CLOUD=true
CHROMADB_CLOUD_API_KEY=ck-3DKWB3X6yC45ePgrFLEnzQWsbF8qwBwPonJQeaNCSJbp
CHROMADB_CLOUD_TENANT=c2c09e69-ec93-4583-960f-da6cc74bd1de
CHROMADB_CLOUD_DATABASE=Knowledge Navigator
```

**Nota**: Questo userà lo stesso database Cloud sia per locale che per Cloud Run.

### Opzione 3: Aggiornare ChromaDB Locale

Il container usa una versione vecchia (0.4.18). Potresti aggiornare a una versione più recente:

```yaml
# docker-compose.yml
chromadb:
  image: chromadb/chroma:latest  # o una versione specifica più recente
```

## 📊 Confronto Locale vs Cloud Run

| Componente | Locale | Cloud Run |
|------------|--------|-----------|
| **ChromaDB** | Container Docker locale (porta 8001) | ChromaDB Cloud (servizio gestito) |
| **Database** | PostgreSQL locale (porta 5432) | Supabase PostgreSQL (cloud) |
| **LLM** | Ollama locale | Gemini API (cloud) |
| **Configurazione** | `.env` | `.env.cloud-run` |

## ✅ Verifica Funzionamento

Dopo aver risolto il problema ChromaDB:

```bash
# Riavvia backend
cd backend
./start.sh

# Verifica health check
curl http://localhost:8000/health
```

---

**Ultimo aggiornamento**: 2025-11-22

