# Tool Preferences vs Background Services

## 📋 Panoramica

Questo documento spiega la differenza tra le **preferenze tool** (che controllano quali tool l'LLM può usare durante le chat) e i **servizi di background** (che creano notifiche automaticamente).

## 🔧 Tool Preferences

Le **preferenze tool** (`enabled_tools` in `user_metadata`) controllano quali tool sono disponibili per l'LLM durante le chat con l'assistente.

### Come Funzionano

1. **Filtro in `get_available_tools()`**: I tool vengono filtrati prima di essere passati all'LLM
2. **Check in `execute_tool()`**: Prima di eseguire un tool, viene verificato se è abilitato
3. **Scope**: Si applicano solo ai tool usati dall'LLM durante le chat

### Tool Built-in Affetti

- `get_emails`: Recupera email da Gmail
- `get_calendar_events`: Recupera eventi dal calendario
- `send_email`: Invia email
- `web_search`: Cerca sul web
- `web_fetch`: Recupera contenuto web
- Altri tool built-in...

### Tool MCP Affetti

- Tutti i tool MCP selezionati dall'utente tramite `mcp_tools_preferences`

## 🔄 Background Services

I **servizi di background** (`EmailPoller`, `CalendarWatcher`) creano notifiche automaticamente **indipendentemente** dalle preferenze tool.

### Come Funzionano

1. **EmailPoller**: Controlla periodicamente le integrazioni Gmail e crea notifiche per nuove email
2. **CalendarWatcher**: Controlla periodicamente le integrazioni Google Calendar e crea notifiche per eventi imminenti
3. **Scope**: Funzionano indipendentemente dalle preferenze tool perché:
   - Non usano i tool, ma accedono direttamente alle integrazioni
   - Usano `EmailService` e `CalendarService` direttamente
   - Sono progettati per funzionare automaticamente in background

### Perché Bypassano le Preferenze Tool

1. **Sistema Proattivo**: Le notifiche sono proattive, non reattive
2. **Indipendenza**: Il sistema di background deve funzionare anche se l'utente non sta chattando
3. **Separazione delle Responsabilità**: Le preferenze tool controllano l'LLM, non il sistema di background

## ⚠️ Comportamento Attuale

### Scenario: Utente Disabilita `get_emails` e `get_calendar_events`

**Risultato**:
- ✅ L'LLM **NON può** usare `get_emails` e `get_calendar_events` durante le chat
- ✅ Le notifiche email e calendario **continuano** a essere create dal sistema di background

**Perché**:
- Le preferenze tool controllano solo i tool usati dall'LLM
- Il sistema di background usa direttamente le integrazioni, non i tool

## 🎯 Come Disabilitare le Notifiche

Se l'utente vuole disabilitare le notifiche email/calendario, ha diverse opzioni:

### Opzione 1: Disabilitare tramite Settings del Profilo (Raccomandato)

1. Andare su `/settings/profile`
2. Nella sezione "Background Services", disabilitare:
   - **Email Notifications**: Disabilita le notifiche per nuove email
   - **Calendar Notifications**: Disabilita le notifiche per eventi imminenti
3. Cliccare "Save Preferences"

Questa è l'opzione più semplice e permette di controllare le notifiche senza disabilitare le integrazioni.

### Opzione 2: Disabilitare le Integrazioni

1. Andare su `/integrations`
2. Disabilitare le integrazioni Gmail/Calendar

**Nota**: Questo disabilita completamente l'accesso alle email/calendario, non solo le notifiche.

### Opzione 3: Disabilitare i Servizi di Background Globalmente

Modificare le impostazioni in `.env`:
```
EMAIL_POLLER_ENABLED=false
CALENDAR_WATCHER_ENABLED=false
```

**Nota**: Questo disabilita i servizi per tutti gli utenti del tenant.

## 🔍 Verifica

Per verificare se le preferenze tool funzionano correttamente:

1. **Controllare i log**: Cercare `🔒 Filtered tools by user preferences` nei log del backend
2. **Testare l'esecuzione**: Provare a usare un tool disabilitato durante una chat
3. **Verificare le notifiche**: Le notifiche dovrebbero continuare a essere create anche se i tool sono disabilitati

## 📝 Note Tecniche

### Codice Rilevante

- `backend/app/core/tool_manager.py`:
  - `get_available_tools()`: Filtra i tool in base alle preferenze
  - `execute_tool()`: Verifica se un tool è abilitato prima di eseguirlo
- `backend/app/services/schedulers/email_poller.py`: Crea notifiche email indipendentemente dalle preferenze tool
- `backend/app/services/schedulers/calendar_watcher.py`: Crea notifiche calendario indipendentemente dalle preferenze tool
- `backend/app/services/event_monitor.py`: Orchestratore dei servizi di background

### Architettura

```
┌─────────────────────────────────────────────────────────┐
│                    Tool Preferences                      │
│  (Controlla quali tool l'LLM può usare nelle chat)      │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│              ToolManager.execute_tool()                  │
│  (Verifica se il tool è abilitato prima di eseguirlo)    │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              Background Services                        │
│  (Creano notifiche automaticamente)                     │
└─────────────────────────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        ▼                                 ▼
┌──────────────────┐          ┌──────────────────┐
│  EmailPoller     │          │ CalendarWatcher  │
│  (Usa EmailService│          │ (Usa CalendarService│
│   direttamente)  │          │  direttamente)   │
└──────────────────┘          └──────────────────┘
```

## ✅ Conclusione

Le **preferenze tool** e i **servizi di background** sono due sistemi separati:

- **Preferenze tool**: Controllano quali tool l'LLM può usare durante le chat
- **Servizi di background**: Creano notifiche automaticamente indipendentemente dalle preferenze tool

### Nuova Funzionalità: Preferenze Servizi di Background

Ora è possibile controllare i servizi di background tramite le preferenze utente:

- **Email Notifications**: Controlla se ricevere notifiche per nuove email
- **Calendar Notifications**: Controlla se ricevere notifiche per eventi imminenti

Queste preferenze sono disponibili in `/settings/profile` nella sezione "Background Services".

**Comportamento**:
- Se un'integrazione ha un `user_id`, le preferenze di quell'utente vengono rispettate
- Se un'integrazione è globale (`user_id = NULL`), le notifiche vengono create per tutti gli utenti (backward compatibility)

Questo permette un controllo granulare sulle notifiche senza disabilitare le integrazioni o i tool.

