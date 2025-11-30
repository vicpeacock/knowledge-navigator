# Sistema Tool - Knowledge Navigator

## Panoramica

Sistema di integrazione tool per azioni esterne e automazione.

---

## Categorie Tool

### Base Tools (Built-in)
- `get_calendar_events` - Google Calendar integration
- `get_emails` - Gmail integration
- `summarize_emails` - AI email summarization
- `web_search` / `customsearch_search` - Ricerca web
- `web_fetch` - Fetch contenuto pagina web

### MCP Tools (Dynamic)
- Browser tools (Playwright): navigate, snapshot, click, evaluate
- Tools da MCP servers esterni (configurabili)

### Google Workspace
- Calendar: read events, natural language queries
- Gmail: read, send, archive
- Drive: file access e management
- Tasks: create, list, update

---

## Tool Execution Flow

```
LLM Request
    ↓
Tool Selection (LLM decides)
    ↓
Tool Execution
    ↓
Result Integration
    ↓
Response Generation
```

---

## Tool Descriptions

Tool hanno descrizioni funzionali:
- **What**: Cosa fa
- **When**: Quando usarlo (con esempi)
- **How**: Come usarlo (parametri)

---

## Riferimenti

- `backend/app/core/tool_manager.py` - Tool management
- `backend/app/api/integrations/` - Integrazioni Google Workspace
- `backend/app/api/integrations/mcp.py` - MCP Gateway
