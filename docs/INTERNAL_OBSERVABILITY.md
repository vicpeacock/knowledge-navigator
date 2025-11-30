# Sistema Observability - Knowledge Navigator

## Panoramica

Sistema di tracing distribuito e metriche per monitoraggio performance e comportamento.

---

## Componenti

### Tracing Module
- **Framework**: OpenTelemetry (con fallback semplice)
- **Traccia**: Richieste HTTP, tool execution, LLM calls
- **Trace IDs**: Per correlare eventi

### Metrics Module
- **Framework**: Prometheus (con fallback semplice)
- **Tipi**: Counters, Histograms, Gauges, Summaries
- **Endpoint**: `/metrics` per scraping

### Observability Middleware
- Middleware FastAPI per tracciare tutte le richieste
- Aggiunge trace IDs a response headers
- Registra metriche per ogni richiesta

---

## Utilizzo

### Tracing Functions
```python
with trace_span("operation", {"component": "api"}):
    set_trace_attribute("user_id", "123")
    add_trace_event("operation.started")
    # ... code ...
```

### Metrics
```python
increment_counter("api_requests_total", labels={"endpoint": "/api/sessions"})
observe_histogram("operation_duration_seconds", duration)
set_gauge("active_sessions", count)
```

---

## Riferimenti

- `backend/app/core/tracing.py` - Tracing implementation
- `backend/app/core/metrics.py` - Metrics implementation
- `docs/OBSERVABILITY.md` - Documentazione completa
