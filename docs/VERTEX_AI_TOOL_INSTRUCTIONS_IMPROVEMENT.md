# Miglioramento delle Istruzioni Tool per Vertex AI

## Problema Identificato

Vertex AI riceveva istruzioni hardcoded generiche sui tool invece di utilizzare le descrizioni reali fornite dal MCP server. Questo causava:

1. **Istruzioni generiche**: Esempi hardcoded come "usa mcp_get_events per calendario" invece di descrizioni specifiche
2. **Mancanza di contesto**: Le descrizioni dettagliate dal MCP server venivano ignorate nelle istruzioni testuali
3. **Ridondanza**: Le Function Declarations già contenevano le descrizioni, ma le istruzioni testuali non le utilizzavano

## Soluzione Implementata

### Modifiche a `backend/app/core/vertex_ai_client.py`

**Prima** (hardcoded generico):
```python
tool_instruction = f"""
IMPORTANTE - Uso dei Tool:
Hai accesso ai seguenti tool: {', '.join(tool_names[:10])}...

Quando l'utente chiede informazioni o azioni che richiedono questi tool, DEVI chiamarli:
- Per controllare il calendario → usa mcp_get_events o mcp_list_calendars
- Per leggere email → usa mcp_search_gmail_messages...
"""
```

**Dopo** (usa descrizioni MCP reali):
```python
# Build instructions from actual tool descriptions
tool_descriptions = []
for tool in tools:
    tool_name = tool.get("name", "unknown")
    tool_description = tool.get("description", "")  # ← Descrizione reale dal MCP!
    if tool_description:
        tool_descriptions.append(f"- {tool_name}: {tool_description}")

tool_instruction = f"""
IMPORTANTE - Uso dei Tool:
Hai accesso ai seguenti tool ({len(tool_names)} totali):

{chr(10).join(shown_tools)}
...
Ogni tool ha una descrizione specifica che indica quando e come usarlo - segui quelle descrizioni.
"""
```

## Vantaggi

1. **Descrizioni Specifiche**: Ogni tool ha la sua descrizione dettagliata che spiega esattamente quando e come usarlo
2. **Auto-Aggiornamento**: Quando il MCP server aggiorna le descrizioni dei tool, Vertex AI le riceve automaticamente
3. **Coerenza**: Le istruzioni testuali ora corrispondono alle Function Declarations strutturate
4. **Meno Confusione**: Nessuna istruzione generica che potrebbe sovrascrivere o confondere le descrizioni reali
5. **Supporto `tools_description`**: Ora viene anche utilizzato il parametro `tools_description` se fornito (per informazioni aggiuntive)

## Come Funziona

1. **Recupero Descrizioni**: Le descrizioni vengono recuperate direttamente dai tool objects passati a `generate_with_context()`
2. **Formattazione**: Vengono formattate come lista con nome e descrizione per ogni tool
3. **Limitazione**: Mostra fino a 15 tool con descrizioni complete, poi un riepilogo se ce ne sono di più
4. **Integrazione**: Le istruzioni vengono aggiunte al `system_instruction` insieme alle Function Declarations strutturate

## Esempio di Output

```
IMPORTANTE - Uso dei Tool:
Hai accesso ai seguenti tool (83 totali):

- mcp_get_events: Retrieve calendar events for a specific calendar. Use when user asks about events, appointments, or schedule.
- mcp_search_gmail_messages: Search for Gmail messages using Gmail query syntax. Use when user asks about emails or messages.
- mcp_get_drive_file_content: Get the content of a Google Drive file. Use when user asks to read or view a file.
- customsearch_search: Search the web using Google Custom Search API. Use when user asks to search for information online.
...

IMPORTANTE: Quando l'utente chiede informazioni o azioni, usa SEMPRE i tool appropriati basandoti sulle loro descrizioni sopra.
Ogni tool ha una descrizione specifica che indica quando e come usarlo - segui quelle descrizioni.
```

## Test

Per verificare che funzioni:

1. Esegui una richiesta che richiede l'uso di tool MCP (es. "cerca file su Google Drive")
2. Verifica nei log che le descrizioni dei tool siano incluse nelle istruzioni
3. Verifica che Vertex AI utilizzi correttamente i tool basandosi sulle descrizioni

## Riferimenti

- File modificato: `backend/app/core/vertex_ai_client.py`
- Commit: "Improve Vertex AI tool instructions to use actual MCP tool descriptions instead of hardcoded generic examples"
- Deployment: Backend deployato su Cloud Run con le nuove istruzioni

