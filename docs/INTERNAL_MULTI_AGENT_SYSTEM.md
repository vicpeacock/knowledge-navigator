# Sistema Multi-Agente e LangGraph - Knowledge Navigator

## Panoramica

Knowledge Navigator usa LangGraph per orchestrazione di agenti specializzati che lavorano insieme per gestire richieste complesse.

---

## Architettura LangGraph

### Graph Structure

```
event_handler (entry)
    ↓
orchestrator
    ↓
tool_loop
    ↓
knowledge_agent
    ↓
notification_collector
    ↓
response_formatter
    ↓
END
```

### Node Responsibilities

#### event_handler_node
- Normalizza incoming event
- Aggiunge messaggio a history
- Logs activity

#### orchestrator_node
- Routea a next node appropriato (attualmente sempre tool_loop)
- Logs routing decision
- Coordina flusso

#### tool_loop_node
- Gestisce planning (se necessario)
- Esegue tool calls (iterativo)
- Genera risposta (diretta o dopo tool execution)
- Garantisce che response_text non sia mai vuoto

#### knowledge_agent_node
- Aggiorna short-term memory
- Triggera auto-learning in background
- Esegue solo se use_memory=True

#### notification_collector_node
- Raccoglie notifiche da NotificationCenter
- Snapshot notifiche per response

#### response_formatter_node
- Crea ChatResponse da state
- Garantisce che response non sia mai vuoto
- Verifica finale prima di END

---

## Agenti Specializzati

### Main Agent
**Ruolo**: Gestisce interazioni utente, tool calling, generazione risposte

**Capacità**:
- Analizza richieste utente
- Decide quali tool chiamare
- Esegue tool calls iterativamente
- Genera risposte finali

### Knowledge Agent
**Ruolo**: Recupera informazioni da memoria multi-livello

**Capacità**:
- Retrieval da short/medium/long-term memory
- Integra informazioni nel context
- Triggera auto-learning da conversazioni

### Integrity Agent
**Ruolo**: Verifica contraddizioni nella memoria long-term (background)

**Capacità**:
- Controlla coerenza semantica
- Rileva contraddizioni (confidence > 0.90)
- Notifica utente di potenziali problemi

### Planner Agent
**Ruolo**: Crea piani multi-step per task complessi

**Capacità**:
- Analizza richieste complesse
- Genera piani strutturati con step
- Coordina esecuzione sequenziale

### Notification Collector
**Ruolo**: Aggrega notifiche da varie fonti

**Capacità**:
- Raccoglie notifiche da agenti
- Snapshot per response
- Formatta per presentazione utente

---

## State Machine Flow

1. **Event Handler**: Riceve e normalizza evento
2. **Orchestrator**: Decide routing
3. **Tool Loop**: Esegue tool calls iterativamente
4. **Knowledge Agent**: Recupera e integra memoria
5. **Notification Collector**: Raccoglie notifiche
6. **Response Formatter**: Formatta risposta finale

---

## Fallback Layers

Sistema implementa multiple fallback layers per garantire risposte sempre valide:

1. **Tool Loop**: Controlla response vuoto dopo tool execution
2. **Response Formatter**: Verifica response prima di creare ChatResponse
3. **Run LangGraph**: Verifica chat_response in final_state
4. **Chat Endpoint**: Final check prima di return frontend

---

## Tool Integration

Tool sono descritti funzionalmente:
- **What**: Cosa fa il tool
- **When**: Quando usarlo (con esempi)
- **How**: Come usarlo (parametri)

LLM decide basandosi su descrizioni, non hardcoded heuristics.

---

## Error Handling

Ogni node:
- Gestisce errori gracefully con fallback
- Logs execution con proper levels
- Emette telemetry events
- Garantisce state sempre valido

---

## Implementazione

**File Principale**: `backend/app/agents/langgraph_app.py`

**State Schema**: Definito in `LangGraphState` con tutti i campi necessari

**Graph Building**: Costruito dinamicamente con logging completo

---

## Riferimenti

- `backend/app/agents/langgraph_app.py` - Implementazione LangGraph
- `backend/app/agents/main_agent.py` - Main agent pipeline
- `backend/app/core/tool_manager.py` - Tool descriptions e management
