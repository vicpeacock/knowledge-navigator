# Script di Servizio

Tutti gli script di servizio sono organizzati nella directory `scripts/`.

## Script Disponibili

Tutti gli script sono nella directory `scripts/`:

- **`start.sh`** - Avvia tutti i servizi (backend, frontend, Docker, Ollama, llama.cpp)
- **`stop.sh`** - Ferma tutti i servizi
- **`restart_backend.sh`** - Riavvia solo il backend (utile dopo modifiche configurazione)
- **`start-mcp-gateway.sh`** - Wrapper per avviare il Docker MCP Gateway
- **`stop-mcp-gateway.sh`** - Wrapper per fermare il Docker MCP Gateway
- **`cleanup-playwright-containers.sh`** - Wrapper per pulire container Docker orfani
- **`start_llama_background.sh`** - Avvia llama.cpp in background
- **`start_llama_background_monitored.sh`** - Avvia llama.cpp con monitoraggio
- **`monitor_llama_background.sh`** - Monitora llama.cpp

## Utilizzo

```bash
# Dalla root del progetto
./scripts/start.sh              # Avvia tutto
./scripts/stop.sh               # Ferma tutto
./scripts/restart_backend.sh    # Riavvia solo il backend

# Oppure direttamente da scripts/
cd scripts
./start.sh
./restart_backend.sh
```

## Struttura

```
scripts/
├── start.sh                    # Avvia tutti i servizi
├── stop.sh                     # Ferma tutti i servizi
├── restart_backend.sh          # Riavvia solo il backend
├── start-mcp-gateway.sh        # Wrapper per MCP Gateway
├── stop-mcp-gateway.sh         # Wrapper per MCP Gateway
├── cleanup-playwright-containers.sh  # Wrapper per pulizia container
├── start_llama_background.sh   # Avvia llama.cpp
├── start_llama_background_monitored.sh
└── monitor_llama_background.sh
```

## Note

- Tutti gli script sono nella directory `scripts/` e devono essere chiamati con `./scripts/script_name.sh`
- Tutti gli script usano `PROJECT_ROOT` per trovare la directory del progetto
- Gli script gestiscono automaticamente la terminazione di processi esistenti sulle porte utilizzate
- Gli script wrapper (MCP Gateway, cleanup) chiamano gli script completi in `tools/infra/`

