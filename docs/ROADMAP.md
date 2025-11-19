# Knowledge Navigator - Roadmap

## 📊 Stato Attuale

### ✅ Completato - Fase 1: Core Integrations (parziale)

**Calendario Integration:**
- ✅ OAuth2 con Google Calendar
- ✅ Lettura eventi con query in linguaggio naturale
- ✅ Tool calling automatico per query calendario
- ✅ Parsing date naturali (domani, questa settimana, ecc.)

**Email Integration:**
- ✅ OAuth2 con Gmail
- ✅ Lettura email con filtri (unread, by sender, ecc.)
- ✅ Riassunto automatico email non lette
- ✅ Tool calling automatico per query email

**Core Features:**
- ✅ Sistema multi-sessione con chat indipendenti
- ✅ **Sistema sessioni giornaliere** - Una sessione per giorno con archiviazione automatica
- ✅ **Transizione di giorno** - Dialog per confermare passaggio a nuovo giorno
- ✅ Upload e gestione file (PDF, DOCX, XLSX, TXT)
- ✅ Sistema memoria multi-livello (short/medium/long-term)
- ✅ **Gestione memoria a lungo termine** - Pagina dedicata con cancellazione batch
- ✅ RAG con ChromaDB per ricerca semantica
- ✅ **LangGraph refactoring completo** - Tutti i nodi eseguono correttamente, fallback multipli per risposte vuote
- ✅ Tool calling dinamico (LLM decide quando usare tool) - Descrizioni funzionali senza euristiche hardcoded
- ✅ Archiviazione chat con indicizzazione semantica
- ✅ Title e description per ogni chat
- ✅ Home page con solo chat attive
- ✅ Toggle "Web Search" per forzare ricerca web (come Ollama desktop)
- ✅ Status panel globale per notifiche non bloccanti
- ✅ Sistema multi-tenant completo con isolamento dati
- ✅ Gestione utenti con autenticazione JWT
- ✅ Admin panel per gestione utenti
- ✅ Preferenze tools MCP per utente
- ✅ **Timezone utente** - Configurazione timezone per sessioni giornaliere

### 🚧 In Progress / Da Completare

**User Management & Multi-Tenancy (✅ Completo):**
- ✅ Sistema multi-tenant con isolamento dati completo
- ✅ Autenticazione JWT con refresh tokens
- ✅ Gestione utenti (creazione, modifica, attivazione/disattivazione)
- ✅ Admin panel per gestione utenti
- ✅ Email verification e password reset
- ✅ Ruoli utente (admin, user, viewer)
- ✅ Isolamento dati per utente (sessioni, integrazioni Calendar/Email)
- ✅ Preferenze tools MCP per utente
- ✅ UI semplificata per utenti normali (solo "Manage Tools" per MCP)
- ✅ Integrazioni Calendar/Email per utente

**Navigazione Web (Fase 1 - ✅ Completa):**
- ✅ Integrazione MCP Gateway (funzionante)
- ✅ Tool browser Playwright (navigate, snapshot, click, evaluate, ecc.)
- ✅ Ricerca web Ollama (web_search, web_fetch) con API ufficiale
- ✅ Cleanup automatico container Playwright
- ✅ Indicizzazione contenuti web visitati in memoria (long-term)
- ✅ Toggle "Web Search" (force_web_search) - forzare ricerca web come in Ollama desktop
- ✅ Test suite completa per indicizzazione web (9/9 test passati)
- ✅ Preferenze tools MCP per utente (selezione tools personalizzata)
- ❌ Navigazione autonoma web avanzata (Fase 3)

