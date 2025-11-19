# Changelog

## [Unreleased] - Novembre 2025

### ✨ Aggiunte

#### Sistema Sessioni Giornaliere
- Implementato sistema di sessioni giornaliere con una sessione per giorno per utente
- Archiviazione automatica delle sessioni con riassunto in memoria a lungo termine
- Dialog di conferma per transizione di giorno (`DayTransitionDialog`)
- Supporto timezone personalizzato per utenti
- Script `create_today_session.py` per creare sessioni giornaliere
- Script `cleanup_sessions_and_memory.py` per pulizia sessioni e memoria

#### Gestione Profilo Utente
- Endpoint `GET /api/v1/users/me` per ottenere il profilo corrente
- Endpoint `PUT /api/v1/users/me` per aggiornare nome e timezone
- Sezione "Profile Settings" nella pagina Profile con selezione timezone
- Lista di 17 timezone comuni disponibili per selezione

#### Gestione Memoria a Lungo Termine
- Pagina dedicata `/memory` con tab "Gestione Memoria" e "Ricerca Memoria"
- Componente `LongTermMemoryManager` con lista completa memorie
- Cancellazione batch con checkboxes
- Paginazione per gestione grandi volumi di dati
- Endpoint API `GET /api/memory/long/list` e `POST /api/memory/long/batch/delete`

#### Miglioramenti Sistema Notifiche
- Server-Sent Events (SSE) per notifiche real-time (`GET /api/notifications/stream`)
- Pagina dedicata `/notifications` con filtri avanzati (urgenza, tipo, stato)
- Ottimizzazioni database con indici compositi
- Query ottimizzate: da O(n) a O(1) per filtraggio notifiche
- Pre-caricamento integrazioni invece di query per notifica
- UI migliorata `NotificationBell` con raggruppamento per tipo
- Nuovi pulsanti: "Segna Lette", "Pulisci", "Vedi Tutte"
- Cancellazione batch notifiche
- Bottoni semplificati: solo testo + icona (senza gradienti o effetti)
- Popup allargato da 384px a 500px per evitare sovrapposizioni

#### Miglioramenti Email
- Tool `archive_email` per archiviare email
- Tool `send_email` per inviare email
- Tool `reply_to_email` per rispondere a email
- Migliorata gestione errori con messaggi user-friendly
- Rilevamento automatico risposte a email inviate dall'assistente

### 🔧 Miglioramenti

- Ottimizzazione query database per notifiche (indici compositi)
- Paginazione per notifiche e memoria a lungo termine
- Migliorata deduplicazione email basata su `integration_id`
- Gestione corretta sessioni cancellate/archiviate
- Migliorata gestione OAuth per integrazioni Google
- Rimossi bottoni "Integrazioni" e "Memoria" da SessionList (ora solo nel menu principale)
- UI semplificata: bottoni notifiche con solo testo + icona
- Popup notifiche allargato per migliore usabilità
- Migliorata gestione errori nel Profile (gestione corretta errori Pydantic)

### 🐛 Bug Fixes

- Fix errore `ReferenceError: router is not defined` in `NotificationBell`
- Fix autenticazione endpoint OAuth callback (rimosso `get_current_user` per redirect Google)
- Fix deduplicazione notifiche per integrazione
- Fix aggiornamento notifiche quando viene creata nuova sessione
- Fix gestione sessioni cancellate nella deduplicazione email
- Fix import `html2pdf.js` nella pagina metrics (dynamic import per SSR)
- Fix routing FastAPI: endpoint `/me` spostato prima di `/{user_id}` per evitare conflitti UUID
- Fix telemetria: `service_health_agent` ora usa `publish_to_all_active_sessions()` invece di UUID nullo
- Fix gestione errori Profile: corretta visualizzazione errori Pydantic (array di oggetti)
- Migliorato stack trace logging per debug telemetria

### 📚 Documentazione

- Creato `docs/DAILY_SESSIONS_AND_NOTIFICATIONS.md` con documentazione completa
- Aggiornata `docs/ROADMAP.md` con nuove funzionalità
- Aggiornato `README.md` con funzionalità principali e statistiche

### 🧪 Testing

- Test integrazione sessioni giornaliere (`test_daily_session_integration.py`)
- Test transizione giorno (`test_day_transition_api.py`)
- Test frontend `DayTransitionDialog` (6/6 test passati)

### 🗄️ Database

- Migration: `4d2ea1f98574_add_user_timezone_and_inactivity_timeout.py`
- Migration: `add_notification_indexes.py` (indici compositi per performance)

---

## Versioni Precedenti

Vedi git log per storico completo delle modifiche.

