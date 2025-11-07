# Setup Background Agent - Ollama Background

## Overview

Il Background Agent usa un container Ollama separato con un modello piccolo (`phi-3-mini`) per eseguire task in background senza occupare il modello principale.

## Setup Step-by-Step

### 1. Avviare i Container Docker

```bash
# Avvia tutti i servizi (postgres, chromadb, ollama-background)
docker-compose up -d

# Verifica che tutti i container siano in esecuzione
docker-compose ps
```

Dovresti vedere:
- `knowledge-navigator-postgres` (porta 5432)
- `knowledge-navigator-chromadb` (porta 8001)
- `knowledge-navigator-ollama-background` (porta 11435)

### 2. Pull del Modello phi-3-mini

Dopo che il container `ollama-background` è avviato, devi pullare il modello:

```bash
# Pull del modello phi-3-mini nel container background
docker exec knowledge-navigator-ollama-background ollama pull phi-3-mini
```

Questo può richiedere alcuni minuti (il modello è ~2.3GB).

### 3. Verificare che il Modello sia Disponibile

```bash
# Verifica che il modello sia stato pullato correttamente
docker exec knowledge-navigator-ollama-background ollama list
```

Dovresti vedere `phi-3-mini` nella lista.

### 4. Avviare il Backend

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

All'avvio, il backend eseguirà automaticamente un health check di tutti i servizi:
- ✅ PostgreSQL
- ✅ ChromaDB
- ✅ Ollama Main (localhost:11434)
- ✅ Ollama Background (localhost:11435)

### 5. Verificare Health Check

Puoi verificare lo stato di tutti i servizi chiamando l'endpoint:

```bash
curl http://localhost:8000/health
```

Risposta esempio:
```json
{
  "all_healthy": true,
  "services": {
    "postgres": {
      "healthy": true,
      "message": "PostgreSQL connection successful"
    },
    "chromadb": {
      "healthy": true,
      "message": "ChromaDB connection successful"
    },
    "ollama_main": {
      "healthy": true,
      "message": "Ollama main connection successful, model 'gpt-oss:20b' available"
    },
    "ollama_background": {
      "healthy": true,
      "message": "Ollama background connection successful, model 'phi-3-mini' available"
    }
  }
}
```

## Troubleshooting

### Ollama Background non risponde

Se vedi un errore come:
```json
{
  "ollama_background": {
    "healthy": false,
    "error": "Cannot connect to Ollama background (connection refused)"
  }
}
```

**Soluzione:**
1. Verifica che il container sia in esecuzione:
   ```bash
   docker ps | grep ollama-background
   ```
2. Se non è in esecuzione, avvialo:
   ```bash
   docker-compose up -d ollama-background
   ```
3. Attendi qualche secondo e riprova

### Modello phi-3-mini non trovato

Se vedi un errore come:
```json
{
  "ollama_background": {
    "healthy": false,
    "error": "Model 'phi-3-mini' not found. Available: []"
  }
}
```

**Soluzione:**
1. Pulla il modello:
   ```bash
   docker exec knowledge-navigator-ollama-background ollama pull phi-3-mini
   ```
2. Verifica che sia stato pullato:
   ```bash
   docker exec knowledge-navigator-ollama-background ollama list
   ```

### Container Ollama Background si ferma

Se il container si ferma frequentemente, controlla i log:

```bash
docker logs knowledge-navigator-ollama-background
```

Possibili cause:
- Memoria insufficiente (il container ha limite di 8GB)
- CPU insufficiente (il container ha limite di 2 CPU)

Puoi aumentare i limiti in `docker-compose.yml` se necessario.

## Configurazione

### Modificare il Modello Background

Se vuoi usare un modello diverso da `phi-3-mini`, modifica `backend/app/core/config.py`:

```python
ollama_background_model: str = "llama-3.2-3b"  # o altro modello
```

Poi pulla il nuovo modello:
```bash
docker exec knowledge-navigator-ollama-background ollama pull llama-3.2-3b
```

### Modificare la Porta

Se la porta 11435 è occupata, modifica `docker-compose.yml`:

```yaml
ports:
  - "11436:11434"  # Cambia 11435 in 11436
```

E aggiorna `backend/app/core/config.py`:

```python
ollama_background_base_url: str = "http://localhost:11436"
```

## Verifica Funzionamento

Dopo il setup, quando il backend avvia, dovresti vedere nei log:

```
🚀 Starting Knowledge Navigator backend...
🔍 Starting health check for all services...
✅ Health check completed. All services healthy: True
✅ All services are healthy. Backend ready!
```

Se qualche servizio non è healthy, vedrai:

```
⚠️  Some services are not healthy:
  - ollama_background: [errore specifico]
⚠️  Backend will start but some features may not work correctly.
```

Il backend partirà comunque, ma le funzionalità che richiedono Ollama background non funzioneranno.

## Note

- Il modello `phi-3-mini` è piccolo (~2.3GB) e veloce, perfetto per task semplici
- Il container background ha limiti di risorse (2 CPU, 8GB RAM) per non impattare il sistema
- Se Ollama background è down, il backend lo segnalerà nello status panel, ma continuerà a funzionare
- Il modello principale (gpt-oss:20b) rimane completamente isolato e non viene usato per background tasks

