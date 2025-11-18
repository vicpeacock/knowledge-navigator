# Sistema di Sessioni Giornaliere e Miglioramenti Notifiche

## Data: Novembre 2025

## Panoramica

Questo documento descrive le implementazioni principali relative al sistema di sessioni giornaliere e ai miglioramenti al sistema di notifiche.

---

## 1. Sistema di Sessioni Giornaliere

### 1.1 Concetto

Il sistema gestisce le sessioni su base giornaliera invece di creare sessioni ad-hoc per ogni interazione. Ogni utente ha una sessione attiva per giorno, che viene automaticamente archiviata e riassunta quando inizia un nuovo giorno.

### 1.2 Componenti Principali

#### `DailySessionManager` (`backend/app/services/daily_session_manager.py`)

Servizio che gestisce le sessioni giornaliere:

- **`get_or_create_today_session(user_id, tenant_id)`**: Recupera o crea la sessione del giorno corrente
- **`check_day_transition(user_id, tenant_id, current_session_id)`**: Verifica se è necessario passare a un nuovo giorno
- **`_check_and_archive_yesterday_session(user, tenant_id, user_id)`**: Archivia la sessione del giorno precedente
- **`_generate_daily_summary(session)`**: Genera un riassunto della sessione usando l'LLM e lo aggiunge alla memoria a lungo termine

#### Modifiche al Database

- Aggiunto campo `timezone` alla tabella `users` (default: "UTC")
- Aggiunto campo `inactivity_timeout_minutes` alla tabella `users` (default: 30)
- Migration: `4d2ea1f98574_add_user_timezone_and_inactivity_timeout.py`

#### Integrazione con Email

- `EmailActionProcessor` ora aggiunge le email alla sessione giornaliera invece di creare sessioni ad-hoc
- Deduplicazione basata su `email_id` nei messaggi per evitare duplicati
- Tracking delle email processate nel metadata della sessione

### 1.3 Transizione di Giorno

Quando viene rilevata una transizione di giorno durante un'interazione:

1. Il backend rileva che la sessione corrente è di un giorno precedente
2. Restituisce un flag `day_transition_pending=True` nella risposta
3. Il frontend mostra un dialog (`DayTransitionDialog`) per confermare il passaggio
4. Se l'utente conferma, viene creata una nuova sessione e la vecchia viene archiviata
5. Il riassunto della sessione precedente viene aggiunto alla memoria a lungo termine

#### Componente Frontend: `DayTransitionDialog`

- Dialog modale per confermare la transizione
- Opzioni: "Rimani su Ieri" o "Continua con Oggi"
- Navigazione automatica alla nuova sessione dopo conferma

### 1.4 Script di Gestione

#### `cleanup_sessions_and_memory.py`

Script per pulire le sessioni e la memoria:

- Rimuove tutte le sessioni tranne quella di oggi dell'admin
- Rimuove le notifiche associate prima di eliminare le sessioni
- Pulisce la memoria a lungo termine da PostgreSQL e ChromaDB

#### `create_today_session.py`

Script per creare la sessione giornaliera per l'admin:

- Trova l'utente admin (cerca prima `admin@example.com`, poi qualsiasi admin)
- Crea o recupera la sessione del giorno corrente
- Gestisce il timezone dell'utente

---

## 2. Gestione Memoria a Lungo Termine

### 2.1 Nuovi Endpoint API

#### `GET /api/memory/long/list`

Lista tutte le memorie a lungo termine con paginazione:

- Parametri: `limit`, `offset`, `min_importance`
- Restituisce: lista di memorie con dettagli completi

#### `POST /api/memory/long/batch/delete`

Cancellazione batch di memorie (solo admin):

- Accetta array di `memory_ids`
- Elimina da PostgreSQL e ChromaDB
- Restituisce conteggio delle memorie eliminate

### 2.2 Componente Frontend: `LongTermMemoryManager`

Pagina dedicata per gestire la memoria a lungo termine:

- Lista completa delle memorie con paginazione
- Checkboxes per selezione multipla
- Pulsante "Seleziona/Deseleziona Tutto"
- Cancellazione batch delle memorie selezionate
- Cancellazione singola per ogni memoria
- Visualizzazione di importanza, data di creazione, sessioni di origine

### 2.3 Navigazione