**Proattività (Fase 2 - ✅ Completata):**
- ✅ Sistema eventi per monitorare email/calendario (implementato)
- ✅ Email Poller - rileva automaticamente nuove email
- ✅ Calendar Watcher - rileva eventi imminenti (15min, 5min prima)
- ✅ Event Monitor Service - orchestratore principale
- ✅ Integrazione con sistema notifiche esistente
- ✅ **SSE per notifiche real-time** - Server-Sent Events per aggiornamenti immediati
- ✅ **Pagina dedicata notifiche** - `/notifications` con filtri, paginazione, cancellazione batch
- ✅ **Ottimizzazioni notifiche** - Indici database, query O(1), pre-caricamento integrazioni
- ✅ **UI migliorata NotificationBell** - Raggruppamento per tipo, pulsanti "Segna Lette" e "Vedi Tutte"
- ❌ WebSocket per notifiche bidirezionali (opzionale, SSE sufficiente)
- ❌ Motore decisionale avanzato per priorità eventi
- ❌ Notifiche push browser

**WhatsApp Integration (Fase 1 - ⏸️ Temporaneamente Disabilitata):**
- ⏹️ Integrazione WhatsApp (Selenium + pywhatkit) **rimossa** dalla codebase
- 📝 **Nota**: ripartiremo da zero con l'implementazione basata su WhatsApp Business API; nessun supporto WhatsApp è disponibile fino a quel refactoring.

**Miglioramenti Memoria (Fase 2 - ✅ Completata):**
- ✅ Indicizzazione email in memoria (completata in Fase 1)
- ✅ Indicizzazione contenuti web in memoria (completata in Fase 1)
- ✅ Test suite completa per indicizzazione email (10/10 test passati)
- ✅ Test suite completa per indicizzazione web (9/9 test passati)
- ✅ Auto-apprendimento da conversazioni (ConversationLearner)
- ✅ Ricerca semantica avanzata (hybrid search, query suggestions)
- ✅ Consolidamento memoria (duplicati, riassunti)
- ✅ Riassunto automatico conversazioni lunghe in memoria medium-term
- ✅ **Gestione memoria a lungo termine** - Pagina dedicata con lista, filtri, cancellazione batch
- ✅ **Riassunto sessioni giornaliere** - Archiviazione automatica con riassunto in memoria long-term
- ❌ **Controllo integrità semantica**: Identificare contraddizioni nella memoria long-term (es: "nato il 12 luglio" vs "compleanno 15 agosto")

---

## 📋 Roadmap Dettagliata

### Fase 1 - Core Integrations (2-3 settimane) - ✅ 100% Completa

**Calendario** ✅
- [x] Lettura eventi
- [x] Query naturali
- [x] Tool calling automatico

**Email** ✅
- [x] Lettura email
- [x] Riassunti automatici
- [x] Indicizzazione email in memoria (long-term)

**Navigazione Web** ✅
- [x] Integrazione MCP Gateway e tool browser Playwright
- [x] Ricerca web Ollama (web_search, web_fetch)
- [x] Integrazione ricerca web nelle risposte chatbot
- [x] Indicizzazione contenuti web visitati in memoria (long-term)
- [x] Toggle "Web Search" (force_web_search) - UI e API per forzare ricerca web
- [x] Test suite completa per indicizzazione web (9/9 test passati)

**WhatsApp** ⏹️ In attesa di nuova implementazione
- [x] Rimozione integrazione Selenium/Web scraping
- [ ] **Pianificato**: Implementazione con WhatsApp Business API
- [ ] **Pianificato**: Lettura messaggi con Business API
- [ ] **Pianificato**: Integrazione nelle risposte (tool get_whatsapp_messages)

---

### Fase 2 - Proattività (3-4 settimane) - 🚧 In Corso

**Sistema Eventi:**
- [x] Event Monitor Service ✅ (implementato e integrato nel backend)
- [x] Email Poller (controllo nuove email) ✅ (implementato)
- [x] Calendar Watcher (eventi imminenti) ✅ (implementato con reminder 15min e 5min)
- [x] Integrazione con NotificationService ✅ (notifiche create automaticamente)
- [x] Endpoint API per test manuale ✅ (`POST /api/notifications/check-events`)
- [ ] WhatsApp Monitor (messaggi in arrivo) - In attesa Business API

