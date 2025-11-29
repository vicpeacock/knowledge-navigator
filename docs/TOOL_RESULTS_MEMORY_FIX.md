# Fix: Tool Results Memory Persistence

## Problema

L'agente non riusciva a utilizzare i risultati intermedi dei tool nelle chiamate successive. Ad esempio:
1. `mcp_search_emails` trova 10 email e restituisce gli ID
2. L'agente chiede conferma per leggere il contenuto
3. L'utente conferma con "si grazie"
4. L'agente non riesce a recuperare gli ID delle email e continua a chiedere

## Causa

I `tool_results` venivano salvati nello stato di LangGraph durante l'esecuzione, ma:
- Non venivano salvati nella memoria a breve termine
- Non venivano recuperati quando si continuava la conversazione dopo un acknowledgement
- Venivano persi quando veniva creata una nuova esecuzione LangGraph

## Soluzione

### 1. Salvataggio tool_results nella memoria a breve termine

**File**: `backend/app/agents/langgraph_app.py` - `knowledge_agent_node`

Quando vengono generati i `tool_results`, vengono salvati nella memoria a breve termine insieme al contesto della conversazione:

```python
# Get existing short-term memory to preserve tool_results
existing_memory = await memory_manager.get_short_term_memory(...)

# Get tool_results from state to save them
tool_results = state.get("tool_results", [])

new_context = {
    "last_user_message": request.message,
    "last_assistant_message": response_text,
    "message_count": len(state.get("previous_messages", [])) + 2,
}

# Preserve tool_results from existing memory and add new ones
if existing_memory:
    existing_tool_results = existing_memory.get("tool_results", [])
    # Merge tool_results, avoiding duplicates
    existing_tool_ids = {(tr.get("tool"), str(tr.get("parameters", {}))) for tr in existing_tool_results}
    for tr in tool_results:
        tool_id = (tr.get("tool"), str(tr.get("parameters", {})))
        if tool_id not in existing_tool_ids:
            existing_tool_results.append(tr)
    new_context["tool_results"] = existing_tool_results
elif tool_results:
    new_context["tool_results"] = tool_results

await memory_manager.update_short_term_memory(...)
```

### 2. Recupero tool_results quando si continua la conversazione

**File**: `backend/app/api/sessions.py` - `chat` endpoint

Quando si recupera la memoria a breve termine, vengono estratti anche i `tool_results` precedenti:

```python
short_term = await memory.get_short_term_memory(db, session_id)
if short_term:
    memory_used["short_term"] = True
    # Extract tool_results from short-term memory if available
    tool_results_from_memory = short_term.get("tool_results", [])
    if tool_results_from_memory:
        from app.agents.langgraph_app import _format_tool_results_for_llm
        tool_results_text = _format_tool_results_for_llm(tool_results_from_memory)
        retrieved_memory.insert(0, f"Risultati tool precedenti:\n{tool_results_text}")
```

### 3. Recupero tool_results durante acknowledgement

**File**: `backend/app/agents/langgraph_app.py` - `tool_loop_node`

Quando l'utente conferma ("si grazie"), i `tool_results` precedenti vengono recuperati dalla memoria a breve termine:

```python
# If this is an acknowledgement, retrieve previous tool_results from short-term memory
if acknowledgement:
    try:
        short_term = await state["memory_manager"].get_short_term_memory(
            state["db"],
            state["session_id"],
        )
        if short_term and short_term.get("tool_results"):
            previous_tool_results = short_term.get("tool_results", [])
            logger.info(f"🔍 Retrieved {len(previous_tool_results)} tool_results from short-term memory for acknowledgement")
            state.setdefault("tool_results", []).extend(previous_tool_results)
    except Exception as mem_error:
        logger.warning(f"⚠️  Error retrieving tool_results from memory: {mem_error}")
```

## Flusso Completo

1. **Prima chiamata**: L'agente esegue `mcp_search_emails` e trova email con ID
   - I `tool_results` vengono salvati nello stato
   - Alla fine dell'esecuzione, vengono salvati nella memoria a breve termine

2. **L'agente chiede conferma**: "Vuoi che recuperi il contenuto di queste email?"

3. **Utente conferma**: "si grazie"
   - Viene creata una nuova esecuzione LangGraph
   - I `tool_results` vengono recuperati dalla memoria a breve termine
   - Vengono aggiunti allo stato prima di eseguire nuovi tool

4. **Seconda chiamata**: L'agente può utilizzare gli ID delle email per chiamare `mcp_get_email`

## Test

Esegui il test per verificare la struttura:

```bash
cd backend
python3 tests/test_tool_results_memory_simple.py
```

Il test verifica che:
- La struttura dei `tool_results` sia corretta
- Gli ID possano essere estratti e utilizzati per chiamate tool successive

## Note

- I `tool_results` vengono salvati nella memoria a breve termine con TTL di `settings.short_term_memory_ttl` (default: 3600 secondi)
- I `tool_results` vengono deduplicati basandosi su tool name e parameters
- I `tool_results` vengono formattati per il LLM usando `_format_tool_results_for_llm`

## Data

2025-11-29

