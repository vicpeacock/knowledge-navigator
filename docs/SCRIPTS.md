# Script di Servizio

Tutti gli script di servizio sono organizzati nella directory `scripts/`.

## Script Disponibili

### Script Principali (link simbolici nella root)

- **`start.sh`** → `scripts/start.sh` - Avvia tutti i servizi (backend, frontend, Docker, Ollama, llama.cpp)
- **`stop.sh`** → `scripts/stop.sh` - Ferma tutti i servizi

### Script in `scripts/`

- **`start.sh`** - Script completo per avviare tutti i servizi
- **`stop.sh`** - Script completo per fermare tutti i servizi
- **`restart_backend.sh`** - Riavvia solo il backend (utile dopo modifiche configurazione)
- **`start-mcp-gateway.sh`** - Avvia il Docker MCP Gateway
- **`stop-mcp-gateway.sh`** - Ferma il Docker MCP Gateway
- **`cleanup-playwright-containers.sh`** - Pulisce container Docker orfani di Playwright
- **`start_llama_background.sh`** - Avvia llama.cpp in background
- **`start_llama_background_monitored.sh`** - Avvia llama.cpp con monitoraggio
- **`monitor_llama_background.sh`** - Monitora llama.cpp

## Utilizzo

```bash
# Dalla root del progetto
./start.sh              # Avvia tutto
./stop.sh               # Ferma tutto

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
├── start-mcp-gateway.sh        # Avvia MCP Gateway
├── stop-mcp-gateway.sh         # Ferma MCP Gateway
├── cleanup-playwright-containers.sh  # Pulisce container orfani
├── start_llama_background.sh   # Avvia llama.cpp
├── start_llama_background_monitored.sh
└── monitor_llama_background.sh
```

## Note

- Gli script nella root (`start.sh`, `stop.sh`) sono link simbolici che puntano a `scripts/`
- Tutti gli script usano `PROJECT_ROOT` per trovare la directory del progetto
- Gli script gestiscono automaticamente la terminazione di processi esistenti sulle porte utilizzate

