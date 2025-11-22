# Analisi Stabilità Backend - Perché si ferma spesso

## 🔍 Possibili Cause Identificate

### 1. Operazioni Bloccanti nell'Event Loop

#### Problema: Operazioni sincrone che bloccano l'event loop
- **ChromaDB queries**: Anche se abbiamo aggiunto `run_in_executor`, alcune chiamate potrebbero ancora bloccare
- **Embedding generation**: Operazioni CPU-intensive che possono bloccare
- **Database queries lunghe**: Query PostgreSQL complesse senza timeout

#### File coinvolti:
- `backend/app/core/memory_manager.py` - ChromaDB queries
- `backend/app/core/embedding_service.py` - Generazione embedding
- `backend/app/api/sessions.py` - Query database complesse

### 2. Timeout Mancanti o Troppo Lunghi

#### Problema: Operazioni senza timeout che possono bloccarsi indefinitamente
- **MCP Client**: Chiamate a tool esterni senza timeout
- **Ollama**: Chiamate LLM senza timeout appropriato
- **Database**: Query senza timeout

#### File coinvolti:
- `backend/app/core/mcp_client.py` - Chiamate MCP
- `backend/app/core/ollama_client.py` - Chiamate LLM
- `backend/app/api/metrics.py` - Evaluation senza timeout

### 3. Gestione Errori Insufficiente

#### Problema: Eccezioni non gestite che causano crash
- **Evaluation endpoint**: Può fallire senza gestione adeguata
- **LangGraph**: Errori nei nodi possono causare crash
- **Database**: Errori di connessione non gestiti

#### File coinvolti:
- `backend/app/api/metrics.py` - Evaluation endpoint
- `backend/app/agents/langgraph_app.py` - Nodi del grafo
- `backend/app/db/database.py` - Gestione connessioni

### 4. Memory Leaks o Accumulo di Risorse

#### Problema: Risorse non rilasciate correttamente
- **Agent Activity Stream**: Subscribers non rimossi correttamente
- **Database connections**: Connessioni non chiuse
- **MCP sessions**: Sessioni non chiuse correttamente

#### File coinvolti:
- `backend/app/services/agent_activity_stream.py` - Subscribers
- `backend/app/core/mcp_client.py` - Sessioni MCP
- `backend/app/db/database.py` - Pool connessioni

### 5. Operazioni Evaluation Troppo Lunghe

#### Problema: Evaluation può richiedere molto tempo e bloccare il backend
- **Test cases sequenziali**: Ogni test case può richiedere 30-60 secondi
- **Nessun timeout**: L'endpoint può rimanere bloccato per minuti
- **Nessuna cancellazione**: Non è possibile cancellare un'evaluation in corso

#### File coinvolti:
- `backend/app/api/metrics.py` - Endpoint evaluation
- `backend/app/core/evaluation.py` - Esecuzione test cases

## 🛠️ Soluzioni Proposte

### 1. Aggiungere Timeout a Tutte le Operazioni Lunghe

```python
# Esempio: Aggiungere timeout a evaluation
import asyncio

report = await asyncio.wait_for(
    evaluator.evaluate_test_suite(test_cases=test_cases, parallel=parallel),
    timeout=600.0  # 10 minuti max
)
```

### 2. Eseguire Evaluation in Background Task

```python
# Invece di eseguire direttamente, mettere in background
from fastapi import BackgroundTasks

@router.post("/api/v1/evaluation/generate")
async def generate_evaluation_report(
    background_tasks: BackgroundTasks,
    ...
):
    # Salva il report in un file o database
    # Restituisci immediatamente con un job ID
    # Esegui evaluation in background
```

### 3. Aggiungere Health Check e Monitoring

```python
# Monitorare lo stato del backend
@router.get("/health/detailed")
async def detailed_health():
    return {
        "status": "healthy",
        "active_requests": count_active_requests(),
        "memory_usage": get_memory_usage(),
        "database_connections": get_db_pool_size(),
    }
```

