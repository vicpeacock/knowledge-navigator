# ChromaDB HTTPS Configuration per Cloud Run

## ⚠️ Problema

ChromaDB client usa `HttpClient` che di default si connette via HTTP. Cloud Run espone servizi via HTTPS.

## ✅ Soluzione

Il client ChromaDB supporta HTTPS automaticamente se l'host inizia con `https://` o se la porta è 443.

### Configurazione Corretta

Nel file `.env.cloud-run`, usa:

```bash
# Opzione 1: URL completo con https://
CHROMADB_HOST=https://knowledge-navigator-chromadb-xxxxx.run.app
CHROMADB_PORT=443

# Opzione 2: Solo hostname (ChromaDB userà HTTPS se porta è 443)
CHROMADB_HOST=knowledge-navigator-chromadb-xxxxx.run.app
CHROMADB_PORT=443
```

### Verifica nel Codice

Il client ChromaDB `HttpClient` costruisce l'URL così:
- Se `host` inizia con `http://` o `https://`, usa quello
- Altrimenti, costruisce `http://{host}:{port}`

**Per Cloud Run**, dobbiamo assicurarci che usi HTTPS. Possiamo:
1. Passare URL completo con `https://` nell'host
2. O modificare il codice per supportare HTTPS esplicitamente

### Modifica Temporanea (se necessario)

Se il client non supporta HTTPS automaticamente, possiamo modificare `memory_manager.py`:

```python
# Invece di:
self.chroma_client = chromadb.HttpClient(
    host=settings.chromadb_host,
    port=settings.chromadb_port,
)

# Usa:
chromadb_host = settings.chromadb_host
if not chromadb_host.startswith('http'):
    # Cloud Run usa HTTPS
    if settings.chromadb_port == 443:
        chromadb_host = f"https://{chromadb_host}"
    else:
        chromadb_host = f"http://{chromadb_host}:{settings.chromadb_port}"

self.chroma_client = chromadb.HttpClient(host=chromadb_host)
```

**Nota**: Verifica prima se il client supporta già HTTPS. La maggior parte dei client HTTP moderni lo supportano automaticamente.

---

**Ultimo aggiornamento**: 2025-11-22