La pagina `/memory` ora ha due tab:
- **Gestione Memoria**: `LongTermMemoryManager` per gestire le memorie
- **Ricerca Memoria**: `MemoryView` per cercare nella memoria

---

## 3. Miglioramenti Sistema Notifiche

### 3.1 Ottimizzazioni Database

#### Indici Aggiunti

Migration: `add_notification_indexes.py`

- **Indice composito**: `ix_notifications_tenant_read_created` su `(tenant_id, read, created_at DESC)`
- **Indice tipo**: `ix_notifications_tenant_type` su `(tenant_id, type)`
- **Indice urgenza**: `ix_notifications_tenant_urgency` su `(tenant_id, urgency)`
- **Indice read**: `ix_notifications_tenant_read` su `(tenant_id, read)`
- **Indice GIN**: `ix_notifications_content_gin` su `content` (JSONB) per query JSON efficienti

#### Ottimizzazione Query

**Prima**: Query O(n) - una query al database per ogni notifica per verificare le integrazioni

**Dopo**: Query O(1) - pre-caricamento di tutte le integrazioni una volta sola

```python
# Pre-load integrations once
user_integrations = {str(i.id): i for i in user_integrations_result.scalars().all()}
integrations_without_user_id = {str(i.id): i for i in integrations_without_user_id_result.scalars().all()}

# Use cached lookups instead of querying per notification
if integration_id_str in user_integrations:
    # Allow notification
```

### 3.2 Server-Sent Events (SSE) per Notifiche Real-Time

#### Endpoint: `GET /api/notifications/stream`

- Stream SSE per aggiornamenti in tempo reale
- Controlla il conteggio delle notifiche ogni 2 secondi
- Invia aggiornamenti quando il conteggio cambia
- Include filtraggio per utente corrente

#### Integrazione Frontend

- `NotificationBell` usa SSE quando il popup è aperto
- Fallback automatico al polling se SSE non è disponibile
- Polling ogni 10 secondi quando il popup è chiuso

### 3.3 Pagina Dedicata Notifiche

#### Route: `/notifications`

Pagina completa per gestire tutte le notifiche:

**Filtri**:
- Urgenza (high, medium, low)
- Tipo (email_received, calendar_event_starting, contradiction, todo)
- Stato (lette/non lette)

**Funzionalità**:
- Paginazione (limit/offset)
- Selezione multipla con checkboxes
- Cancellazione batch
- "Segna tutte come lette"
- Visualizzazione raggruppata per tipo
- Icone per tipo di notifica
- Badge colorati per urgenza
- Pulsante "Torna indietro"

### 3.4 Miglioramenti UI NotificationBell

**Raggruppamento**:
- Notifiche raggruppate per tipo
- Header con conteggio per tipo quando ci sono più notifiche dello stesso tipo

**Nuovi Pulsanti**:
- "Segna Lette": marca tutte le notifiche come lette
- "Pulisci": elimina tutte le notifiche pendenti (batch delete)
- "Vedi Tutte": link alla pagina dedicata `/notifications`

**Real-Time**:
- SSE quando popup aperto per aggiornamenti immediati
- Polling quando popup chiuso per mantenere conteggio aggiornato

### 3.5 Nuovi Endpoint API

#### `GET /api/notifications/`

Lista notifiche con filtri e paginazione:
- Parametri: `session_id`, `urgency`, `read`, `limit`, `offset`

#### `GET /api/notifications/count`

Conta notifiche con filtri:
- Parametri: `session_id`, `urgency`, `read`

#### `POST /api/notifications/read-all`

Marca tutte le notifiche come lette:
- Parametri opzionali: `session_id`, `urgency`

#### `POST /api/notifications/batch/delete`

Cancellazione batch:
- Body: array di `notification_ids`

---

## 4. Testing

### 4.1 Test Backend

#### `test_daily_session_integration.py`

Test di integrazione per sessioni giornaliere:
- Email aggiunta alla sessione giornaliera
- Deduplicazione email
- Tracking metadata sessione
- Email multiple stessa sessione

#### `test_day_transition_api.py`

Test per transizione di giorno:
- Rilevamento transizione
- Struttura ChatResponse con flag di transizione

### 4.2 Test Frontend

#### `DayTransitionDialog.test.tsx`

Test per il componente dialog:
- Rendering condizionale
- Interazioni pulsanti
- Navigazione
- Gestione errori

---

## 5. File Modificati/Creati

### Backend

