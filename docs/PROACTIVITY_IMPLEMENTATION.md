# Implementazione Sistema Proattività

## 📋 Panoramica

Sistema implementato per rilevare automaticamente eventi esterni (email, calendario) e creare notifiche proattive per l'utente.

**Data Implementazione**: 2025-11-17  
**Status**: ✅ Base Implementation Completa

---

## 🏗️ Architettura Implementata

### Componenti Principali

1. **EventMonitor** (`backend/app/services/event_monitor.py`)
   - Orchestratore principale
   - Avvia polling automatico ogni minuto (configurabile)
   - Gestisce lifecycle del sistema

2. **EmailPoller** (`backend/app/services/schedulers/email_poller.py`)
   - Controlla tutte le integrazioni Gmail attive
   - Rileva nuove email non lette (ultime 24 ore)
   - Crea notifiche con priorità basata su contenuto

3. **CalendarWatcher** (`backend/app/services/schedulers/calendar_watcher.py`)
   - Controlla tutte le integrazioni Google Calendar attive
   - Rileva eventi imminenti (prossime 2 ore)
   - Crea reminder a 15 minuti e 5 minuti prima dell'evento

4. **NotificationService** (già esistente)
   - Gestisce creazione e storage notifiche
   - Integrato con database e sistema multi-tenant

---

## 🔄 Flusso di Funzionamento

### 1. Avvio Automatico

All'avvio del backend:
```
Backend Startup
  ↓
EventMonitor.start()
  ↓
Background Loop (ogni 60 secondi)
  ↓
_check_all_events()
  ├─ EmailPoller.check_new_emails()
  └─ CalendarWatcher.check_upcoming_events()
```

### 2. Email Polling

```
EmailPoller.check_new_emails()
  ↓
Per ogni integrazione Gmail attiva:
  ├─ Decrypt credentials
  ├─ Setup Gmail service
  ├─ Query: "is:unread newer_than:1d"
  ├─ Filtra email già controllate (tracking last_email_id)
  └─ Per ogni nuova email:
      ├─ Determina priorità (high/medium/low)
      └─ Crea notifica via NotificationService
```

**Priorità Email:**
- **High**: Oggetto contiene parole chiave urgenti ("urgent", "asap", "important")
- **Medium**: Email molto recente (< 5 minuti)
- **Low**: Default

### 3. Calendar Watching

```
CalendarWatcher.check_upcoming_events()
  ↓
Per ogni integrazione Calendar attiva:
  ├─ Decrypt credentials
  ├─ Setup Calendar service
  ├─ Query eventi prossime 2 ore
  └─ Per ogni evento:
      ├─ Calcola tempo rimanente
      ├─ Se siamo a 15min o 5min prima:
      │   ├─ Determina priorità (high se ≤5min, medium se 15min)
      │   └─ Crea notifica via NotificationService
      └─ Evita duplicati (tracking per evento)
```

**Reminder Times:**
- 15 minuti prima → priorità "medium"
- 5 minuti prima → priorità "high"

---

## 📊 Tipi di Notifiche Create

### Email Notifications

**Type**: `email_received`  
**Content**:
```json
{
  "email_id": "gmail_message_id",
  "from": "sender@example.com",
  "subject": "Email subject",
  "snippet": "First 200 chars...",
  "date": "2025-11-17T10:30:00Z",
  "integration_id": "uuid"
}
```

**Urgency**: `high` | `medium` | `low`

### Calendar Notifications

**Type**: `calendar_event_starting`  
**Content**:
```json
{
  "event_id": "google_calendar_event_id",
  "title": "Meeting Title",
  "start_time": "2025-11-17T15:00:00Z",
  "location": "Conference Room A",
  "reminder_minutes": 15,
  "time_until_start_minutes": 15,
  "integration_id": "uuid"
}
```

**Urgency**: `high` (5min) | `medium` (15min)

---

## ⚙️ Configurazione

### Variabili Ambiente

```python
# backend/app/core/config.py
event_monitor_enabled: bool = True  # Abilita/disabilita sistema
event_monitor_poll_interval_seconds: int = 60  # Frequenza polling (default: 1 minuto)
email_poller_enabled: bool = True  # Abilita email polling
calendar_watcher_enabled: bool = True  # Abilita calendar watching
```

### Disabilitare Sistema

