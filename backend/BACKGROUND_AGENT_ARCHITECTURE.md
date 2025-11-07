# Architettura Background Agent - Opzioni di Implementazione

## Situazione Attuale

- **Modello principale**: `gpt-oss:20b` (modello grande, ~40GB RAM)
- **Ollama**: Esegue su host (localhost:11434)
- **Uso**: Tutte le chiamate LLM (chat, estrazione conoscenza, riassunti) usano lo stesso modello
- **Problema**: Background tasks occupano il modello principale, rallentando le risposte chat

## Obiettivo

Separare i task in background dal modello principale per:
- ✅ Non bloccare le risposte chat
- ✅ Usare un modello più efficiente per task semplici (contraddizioni, analisi)
- ✅ Scalabilità: background tasks possono essere più lenti senza impatto UX

---

## Opzione 1: Container Ollama Separato con Modello Piccolo ⭐ (Raccomandato)

### Architettura

```
┌─────────────────────────────────────────┐
│  Backend FastAPI (Host)                 │
│  ┌───────────────────────────────────┐  │
│  │  OllamaClient (Main)              │  │
│  │  → ollama-main:11434              │  │
│  │  → Modello: gpt-oss:20b           │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │  BackgroundAgent                   │  │
│  │  → OllamaClient (Background)       │  │
│  │  → ollama-background:11435         │  │
│  │  → Modello: phi-3-mini (3.8B)    │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
         │                    │
         │                    │
    ┌────▼────┐          ┌────▼────┐
    │ Ollama  │          │ Ollama  │
    │ Main    │          │ Background│
    │ :11434  │          │ :11435  │
    └─────────┘          └─────────┘
```

### Implementazione

#### 1. Docker Compose - Aggiungere Ollama Background

```yaml
# docker-compose.yml
services:
  # ... existing services (postgres, chromadb) ...
  
  ollama-background:
    image: ollama/ollama:latest
    container_name: knowledge-navigator-ollama-background
    ports:
      - "11435:11434"  # Porta diversa per non conflitto
    volumes:
      - ollama_background_data:/root/.ollama
    environment:
      - OLLAMA_HOST=0.0.0.0
    deploy:
      resources:
        limits:
          cpus: '2'  # Limita CPU per non impattare sistema
          memory: 8G  # Modello piccolo richiede meno RAM
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  # ... existing volumes ...
  ollama_background_data:
```

#### 2. Setup Modello Background

```bash
# Dopo avvio container, pull modello piccolo
docker exec knowledge-navigator-ollama-background ollama pull phi-3-mini
# Oppure: llama-3.2-3b, qwen2.5-1.5b, gemma-2-2b
```

#### 3. Configurazione Backend

```python
# app/core/config.py
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Ollama Main (per chat)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gpt-oss:20b"
    
    # Ollama Background (per task in background)
    ollama_background_base_url: str = "http://localhost:11435"
    ollama_background_model: str = "phi-3-mini"  # Modello piccolo ed efficiente
```

#### 4. OllamaClient Separato

```python
# app/core/ollama_client.py
class OllamaClient:
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = base_url or settings.ollama_base_url
        self.model = model or settings.ollama_model
        self.client = httpx.AsyncClient(timeout=120.0)
    # ... rest of implementation ...

# app/core/dependencies.py
def get_ollama_client() -> OllamaClient:
    """Ollama client per chat principale"""
    return OllamaClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model
    )

def get_ollama_background_client() -> OllamaClient:
    """Ollama client per task in background"""
    return OllamaClient(
        base_url=settings.ollama_background_base_url,
        model=settings.ollama_background_model
    )
```

#### 5. BackgroundAgent

```python
# app/services/background_agent.py
class BackgroundAgent:
    def __init__(self, memory_manager, db_session):
        self.memory_manager = memory_manager
        self.db = db_session
        # Usa Ollama background (modello piccolo)
        self.ollama = get_ollama_background_client()
        self.integrity_checker = SemanticIntegrityChecker(
            memory_manager, self.ollama
        )
```

### Vantaggi

✅ **Isolamento completo**: Modello background non interferisce con chat
✅ **Performance**: Modello piccolo (3-4B) è veloce per task semplici
✅ **Risorse**: Richiede solo 4-8GB RAM vs 40GB del modello principale
✅ **Scalabilità**: Può essere eseguito su macchina diversa se necessario
✅ **Semplicità**: Stessa API Ollama, solo porta/modello diversi

### Svantaggi

⚠️ **Setup iniziale**: Richiede pull del modello background
⚠️ **RAM aggiuntiva**: ~8GB per modello piccolo (ma molto meno del principale)

---

## Opzione 2: Queue System con Worker Separato

### Architettura

```
┌─────────────────────────────────────────┐
│  Backend FastAPI                        │
│  ┌───────────────────────────────────┐  │
│  │  OllamaClient (Main)             │  │
│  │  → gpt-oss:20b                   │  │
│  └───────────────────────────────────┘  │
│  ┌───────────────────────────────────┐  │
│  │  Task Queue (Redis)               │  │
│  │  → integrity_check                │  │
│  │  → event_check                    │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
         │
         │
    ┌────▼────────────────────────────┐
    │  Background Worker (Processo)   │
    │  ┌──────────────────────────┐   │
    │  │  OllamaClient            │   │
    │  │  → gpt-oss:20b           │   │
    │  │  (stesso modello,        │   │
    │  │   ma processo separato)   │   │
    │  └──────────────────────────┘   │
    │  Consuma task da Redis           │
    └──────────────────────────────────┘
```