**WebSocket & Notifiche:**
- [x] **SSE per notifiche real-time** ✅ (Server-Sent Events implementato)
- [x] **Pagina dedicata notifiche** ✅ (`/notifications` con filtri e paginazione)
- [x] **Ottimizzazioni database** ✅ (indici compositi, query O(1))
- [x] **UI migliorata NotificationBell** ✅ (raggruppamento, nuovi pulsanti)
- [ ] WebSocket server (opzionale, SSE sufficiente per notifiche unidirezionali)
- [ ] Priorità eventi avanzata (LOW, MEDIUM, HIGH, URGENT) - base implementata

**Motore Decisionale:**
- [ ] Valutazione importanza eventi
- [ ] Configurazione utente per filtri
- [ ] Decisioni su quando interrompere utente

---

### Fase 3 - Advanced Features (4-6 settimane)

**Memoria Avanzata:**
- [x] Auto-apprendimento da conversazioni (ConversationLearner)
- [x] Indicizzazione automatica email importanti
- [x] Indicizzazione automatica contenuti web
- [x] Sintesi e consolidamento memoria (MemoryConsolidator)
- [x] Riassunto automatico conversazioni lunghe in memoria medium-term (ConversationSummarizer)
- [x] **Controllo integrità semantica**: Sistema per identificare contraddizioni nella memoria long-term (Implementato - da migliorare)
  - [x] Rilevamento contraddizioni su date/eventi (es: "nato il 12 luglio" vs "compleanno 15 agosto")
  - [x] Rilevamento contraddizioni su preferenze/fatti personali
  - [x] Notifica all'utente quando viene rilevata una contraddizione (notification bell)
  - [x] Suggerimento di correzione o chiarimento
  - [ ] **TODO - Miglioramenti Rilevamento Contraddizioni**:
    - [ ] Migliorare estrazione conoscenza: distinguere meglio tra affermazioni casuali e preferenze esplicite
    - [ ] Rendere prompt analisi contraddizioni più conservativo (enfatizzare che preferenze diverse in contesti diversi NON sono contraddizioni)
    - [ ] Aumentare soglia confidenza da 0.85 a 0.90-0.95
    - [ ] Aggiungere filtri pre-analisi: non confrontare tipi diversi di conoscenza (fatti temporanei vs preferenze permanenti)
    - [ ] Implementare pulizia periodica memoria: rimuovere duplicati, memorie obsolete, consolidare memorie simili
    - [ ] Aggiungere contesto temporale: distinguere tra fatti temporanei ("oggi ho fatto X") e preferenze permanenti
    - [ ] Ridurre enfasi su contraddizioni tassonomiche nel prompt LLM (essere più conservativo)

**Ricerca e Discovery:**
- [ ] Ricerca cross-sessione
- [ ] Ricerca semantica avanzata
- [ ] Suggerimenti basati su contesto
- [ ] Knowledge graph (opzionale)

**Integrazione Avanzata:**
- [ ] Apple Calendar (CalDAV)
- [ ] Microsoft Outlook (Graph API)
- [ ] iCloud Mail (IMAP)
- [ ] Outlook Mail (Graph API)

**UI/UX:**
- [x] **Pagina dedicata notifiche** ✅ (`/notifications` con filtri avanzati)
- [x] **Gestione memoria a lungo termine** ✅ (pagina dedicata con cancellazione batch)
- [x] **Dialog transizione giorno** ✅ (conferma utente per nuovo giorno)
- [x] **UI semplificata notifiche** ✅ (bottoni testo + icona, popup allargato)
- [x] **Gestione timezone nel Profile** ✅ (selezione timezone nella pagina Profile)
- [x] **Navigazione semplificata** ✅ (rimossi bottoni duplicati da SessionList)
- [ ] Notifiche push browser
- [ ] Dashboard avanzato con statistiche
- [ ] Export/Import sessioni
- [ ] Temi personalizzabili

---

### Fase 4 - Production Ready (2-3 settimane)