Per disabilitare completamente:
```bash
# Nel .env
EVENT_MONITOR_ENABLED=false
```

Per disabilitare solo email o solo calendario:
```bash
EMAIL_POLLER_ENABLED=false
# oppure
CALENDAR_WATCHER_ENABLED=false
```

---

## 🧪 Testing

### Test Manuale

Endpoint API per triggerare check manuale:
```bash
POST /api/notifications/check-events
```

**Response**:
```json
{
  "message": "Event check completed",
  "notifications_created": 3,
  "notifications": [...]
}
```

### Verifica Notifiche

```bash
GET /api/notifications?read=false
```

Mostra tutte le notifiche non lette create dal sistema.

---

## 📝 Logging

Il sistema logga tutte le operazioni:

```
INFO: Checking 2 Gmail integrations for new emails
INFO: 📧 Found 3 new email events
INFO: Created notification for new email from sender@example.com (priority: high)
INFO: Checking 1 Calendar integrations for upcoming events
INFO: 📅 Found 2 upcoming calendar events
INFO: Created notification for event 'Meeting' starting in 15 minutes
```

---

## 🔍 Tracking e Deduplicazione

### Email Tracking

- **Last Email ID**: Traccia l'ultima email controllata per integrazione
- **Storage**: In-memory (`_last_email_ids` dict)
- **Limite**: Prima volta prende solo le 5 più recenti per evitare spam

### Calendar Tracking

- **Reminder Tracking**: TODO - implementare tracking notifiche già inviate
- **Attualmente**: Crea notifica ogni volta che viene rilevato il reminder
- **Miglioramento futuro**: Usare database per tracciare notifiche già inviate

---

## 🚀 Prossimi Sviluppi

### Priorità Alta

1. **Tracking Notifiche Calendar**
   - Evitare duplicati per stesso evento/reminder
   - Usare database o cache per tracciare notifiche inviate

2. **WebSocket Real-time**
   - Notifiche push immediate al frontend
   - Non richiede polling frontend

3. **Filtri Utente**
   - Configurazione per utente su cosa ricevere
   - Quiet hours (non disturbare in certi orari)
   - Filtri per mittenti/eventi

### Priorità Media

4. **Motore Decisionale Avanzato**
   - LLM per valutare importanza email
   - Analisi contenuto per determinare priorità
   - Apprendimento da preferenze utente

5. **Messaggi Proattivi**
   - Generare messaggi proattivi con LLM
   - Es: "Ho ricevuto un'email da Mario. Vuoi che te la legga?"

6. **User Context**
   - Collegare notifiche a sessioni utente
   - Permettere risposte proattive

---

## 📚 File Creati/Modificati

### Nuovi File

- `backend/app/services/event_monitor.py` - Orchestratore principale
- `backend/app/services/schedulers/__init__.py` - Package init
- `backend/app/services/schedulers/email_poller.py` - Email polling
- `backend/app/services/schedulers/calendar_watcher.py` - Calendar watching

### File Modificati

- `backend/app/main.py` - Integrazione EventMonitor nel lifespan
- `backend/app/core/config.py` - Aggiunte configurazioni proattività
- `backend/app/api/notifications.py` - Aggiunto endpoint test manuale
- `docs/ROADMAP.md` - Aggiornato stato implementazione

---

## 🐛 Limitazioni Attuali

1. **Email Tracking**: Solo in-memory, si resetta al riavvio backend
2. **Calendar Tracking**: Non traccia notifiche già inviate (può duplicare)
3. **User Context**: Notifiche non collegate a sessioni utente specifiche
4. **Priorità**: Logica semplice, non usa LLM per valutazione avanzata
5. **Filtri**: Nessun filtro configurabile per utente

---

## ✅ Funzionalità Implementate

- ✅ Polling automatico email ogni minuto
- ✅ Polling automatico calendario ogni minuto
- ✅ Creazione notifiche automatica
- ✅ Priorità basica (high/medium/low)
- ✅ Multi-tenant support (notifiche isolate per tenant)
- ✅ Integrazione con sistema notifiche esistente
- ✅ Endpoint test manuale
- ✅ Logging completo
- ✅ Gestione errori robusta (continua anche se una integrazione fallisce)

---

**Ultimo aggiornamento**: 2025-11-17  
**Versione**: 1.0

