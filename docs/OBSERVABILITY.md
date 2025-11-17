# Observability System - Tracing & Metrics

## 📋 Panoramica

Il sistema di observability fornisce tracing distribuito e metriche per monitorare le performance e il comportamento dell'applicazione Knowledge Navigator. Questo sistema è essenziale per:

- **Debugging**: Tracciare il flusso delle richieste attraverso il sistema
- **Performance Monitoring**: Identificare colli di bottiglia e ottimizzare
- **Error Tracking**: Monitorare errori e eccezioni
- **Business Metrics**: Tracciare metriche di business (tool usage, session duration, etc.)

## 🏗️ Architettura

### Componenti Principali

1. **Tracing Module** (`app/core/tracing.py`)
   - Fornisce tracing distribuito usando OpenTelemetry (con fallback semplice)
   - Traccia richieste HTTP, esecuzione tools, chiamate LLM
   - Genera trace IDs per correlare eventi

2. **Metrics Module** (`app/core/metrics.py`)
   - Fornisce metriche usando Prometheus (con fallback semplice)
   - Counters, Histograms, Gauges, Summaries
   - Endpoint `/metrics` per scraping Prometheus

3. **Observability Middleware** (`app/main.py`)
   - Middleware FastAPI per tracciare automaticamente tutte le richieste HTTP
   - Aggiunge trace IDs alle response headers
   - Registra metriche per ogni richiesta

## 🔧 Utilizzo

### Tracing

#### Tracciare una funzione

```python
from app.core.tracing import trace_span, set_trace_attribute, add_trace_event

async def my_function():
    with trace_span("my.operation", {"component": "api"}):
        set_trace_attribute("user_id", "123")
        add_trace_event("operation.started")
        
        # Your code here
        result = await do_something()
        
        add_trace_event("operation.completed", {"result": "success"})
        return result
```

#### Decorator per tracing automatico

```python
from app.core.tracing import trace_function

@trace_function("my_function", {"component": "api"})
async def my_function():
    # Automatically traced
    pass
```

### Metrics

#### Counters (eventi incrementali)

```python
from app.core.metrics import increment_counter

# Incrementa un counter
increment_counter("api_requests_total", labels={"endpoint": "/api/sessions"})

# Con valore personalizzato
increment_counter("items_processed", value=10, labels={"type": "email"})
```

#### Histograms (distribuzione di valori)

```python
from app.core.metrics import observe_histogram

# Registra durata di un'operazione
start_time = time.time()
result = await do_operation()
duration = time.time() - start_time

observe_histogram("operation_duration_seconds", duration, labels={"operation": "search"})
```

#### Gauges (valori istantanei)

```python
from app.core.metrics import set_gauge

# Imposta un valore corrente
set_gauge("active_sessions", count, labels={"tenant": "tenant1"})
```

#### Decorator per misurare durata

```python
from app.core.metrics import time_function

@time_function("api_request_duration", {"endpoint": "/api/sessions"})
async def handle_request():
    # Durata misurata automaticamente
    pass
```

## 📊 Metriche Disponibili

### HTTP Metrics

- `http_requests_total`: Contatore totale richieste HTTP
  - Labels: `method`, `path`, `status`
- `http_request_duration_seconds`: Durata richieste HTTP
  - Labels: `method`, `path`, `status`
- `http_requests_errors_total`: Contatore errori HTTP
  - Labels: `method`, `path`, `error_type`

### Tool Metrics

- `tool_executions_total`: Contatore esecuzioni tools
  - Labels: `tool`
- `tool_execution_duration_seconds`: Durata esecuzione tools
  - Labels: `tool`, `type`, `error`
- `tool_executions_errors_total`: Contatore errori tools
  - Labels: `tool`, `error_type`

### LLM Metrics

- `llm_requests_total`: Contatore richieste LLM
  - Labels: `model`, `stream`
- `llm_request_duration_seconds`: Durata richieste LLM
  - Labels: `model`, `stream`, `error`
- `llm_requests_errors_total`: Contatore errori LLM
  - Labels: `model`, `error_type`

## 🔍 Tracing

### Trace Spans

Ogni operazione importante crea un trace span con:

- **Nome**: Identifica l'operazione (es: `tool.execute.get_calendar_events`)
- **Attributes**: Metadati (es: `tool.name`, `llm.model`)
- **Events**: Eventi durante l'esecuzione (es: `tool.execution.started`)
- **Duration**: Durata dell'operazione

### Trace IDs

Ogni richiesta HTTP riceve un trace ID univoco nell'header `X-Trace-ID`. Questo permette di:

- Correlare log e metriche
- Tracciare una richiesta attraverso il sistema
- Debugging end-to-end

### Esempio Trace

```
GET /api/sessions
  ├─ tool.execute.get_calendar_events
  │   └─ calendar_service.query (200ms)
  ├─ llm.generate
  │   └─ ollama_client.post (1.2s)
  └─ memory_manager.store (50ms)
```

## 📡 Endpoint Metrics

