# Setup Background Agent - llama.cpp Native

## Overview

Il Background Agent usa **llama.cpp nativo** (non Docker) con un modello piccolo quantizzato (`Phi-3-mini-4k-instruct-q4`) per eseguire task in background senza occupare il modello principale. Questo approccio offre:
- **Prestazioni migliori** su Mac (usa Metal/GPU nativamente)
- **Latenza ridotta** (~2 secondi vs timeout precedenti)
- **Nessun overhead Docker** per il background agent

## Setup Step-by-Step

### 1. Avviare i Container Docker (PostgreSQL e ChromaDB)

```bash
# Avvia solo postgres e chromadb (ollama-background non è più necessario)
docker-compose up -d postgres chromadb

# Verifica che i container siano in esecuzione
docker-compose ps
```

Dovresti vedere:
- `knowledge-navigator-postgres` (porta 5432)
- `knowledge-navigator-chromadb` (porta 8001)

### 2. Installare llama.cpp (se non già installato)

```bash
# Installa llama.cpp via Homebrew
brew install llama.cpp
```

### 3. Scaricare il Modello Phi-3-mini Q4

```bash
# Crea directory per i modelli
mkdir -p ~/models/llama-cpp

# Scarica il modello quantizzato (2.2GB)
cd ~/models/llama-cpp
hf download microsoft/Phi-3-mini-4k-instruct-GGUF Phi-3-mini-4k-instruct-q4.gguf
```

### 4. Avviare llama-server

```bash
# Usa lo script fornito
./scripts/start_llama_background.sh

# Oppure manualmente:
cd ~/models/llama-cpp
llama-server \
  -m Phi-3-mini-4k-instruct-q4.gguf \
  --port 11435 \
  --host 127.0.0.1 \
  --ctx-size 4096 \
  --threads 8 \
  --n-gpu-layers 999 \
  > /tmp/llama-background.log 2>&1 &
```

### 5. Verificare che llama-server sia in Esecuzione

```bash
# Verifica il processo
ps aux | grep "llama-server.*11435" | grep -v grep

# Testa l'API
curl http://localhost:11435/v1/models
```

Dovresti vedere il modello `Phi-3-mini-4k-instruct-q4.gguf` nella risposta.

### 6. Configurare il Backend

Il backend è già configurato per usare llama.cpp. Verifica in `backend/app/core/config.py`:

```python
use_llama_cpp_background: bool = True  # Usa llama.cpp invece di Ollama
ollama_background_base_url: str = "http://localhost:11435"
ollama_background_model: str = "Phi-3-mini-4k-instruct-q4"
```

### 7. Avviare il Backend

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

### 8. Verificare lo Stato

```bash
# Health check
curl http://localhost:8000/health | python3 -m json.tool
```

Dovresti vedere:
```json
{
    "all_healthy": true,
    "services": {
        "ollama_background": {
            "healthy": true,
            "message": "llama.cpp background connection successful, model 'Phi-3-mini-4k-instruct-q4' available"
        }
    }
}
```

## Troubleshooting

### llama-server non parte

```bash
# Verifica che la porta 11435 non sia occupata
lsof -i :11435

# Se occupata, ferma il processo o cambia porta
kill <PID>
```

### Modello non trovato

```bash
# Verifica che il modello esista
ls -lh ~/models/llama-cpp/Phi-3-mini-4k-instruct-q4.gguf

# Verifica che llama-server lo stia usando
curl http://localhost:11435/v1/models | python3 -m json.tool
```

### Backend non si connette

```bash
# Verifica che llama-server risponda
curl http://localhost:11435/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "test"}], "max_tokens": 10}'

# Verifica i log
tail -f /tmp/llama-background.log
```

### Performance lente

- Assicurati che `--n-gpu-layers 999` sia impostato per usare Metal/GPU
- Verifica che il modello sia quantizzato Q4 (non FP16)
- Aumenta `--threads` se hai più core CPU disponibili

## Avvio Automatico (opzionale)

Per avviare llama-server automaticamente all'avvio del sistema, vedi `GPU_ACCELERATION_MAC.md` per istruzioni su come configurare `launchd`.

## Note

- **Porta 11435**: Riservata per llama.cpp background agent
- **Porta 11434**: Usata da Ollama main (per chat)
- **Modello**: Phi-3-mini Q4 è ottimizzato per velocità e qualità
- **Alternative**: Puoi usare altri modelli quantizzati GGUF compatibili con llama.cpp
