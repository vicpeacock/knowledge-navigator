# Testing Observability - Guida Completa

## 📍 Dove si trovano le metriche

### 1. Endpoint Backend (Prometheus Format)
**URL**: `http://localhost:8000/metrics`

**Formato**: Prometheus text format

**Esempio**:
```bash
curl http://localhost:8000/metrics
```

**Output**:
```
# TYPE http_requests_total counter
http_requests_total{method="GET",path="/api/sessions",status="200"} 42.0

# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{method="GET",path="/api/sessions",status="200",le="0.1"} 35
http_request_duration_seconds_sum{method="GET",path="/api/sessions",status="200"} 2.5
http_request_duration_seconds_count{method="GET",path="/api/sessions",status="200"} 42
```

### 2. Dashboard Frontend (Admin Only)
**URL**: `http://localhost:3003/admin/metrics`

**Accesso**: Solo per utenti admin

**Features**:
- Visualizzazione metriche in formato tabellare
- Raggruppamento per tipo di metrica
- Statistiche summary (total metrics, metric types, HTTP requests)
- Download metriche in formato raw
- Refresh manuale

**Come accedere**:
1. Login come admin (`admin@example.com`)
2. Cliccare su "Metrics" nella navbar (accanto a "Admin")
3. Oppure navigare direttamente a `/admin/metrics`

### 3. Console Browser (Development)
**Dove**: Console del browser (F12)

**Cosa vedere**:
- Trace IDs nelle richieste API
- Log di performance (page load, API calls)
- Errori con trace ID correlati

**Esempio log**:
```
[Trace: frontend-abc123] API Request: GET /api/sessions
[Trace: frontend-abc123] API Response: GET /api/sessions - 200 (45ms)
[Trace: frontend-abc123] Backend Trace ID: xyz789
```

## 🧪 Test End-to-End

### Test 1: Verificare Metriche HTTP

1. **Aprire browser**: `http://localhost:3003`
2. **Login come admin**: `admin@example.com` / `admin123`
3. **Navigare a una sessione**: Cliccare su una sessione esistente
4. **Verificare metriche**:
   - Aprire `/admin/metrics`
   - Verificare che `http_requests_total` sia incrementato
   - Verificare che `http_request_duration_seconds` mostri la durata

### Test 2: Verificare Trace IDs

1. **Aprire Console Browser** (F12)
2. **Filtrare log per "Trace"**
3. **Eseguire un'azione** (es: inviare un messaggio)
4. **Verificare**:
   - Trace ID presente nei log
   - Trace ID inviato al backend (header `X-Trace-ID`)
   - Trace ID ricevuto dal backend (header `X-Trace-ID`)

### Test 3: Verificare Tool Execution Metrics

1. **Inviare un messaggio che usa un tool** (es: "Cosa ho in calendario oggi?")
2. **Verificare metriche**:
   - `tool_executions_total` incrementato
   - `tool_execution_duration_seconds` mostra durata
   - Tipo di tool tracciato (calendar, email, web, mcp)

### Test 4: Verificare LLM Metrics

1. **Inviare un messaggio normale**
2. **Verificare metriche**:
   - `llm_requests_total` incrementato
   - `llm_request_duration_seconds` mostra durata
   - Model tracciato (es: `llama3.2`)

### Test 5: Verificare Error Tracking

1. **Causare un errore** (es: richiesta a endpoint inesistente)
2. **Verificare**:
   - `http_requests_errors_total` incrementato
   - Trace ID presente nell'errore
   - Error type tracciato

### Test 6: Verificare Performance Monitoring

1. **Aprire Console Browser**
2. **Navigare tra pagine**
3. **Verificare log**:
   - Page load time tracciato
   - Trace ID per ogni pagina

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

## 🔍 Come Verificare Trace IDs

### Nel Browser
1. Aprire DevTools (F12)
2. Andare su Network tab
3. Selezionare una richiesta
4. Verificare Headers:
   - **Request Headers**: `X-Trace-ID: frontend-abc123`
   - **Response Headers**: `X-Trace-ID: xyz789` (backend trace ID)

### Nel Backend Logs
```bash
tail -f backend/backend.log | grep "Trace"
```

Dovresti vedere:
```
Frontend trace ID received: frontend-abc123
```

## 🎯 Checklist Test Completo

- [ ] Endpoint `/metrics` risponde correttamente
- [ ] Dashboard `/admin/metrics` accessibile (solo admin)
- [ ] Metriche HTTP vengono registrate
- [ ] Trace IDs vengono generati nel frontend
- [ ] Trace IDs vengono inviati al backend
- [ ] Trace IDs vengono ricevuti dal backend
- [ ] Tool execution viene tracciato
- [ ] LLM requests vengono tracciate
- [ ] Errori vengono tracciati con trace ID
- [ ] Performance monitoring funziona
- [ ] Console browser mostra log con trace IDs

## 🐛 Troubleshooting

### Metriche non visibili
1. Verificare che backend sia in esecuzione: `curl http://localhost:8000/health`
2. Verificare endpoint metrics: `curl http://localhost:8000/metrics`
3. Controllare logs backend per errori

### Trace IDs non presenti
1. Verificare console browser (F12)
2. Verificare che `sessionStorage` sia disponibile
3. Controllare Network tab per header `X-Trace-ID`

### Dashboard non accessibile
1. Verificare di essere loggati come admin
2. Verificare che frontend sia in esecuzione
3. Controllare console browser per errori

## 📝 Note

- Le metriche sono in formato Prometheus e possono essere scrape da Prometheus
- I trace IDs sono generati lato frontend e correlati con backend
- Il logging dettagliato è disponibile solo in development mode
- In produzione, considerare sampling per ridurre overhead