**Sicurezza:**
- [x] Autenticazione utente (JWT con refresh tokens)
- [x] Isolamento dati multi-tenant
- [x] Isolamento dati per utente
- [x] Password hashing (bcrypt)
- [x] Email verification
- [x] Password reset
- [ ] Cifratura end-to-end (opzionale)
- [ ] Audit log
- [ ] Backup automatico

**Performance:**
- [x] **Ottimizzazione query database** ✅ (indici compositi per notifiche, query O(1) invece di O(n))
- [x] **Ottimizzazione filtraggio notifiche** ✅ (pre-caricamento integrazioni, batch loading)
- [x] **Paginazione** ✅ (notifiche e memoria a lungo termine)
- [ ] Caching intelligente (opzionale)
- [ ] Background jobs per indicizzazione (parzialmente implementato)
- [ ] Rate limiting API

**Deployment:**
- [ ] Docker compose completo
- [ ] Configurazione produzione
- [ ] Monitoring e logging
- [ ] Documentazione API completa

---

### Fase 5 - Kaggle Challenge Submission (3-4 settimane) - 🎯 In Corso

**Preparazione per Agents Intensive Capstone Project** (Scadenza: 1 Dicembre 2025)

**Observability:**
- [x] Tracing implementation (OpenTelemetry) ✅
- [x] Metrics collection e dashboard ✅
- [x] Logging avanzato ✅

**Agent Evaluation:**
- [x] Evaluation framework ✅
- [x] Test cases per scenari comuni ✅
- [x] Report generation ✅

**Deployment:**
- [x] Cloud Run deployment preparation (Dockerfiles, scripts, docs) ✅
- [ ] Cloud Run deployment effettivo (richiede GCP setup)
- [ ] Database setup su cloud

**Gemini Support (Opzionale):**
- [ ] Integrazione Gemini API
- [ ] Supporto multi-LLM (Ollama/Gemini)

**Video & Submission:**
- [ ] Video dimostrativo <3 min
- [ ] Writeup completo
- [ ] Final submission su Kaggle

📋 **Roadmap dettagliata**: Vedi `docs/KAGGLE_SUBMISSION_ROADMAP.md`

---

## 🎯 Prossimi Passi Suggeriti

**Opzione 1: Kaggle Challenge Submission** 🎯 (Priorità Alta - Scadenza 1 Dic)
- Observability (tracing, metrics)
- Agent Evaluation system
- Cloud Run deployment
- Video dimostrativo
- Writeup finale

**Opzione 2: Completare Fase 1** ✅ (Quasi completa)
- ✅ Navigazione web avanzata
- ✅ Indicizzazione email in memoria
- ✅ Indicizzazione contenuti web in memoria
- ✅ Toggle Web Search
- ⏸️ WhatsApp integration (pianificata con Business API)

**Opzione 3: Iniziare Fase 2** (Dopo Kaggle)
- Sistema eventi
- WebSocket per proattività
- Notifiche real-time
- Monitoraggio email/calendario

**Opzione 4: Miglioramenti Core**
- Auto-apprendimento memoria
- Ricerca semantica avanzata
- UI/UX improvements
- Export/Import sessioni

## 📊 Statistiche Attuali

- **Test Coverage**: 19/19 test passati (100%)
  - Web Indexer: 9/9 ✅
  - Email Indexer: 10/10 ✅
  - Daily Session Integration: 4/4 ✅
  - Day Transition API: 2/2 ✅
  - DayTransitionDialog Frontend: 6/6 ✅
- **Fase 1 Completamento**: ~95% (manca solo WhatsApp con Business API)
- **Fase 2 Completamento**: ~90% (completati sistema eventi, notifiche real-time, UI)
- **Code Quality**: Nessun warning, Pydantic V2 compatibile

## 📚 Documentazione Recente

- **`docs/DAILY_SESSIONS_AND_NOTIFICATIONS.md`** - Documentazione completa sistema sessioni giornaliere e miglioramenti notifiche

Quale fase vuoi affrontare per prima?