### GET /metrics

Endpoint Prometheus per scraping metriche.

**Response**: Formato Prometheus text/plain

**Esempio**:
```bash
curl http://localhost:8000/metrics
```

**Output**:
```
# TYPE http_requests_total counter
http_requests_total{method="GET",path="/api/sessions",status="200"} 42

# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{method="GET",path="/api/sessions",status="200",le="0.1"} 35
http_request_duration_seconds_sum{method="GET",path="/api/sessions",status="200"} 2.5
http_request_duration_seconds_count{method="GET",path="/api/sessions",status="200"} 42
```

## 🛠️ Configurazione

### OpenTelemetry (Opzionale)

Per usare OpenTelemetry completo invece del fallback:

```bash
pip install opentelemetry-api opentelemetry-sdk
pip install opentelemetry-instrumentation-fastapi
pip install opentelemetry-instrumentation-sqlalchemy
pip install opentelemetry-instrumentation-httpx
```

Il sistema rileverà automaticamente OpenTelemetry se disponibile.

### Prometheus (Opzionale)

Per usare Prometheus completo invece del fallback:

```bash
pip install prometheus-client
```

Il sistema rileverà automaticamente Prometheus se disponibile.

### Fallback Mode

Se OpenTelemetry o Prometheus non sono disponibili, il sistema usa implementazioni semplici che:

- Tracciano in memoria (tracing)
- Accumulano metriche in memoria (metrics)
- Funzionano senza dipendenze esterne

## 🧪 Testing

Eseguire i test:

```bash
cd backend
pytest tests/test_observability.py -v
```

## 📈 Integrazione con Monitoring Tools

### Prometheus + Grafana

1. Configurare Prometheus per scraping `/metrics`
2. Creare dashboard Grafana con le metriche
3. Configurare alerting per soglie critiche

### Jaeger / Zipkin (per Tracing)

1. Configurare exporter OpenTelemetry per Jaeger/Zipkin
2. Visualizzare trace in UI
3. Analizzare performance e latenza

### Log Correlation

Usare trace IDs nei log per correlare eventi:

```python
from app.core.tracing import get_trace_id

trace_id = get_trace_id()
logger.info(f"[{trace_id}] Processing request")
```

## 🔒 Best Practices

1. **Non tracciare dati sensibili**: Evitare di includere password, token, PII negli span attributes
2. **Usare labels appropriati**: Labels aiutano a filtrare e aggregare metriche
3. **Non abusare di tracing**: Tracciare solo operazioni significative
4. **Monitorare overhead**: Tracing e metrics hanno un costo in performance
5. **Usare sampling in produzione**: Campionare trace per ridurre overhead

## 🌐 Frontend Integration

### Trace ID Correlation

Il frontend genera trace IDs univoci e li invia al backend nell'header `X-Trace-ID`. Questo permette di:

- Correlare richieste frontend-backend
- Tracciare una richiesta end-to-end
- Debugging completo del flusso utente

### Componenti Frontend

1. **`lib/tracing.ts`**: Modulo tracing frontend
   - Generazione trace IDs
   - Logging con trace IDs
   - Performance tracking

2. **`lib/api.ts`**: Interceptor Axios
   - Aggiunge `X-Trace-ID` header a tutte le richieste
   - Traccia durata richieste
   - Logging richieste/risposte

3. **`components/ErrorBoundary.tsx`**: Error boundary React
   - Cattura errori rendering
   - Include trace ID negli errori

4. **`components/PerformanceMonitor.tsx`**: Performance monitoring
   - Traccia page load time
   - Inizializza trace ID per pagina
   - Setup global error handlers

### Utilizzo Frontend

```typescript
import { trackUserInteraction, PerformanceTracker } from '@/lib/tracing'

// Track user interaction
trackUserInteraction('button_click', 'SessionList', { sessionId: '123' })

// Measure performance
const tracker = new PerformanceTracker('data_fetch')
await fetchData()
tracker.end() // Logs duration
```

### Trace ID Flow

```
Frontend                    Backend
   |                           |
   |-- X-Trace-ID: abc123 ---->|
   |                           |-- Creates span with frontend.trace_id
   |                           |-- Executes request
   |                           |-- Returns X-Trace-ID in response
   |<-- X-Trace-ID: xyz789 ----|
   |                           |
```

## 📚 Riferimenti

- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [FastAPI Middleware](https://fastapi.tiangolo.com/advanced/middleware/)

## 🐛 Troubleshooting

### Metriche non visibili

1. Verificare che `/metrics` endpoint risponda
2. Controllare che Prometheus stia facendo scraping
3. Verificare logs per errori di inizializzazione

### Trace non funzionanti

1. Verificare che tracing sia inizializzato in `main.py`
2. Controllare che OpenTelemetry sia installato (se usato)
3. Verificare logs per errori di tracing

### Performance Issues

1. Ridurre frequenza di tracing/metrics
2. Usare sampling per trace
3. Ottimizzare labels e attributes

