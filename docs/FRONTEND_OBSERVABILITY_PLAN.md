# Piano Integrazione Observability Frontend

## 🎯 Obiettivi

1. **Correlazione Frontend-Backend**: Tracciare richieste end-to-end usando trace IDs
2. **Performance Monitoring**: Misurare tempi di risposta API e caricamento pagine
3. **Error Tracking**: Tracciare errori API e errori di rendering
4. **User Interactions**: Tracciare interazioni utente significative

## 📋 Implementazione Pianificata

### 1. Trace ID Management
- Generare trace ID univoco per ogni richiesta frontend
- Inviare trace ID nell'header `X-Trace-ID` nelle richieste API
- Ricevere trace ID dalle risposte backend (header `X-Trace-ID`)
- Loggare trace ID per debugging

### 2. API Request Tracing
- Intercettare tutte le chiamate API (Axios interceptor)
- Tracciare:
  - URL endpoint
  - Metodo HTTP
  - Durata richiesta
  - Status code
  - Errori
- Inviare trace ID al backend

### 3. Performance Metrics
- Misurare:
  - Tempo di caricamento pagine
  - Tempo di risposta API
  - Tempo di rendering componenti
- Inviare metriche al backend (opzionale) o loggare localmente

### 4. Error Tracking
- Catturare:
  - Errori API (4xx, 5xx)
  - Errori di rendering React
  - Network errors
- Includere trace ID negli errori per correlazione

### 5. User Interaction Tracking (Opzionale)
- Tracciare eventi significativi:
  - Creazione nuova sessione
  - Invio messaggio
  - Upload file
  - Navigazione tra pagine

## 🏗️ Architettura

```
Frontend (React/Next.js)
  ├─ Tracing Module (lib/tracing.ts)
  │   ├─ generateTraceId()
  │   ├─ getCurrentTraceId()
  │   └─ logWithTrace()
  │
  ├─ API Interceptor (lib/api.ts)
  │   ├─ Add X-Trace-ID header
  │   ├─ Measure request duration
  │   └─ Log request/response
  │
  ├─ Error Boundary (components/ErrorBoundary.tsx)
  │   └─ Capture React errors with trace ID
  │
  └─ Performance Monitoring
      ├─ Page load time
      └─ Component render time
```

## 📝 File da Creare/Modificare

1. **`frontend/lib/tracing.ts`** (nuovo)
   - Gestione trace IDs
   - Logging con trace IDs
   - Utility functions

2. **`frontend/lib/api.ts`** (modificare)
   - Aggiungere interceptor per trace IDs
   - Tracciare durata richieste
   - Logging richieste/risposte

3. **`frontend/components/ErrorBoundary.tsx`** (nuovo o modificare)
   - Catturare errori React con trace ID
   - Logging errori

4. **`frontend/app/layout.tsx`** (modificare)
   - Inizializzare tracing
   - Performance monitoring

## 🔧 Dettagli Implementazione

### Trace ID Format
- UUID v4 o formato semplice: `frontend-{timestamp}-{random}`
- Persistente per tutta la durata di una richiesta utente
- Passato a tutte le chiamate API correlate

### API Interceptor
```typescript
// Aggiungere X-Trace-ID header
axios.interceptors.request.use((config) => {
  const traceId = generateTraceId();
  config.headers['X-Trace-ID'] = traceId;
  config.metadata = { startTime: Date.now(), traceId };
  return config;
});

// Log response e durata
axios.interceptors.response.use(
  (response) => {
    const duration = Date.now() - response.config.metadata.startTime;
    logWithTrace(response.config.metadata.traceId, 
      `API ${response.config.method} ${response.config.url} - ${duration}ms`);
    return response;
  },
  (error) => {
    // Log error with trace ID
    return Promise.reject(error);
  }
);
```

### Error Tracking
- React Error Boundary per catturare errori rendering
- Global error handler per errori non catturati
- Includere trace ID in tutti gli errori

## 📊 Metriche da Tracciare

1. **API Metrics**:
   - `frontend_api_requests_total` (counter)
   - `frontend_api_duration_ms` (histogram)
   - `frontend_api_errors_total` (counter)

2. **Performance Metrics**:
   - `frontend_page_load_time_ms` (histogram)
   - `frontend_component_render_time_ms` (histogram)

3. **Error Metrics**:
   - `frontend_errors_total` (counter)
   - `frontend_react_errors_total` (counter)

## 🎯 Benefici

1. **Debugging End-to-End**: Tracciare una richiesta dal click utente fino alla risposta backend
2. **Performance Analysis**: Identificare colli di bottiglia frontend
3. **Error Correlation**: Correlare errori frontend con errori backend usando trace IDs
4. **User Experience**: Monitorare performance percepita dall'utente

## ⚠️ Considerazioni

1. **Privacy**: Non tracciare dati sensibili (password, token, PII)
2. **Performance**: Tracing non deve impattare performance
3. **Sampling**: In produzione, considerare sampling per ridurre overhead
4. **Logging**: Log solo in development o con flag esplicito