### 4. Migliorare Gestione Errori

```python
# Wrapper per gestire errori in modo sicuro
async def safe_execute(coro, default_return=None):
    try:
        return await coro
    except Exception as e:
        logger.error(f"Error in {coro}: {e}", exc_info=True)
        return default_return
```

### 5. Limitare Operazioni Concurrenti

```python
# Usare semaforo per limitare operazioni concurrenti
import asyncio

EVALUATION_SEMAPHORE = asyncio.Semaphore(1)  # Solo 1 evaluation alla volta

async def generate_evaluation_report(...):
    async with EVALUATION_SEMAPHORE:
        # Esegui evaluation
        ...
```

## 📊 Monitoraggio Consigliato

1. **Log Analysis**: Analizzare i log per pattern di crash
2. **Memory Monitoring**: Monitorare uso memoria
3. **Request Tracking**: Tracciare richieste lunghe
4. **Error Tracking**: Tracciare errori frequenti

## 🔧 Fix Immediati Implementati

1. ✅ **Timeout a evaluation endpoint** - Aggiunto timeout di 10 minuti per evitare blocchi
2. ✅ **Limitare numero di test cases** - Già implementato con `max_tests` parameter
3. ✅ **Semaforo per evaluation concurrenti** - Solo 1 evaluation alla volta per evitare sovraccarico
4. ✅ **Migliorare gestione errori** - Aggiunta gestione errori più dettagliata con logging
5. ✅ **Configurazione pool database** - Aggiunte configurazioni per evitare esaurimento connessioni

## 📝 Modifiche Implementate

### 1. Timeout e Semaforo per Evaluation (`backend/app/api/metrics.py`)
- Aggiunto timeout di 10 minuti con `asyncio.wait_for`
- Aggiunto semaforo (`asyncio.Semaphore(1)`) per limitare a 1 evaluation alla volta
- Migliorata gestione errori con logging dettagliato

### 2. Configurazione Pool Database (`backend/app/db/database.py`)
- `pool_size=10`: Mantiene 10 connessioni nel pool
- `max_overflow=20`: Permette fino a 20 connessioni aggiuntive
- `pool_timeout=30`: Timeout di 30 secondi per ottenere una connessione
- `pool_recycle=3600`: Ricicla connessioni dopo 1 ora
- `pool_pre_ping=True`: Verifica che le connessioni siano valide prima di usarle

## 🔍 Come Monitorare il Problema

### 1. Controllare i Log
```bash
# Cercare errori di timeout
tail -f backend/backend.log | grep -i "timeout\|error\|exception"

# Cercare problemi di connessione database
tail -f backend/backend.log | grep -i "pool\|connection\|database"
```

### 2. Verificare Processi
```bash
# Verificare se il backend è in esecuzione
ps aux | grep uvicorn

# Verificare connessioni database
psql -U postgres -c "SELECT count(*) FROM pg_stat_activity WHERE datname='knowledge_navigator';"
```

### 3. Monitorare Risorse
```bash
# Monitorare uso memoria
top -p $(pgrep -f uvicorn)

# Monitorare connessioni di rete
netstat -an | grep :8000
```

## 🚨 Segnali di Problema

1. **Backend non risponde**: Nessuna risposta a `/health` endpoint
2. **Timeout frequenti**: Errori 504 Gateway Timeout
3. **Connessioni database esaurite**: Errori "too many connections"
4. **Memory leak**: Uso memoria che cresce nel tempo
5. **Evaluation bloccate**: Multiple evaluation simultanee che bloccano il backend

## 🔄 Prossimi Passi Consigliati

1. **Implementare Background Tasks** per evaluation lunghe
2. **Aggiungere Monitoring** con Prometheus metrics per connessioni database
3. **Implementare Circuit Breaker** per chiamate esterne (MCP, Ollama)
4. **Aggiungere Health Checks** più dettagliati
5. **Implementare Graceful Shutdown** per chiudere connessioni correttamente