### Implementazione

#### 1. Redis in Docker Compose

```yaml
services:
  redis:
    image: redis:7-alpine
    container_name: knowledge-navigator-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
```

#### 2. Worker Process Separato

```python
# backend/worker.py
import asyncio
import redis.asyncio as redis
from app.services.background_agent import BackgroundAgent
# ...

async def worker():
    r = redis.from_url("redis://localhost:6379")
    agent = BackgroundAgent(...)
    
    while True:
        # Consuma task da queue
        task = await r.blpop("background_tasks", timeout=1)
        if task:
            await agent.process_task(task)
```

#### 3. Backend Invia Task

```python
# In ConversationLearner
async def index_extracted_knowledge(...):
    # Index knowledge
    for item in knowledge_items:
        await memory_manager.add_long_term_memory(...)
    
    # Invia task a queue (non blocca)
    await redis_client.lpush("background_tasks", json.dumps({
        "type": "integrity_check",
        "knowledge_item": item
    }))
```

### Vantaggi

✅ **Decoupling**: Backend e worker completamente separati
✅ **Scalabilità**: Puoi avere N worker su macchine diverse
✅ **Resilienza**: Worker può crashare senza impattare backend
✅ **Priorità**: Puoi avere queue con priorità diverse

### Svantaggi

⚠️ **Complessità**: Richiede Redis, worker process, gestione errori
⚠️ **Overhead**: Serializzazione/deserializzazione task
⚠️ **Stesso modello**: Worker usa stesso modello grande (non risolve problema risorse)

---

## Opzione 3: Ollama Multi-Model (Stesso Container)

### Architettura

```
┌─────────────────────────────────────────┐
│  Ollama Container (localhost:11434)    │
│  ┌───────────────────────────────────┐ │
│  │  Modelli disponibili:             │ │
│  │  - gpt-oss:20b (main)             │ │
│  │  - phi-3-mini (background)        │ │
│  └───────────────────────────────────┘ │
└─────────────────────────────────────────┘
         │                    │
    ┌────▼────┐          ┌────▼────┐
    │ Backend │          │Background│
    │ (main)  │          │ Agent   │
    └─────────┘          └─────────┘
```

### Implementazione

```python
# Stesso Ollama, modelli diversi
class OllamaClient:
    def __init__(self, model: str):
        self.base_url = settings.ollama_base_url
        self.model = model  # Passato come parametro
        # ...

# Usage
main_ollama = OllamaClient("gpt-oss:20b")
background_ollama = OllamaClient("phi-3-mini")
```

### Vantaggi

✅ **Semplicità**: Un solo container Ollama
✅ **Condivisione**: Modelli nella stessa istanza

### Svantaggi

⚠️ **Risorse condivise**: Modelli competono per RAM/CPU
⚠️ **Bloccante**: Se background task usa modello grande, blocca chat
⚠️ **Non isolato**: Un problema può impattare entrambi

---

## Raccomandazione: Opzione 1 ⭐

**Perché Opzione 1 è la migliore:**

1. **Isolamento completo**: Modello background non può interferire con chat
2. **Performance**: Modello piccolo (3-4B) è perfetto per task semplici:
   - Analisi contraddizioni (sì/no, quale corretta)
   - Estrazione entità (date, numeri)
   - Non serve capacità di ragionamento complesso
3. **Risorse**: 8GB RAM vs 40GB, CPU limitata
4. **Semplicità**: Stessa API, solo configurazione diversa
5. **Scalabilità futura**: Può essere spostato su macchina dedicata

### Modelli Candidati per Background

| Modello | Dimensione | RAM | Velocità | Qualità |
|---------|-----------|-----|----------|---------|
| **phi-3-mini** | 3.8B | ~4GB | ⚡⚡⚡ | ✅ Buona |
| **llama-3.2-3b** | 3B | ~4GB | ⚡⚡⚡ | ✅✅ Eccellente |
| **qwen2.5-1.5b** | 1.5B | ~2GB | ⚡⚡⚡⚡ | ✅ Buona |
| **gemma-2-2b** | 2B | ~3GB | ⚡⚡⚡ | ✅ Buona |

**Raccomandazione**: `phi-3-mini` o `llama-3.2-3b` per equilibrio qualità/velocità.

---

## Implementazione Step-by-Step (Opzione 1)

### Step 1: Aggiornare docker-compose.yml
### Step 2: Pull modello background
### Step 3: Aggiornare config.py
### Step 4: Creare OllamaClient separato
### Step 5: Aggiornare BackgroundAgent
### Step 6: Test isolamento

---

## Considerazioni Future

- **Auto-scaling**: Se necessario, background agent può essere su macchina separata
- **Monitoring**: Monitorare utilizzo CPU/RAM di entrambi i container
- **Fallback**: Se background Ollama è down, usare main (con warning)
- **Cache**: Condividere cache embeddings tra i due (già in ChromaDB)

---

## Domande da Risolvere

1. **Modello background**: Quale preferisci? (phi-3-mini, llama-3.2-3b, altro?)
2. **Porta**: 11435 va bene o preferisci altra?
3. **Risorse**: Limiti CPU/RAM per container background?
4. **Fallback**: Cosa fare se background Ollama è down? (usare main con warning?)