**Nuovi File**:
- `backend/app/services/daily_session_manager.py`
- `backend/alembic/versions/4d2ea1f98574_add_user_timezone_and_inactivity_timeout.py`
- `backend/alembic/versions/add_notification_indexes.py`
- `backend/scripts/cleanup_sessions_and_memory.py`
- `backend/scripts/create_today_session.py`
- `backend/tests/test_daily_session_integration.py`
- `backend/tests/test_day_transition_api.py`

**File Modificati**:
- `backend/app/models/database.py` - Aggiunti campi `timezone` e `inactivity_timeout_minutes` a User
- `backend/app/models/schemas.py` - Aggiunti campi `day_transition_pending` e `new_session_id` a ChatResponse
- `backend/app/api/sessions.py` - Integrazione DailySessionManager, ottimizzazione query notifiche
- `backend/app/api/memory.py` - Nuovi endpoint per gestione memoria
- `backend/app/api/notifications.py` - Endpoint SSE, batch delete, paginazione
- `backend/app/services/email_action_processor.py` - Integrazione DailySessionManager
- `backend/app/services/notification_service.py` - Supporto paginazione
- `backend/app/core/dependencies.py` - Dependency per DailySessionManager

### Frontend

**Nuovi File**:
- `frontend/components/DayTransitionDialog.tsx`
- `frontend/components/LongTermMemoryManager.tsx`
- `frontend/app/notifications/page.tsx`
- `frontend/components/DayTransitionDialog.test.tsx`

**File Modificati**:
- `frontend/components/ChatInterface.tsx` - Integrazione DayTransitionDialog
- `frontend/components/NotificationBell.tsx` - SSE, raggruppamento, nuovi pulsanti
- `frontend/app/memory/page.tsx` - Tab navigation
- `frontend/lib/api.ts` - Nuovi endpoint API
- `frontend/types/index.ts` - Nuovi tipi per day transition

---

## 6. Configurazione

### 6.1 Timezone Utente

Gli utenti possono configurare il loro timezone nel profilo. Il sistema usa questo timezone per:
- Determinare quando inizia un nuovo giorno
- Nome delle sessioni giornaliere (es. "Sessione 2025-11-18")
- Archiviazione automatica alla fine del giorno

### 6.2 Inactivity Timeout

Campo `inactivity_timeout_minutes` nel profilo utente (default: 30 minuti). Previsto per implementazione futura di screen saver con richiesta password.

---

## 7. Prossimi Passi

### 7.1 Screen Saver

Implementare screen saver che si attiva dopo `inactivity_timeout_minutes` di inattività:
- Frontend entra in modalità screen saver
- Richiede password per riattivare
- Previene accesso non autorizzato quando l'utente è assente

### 7.2 Miglioramenti Notifiche

- Notifiche push browser (quando supportato)
- Suoni/notifiche desktop per urgenza alta
- Raggruppamento intelligente di notifiche simili
- Notifiche programmate/ricorrenti

### 7.3 Ottimizzazioni

- Cache delle integrazioni a livello di applicazione
- WebSocket invece di SSE per notifiche bidirezionali
- Compressione delle notifiche per ridurre traffico

---

## 8. Note Tecniche

### 8.1 Deduplicazione Email

Le email vengono deduplicate controllando:
1. Notifiche esistenti con stesso `email_id` e `integration_id`
2. Messaggi esistenti con `email_id` nel metadata
3. Sessioni create da email con stesso `email_id`

### 8.2 Filtraggio Notifiche Multi-User

Il sistema filtra le notifiche per garantire che ogni utente veda solo le proprie:
1. Controlla `user_id` nel content della notifica
2. Se assente, controlla `integration_id` e verifica che l'integrazione appartenga all'utente
3. Usa euristiche per integrazioni senza `user_id` (backward compatibility)

### 8.3 Performance

**Prima**:
- Query O(n) per filtraggio notifiche
- Polling ogni 10 secondi sempre attivo
- Nessun indice ottimizzato

**Dopo**:
- Query O(1) con pre-caricamento
- SSE quando popup aperto (più efficiente)
- Indici compositi per query comuni
- Paginazione per ridurre carico

---

## 9. Riferimenti

- [Architettura Proattività](./PROACTIVITY_ARCHITECTURE.md)
- [Implementazione Proattività](./PROACTIVITY_IMPLEMENTATION.md)
- [Roadmap](./ROADMAP.md)

