# Setup ChromaDB Cloud - Guida Rapida

## 🎯 Perché ChromaDB Cloud?

- ✅ **Persistenza garantita** - Gestita da ChromaDB
- ✅ **Setup in 5 minuti** - Basta registrarsi
- ✅ **Free tier disponibile** - Perfetto per demo
- ✅ **Zero manutenzione** - Aggiornamenti automatici
- ✅ **HTTPS incluso** - Sicuro di default

## 📋 Step 1: Registrazione

1. **Vai su**: https://www.trychroma.com/cloud
2. **Clicca "Sign Up"** o "Get Started"
3. **Crea account** (puoi usare GitHub, Google, o email)
4. **Crea nuovo progetto**
5. **Ottieni credenziali**:
   - **Host URL**: `xxxxx.chromadb.cloud`
   - **API Key**: `your-api-key-here`

## 📋 Step 2: Configurazione Backend

### Opzione A: Usa HttpClient con API Key

ChromaDB HttpClient supporta API key tramite headers. Dobbiamo modificare `memory_manager.py`:

```python
# In backend/app/core/memory_manager.py
import chromadb
import os

class MemoryManager:
    def __init__(self, tenant_id: Optional[UUID] = None):
        # ChromaDB Cloud configuration
        chromadb_host = settings.chromadb_host
        chromadb_port = settings.chromadb_port
        
        # Se abbiamo API key, usala (ChromaDB Cloud)
        chromadb_api_key = getattr(settings, 'chromadb_api_key', None)
        
        if chromadb_api_key:
            # ChromaDB Cloud con API key
            self.chroma_client = chromadb.HttpClient(
                host=chromadb_host,
                port=chromadb_port,
                ssl=True,  # HTTPS per Cloud
                headers={
                    "X-Chroma-Token": chromadb_api_key
                }
            )
        else:
            # ChromaDB locale o senza auth
            self.chroma_client = chromadb.HttpClient(
                host=chromadb_host,
                port=chromadb_port,
            )
        
        # ... resto del codice
```

### Opzione B: Aggiungi chromadb_api_key a Settings

In `backend/app/core/config.py`:

```python
# ChromaDB
chromadb_host: str = "localhost"
chromadb_port: int = 8001
chromadb_api_key: Optional[str] = None  # Per ChromaDB Cloud
```

## 📋 Step 3: Aggiorna .env.cloud-run

```bash
# ChromaDB Cloud
CHROMADB_HOST=xxxxx.chromadb.cloud
CHROMADB_PORT=443
CHROMADB_API_KEY=your-api-key-here
```

## 📋 Step 4: Test

```bash
# Test connection
curl https://xxxxx.chromadb.cloud/api/v1/heartbeat \
  -H "X-Chroma-Token: your-api-key-here"
```

## ✅ Vantaggi per Demo

- ✅ **Persistenza garantita** - I dati non vengono persi
- ✅ **Setup veloce** - 15 minuti totali
- ✅ **Free tier** - Probabilmente sufficiente per demo
- ✅ **Professionale** - Mostra uso di servizi cloud gestiti

## 💰 Costi

- **Free tier**: Verifica limiti su https://www.trychroma.com/cloud
- **Piani a pagamento**: Solo se superi free tier (probabilmente non necessario per demo)

---

**Vuoi che implementi il supporto per ChromaDB Cloud nel backend?**

**Ultimo aggiornamento**: 2025-11-22

