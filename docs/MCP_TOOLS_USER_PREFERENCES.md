# MCP Tools - Preferenze per Utente

## 📋 Panoramica

Le preferenze dei tools MCP sono ora gestite per utente, permettendo a ogni utente di selezionare i tools che desidera utilizzare, indipendentemente dagli altri utenti dello stesso tenant.

## 🎯 Funzionalità

### Preferenze per Utente
- Ogni utente può selezionare i propri tools MCP preferiti
- Le preferenze sono salvate in `user_metadata.mcp_tools_preferences`
- Formato: `{integration_id: [tool_names]}`
- Le preferenze sono isolate per utente (admin e utenti normali hanno selezioni indipendenti)

### Interfaccia Semplificata
- **Utenti normali**: Vedono solo il bottone "Manage Tools"
- **Admin**: Vedono tutte le funzionalità (Test, Debug, Remove, Connect New MCP Server)

## 🏗️ Architettura

### Backend

#### Salvataggio Preferenze
- **Endpoint**: `POST /api/integrations/mcp/{integration_id}/tools/select`
- **Dati**: `{tool_names: string[]}`
- **Storage**: `user_metadata.mcp_tools_preferences[integration_id] = tool_names`
- **Metodo**: UPDATE esplicito su tabella `users` per garantire il salvataggio corretto dei campi JSONB

#### Lettura Preferenze
- **Endpoint**: `GET /api/integrations/mcp/{integration_id}/tools`
- **Dati letti da**: `user_metadata.mcp_tools_preferences[integration_id]`
- **Ritorna**: `{available_tools, selected_tools}`

#### ToolManager
- `get_mcp_tools(current_user)`: Filtra i tools in base alle preferenze utente
- Se l'utente non ha preferenze per un'integrazione, quella integrazione viene saltata

### Frontend

#### Gestione Tools
- **Pagina**: `/integrations`
- **Sezione MCP**: Mostra tutte le integrazioni MCP disponibili
- **Bottone "Manage Tools"**: Apre pannello per selezionare tools
- **Salvataggio**: Dopo il salvataggio, ricarica automaticamente i tools dal server

#### UI Differenziata
- **Utenti normali**: Solo "Manage Tools"
- **Admin**: "Manage Tools", "Test", "Debug", "Remove", "Connect New MCP Server"

## 📝 Flusso Utente

1. Utente accede a `/integrations`
2. Clicca su "Manage Tools" per un'integrazione MCP
3. Seleziona i tools desiderati dalle checkbox
4. Clicca "Save Selection"
5. Il sistema salva le preferenze in `user_metadata`
6. I tools selezionati vengono ricaricati dal server
7. Messaggio di successo conferma il salvataggio

## 🔧 Dettagli Tecnici

### Struttura Dati

```json
{
  "user_metadata": {
    "mcp_tools_preferences": {
      "integration_id_1": ["tool1", "tool2"],
      "integration_id_2": ["tool3"]
    }
  }
}
```

### Query Database

```python
# Salvataggio
await db.execute(
    update(User)
    .where(User.id == current_user.id)
    .values(user_metadata=user_metadata)
)

# Lettura
user_metadata = current_user.user_metadata or {}
mcp_preferences = user_metadata.get("mcp_tools_preferences", {})
selected_tools = mcp_preferences.get(str(integration_id), [])
```

## ✅ Testing

### Test Manuali
1. Login come utente normale
2. Seleziona tools MCP
3. Salva e verifica che le preferenze siano salvate
4. Logout e login come admin
5. Verifica che le preferenze siano diverse

### Verifica Salvataggio
- Il backend verifica il salvataggio leggendo `user_metadata` dopo il commit
- Il frontend ricarica i tools dal server dopo il salvataggio
- Messaggi di successo/errore informano l'utente

## 🐛 Fix Implementati

### Problema: Preferenze non salvate
- **Causa**: SQLAlchemy non rilevava le modifiche ai campi JSONB quando si modificava direttamente l'oggetto
- **Soluzione**: Uso di UPDATE esplicito con creazione di nuovi dict per garantire che SQLAlchemy rilevi le modifiche

### Problema: UI troppo complessa per utenti normali
- **Causa**: Tutti gli utenti vedevano tutte le funzionalità MCP
- **Soluzione**: UI differenziata basata sul ruolo utente (`user.role === 'admin'`)

## 📚 Riferimenti

- `backend/app/api/integrations/mcp.py`: Endpoint MCP
- `backend/app/core/tool_manager.py`: Gestione tools MCP
- `frontend/app/integrations/page.tsx`: UI integrazioni MCP

