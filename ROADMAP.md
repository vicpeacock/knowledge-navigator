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
- ✅ Upload e gestione file (PDF, DOCX, XLSX, TXT)
- ✅ Sistema memoria multi-livello (short/medium/long-term)
- ✅ RAG con ChromaDB per ricerca semantica
- ✅ Tool calling dinamico (LLM decide quando usare tool)
- ✅ Archiviazione chat con indicizzazione semantica
- ✅ Title e description per ogni chat
- ✅ Home page con solo chat attive
- ✅ Toggle "Web Search" per forzare ricerca web (come Ollama desktop)
- ✅ Status panel globale per notifiche non bloccanti

### 🚧 In Progress / Da Completare

**Navigazione Web (Fase 1 - ✅ Completa):**
- ✅ Integrazione MCP Gateway (funzionante)
- ✅ Tool browser Playwright (navigate, snapshot, click, evaluate, ecc.)
- ✅ Ricerca web Ollama (web_search, web_fetch) con API ufficiale
- ✅ Cleanup automatico container Playwright
- ✅ Indicizzazione contenuti web visitati in memoria (long-term)
- ✅ Toggle "Web Search" (force_web_search) - forzare ricerca web come in Ollama desktop
- ✅ Test suite completa per indicizzazione web (9/9 test passati)
- ❌ Navigazione autonoma web avanzata (Fase 3)

**Proattività (Fase 2 - Non iniziata):**
- ❌ Sistema eventi per monitorare email/calendario/WhatsApp
- ❌ WebSocket per notifiche real-time
- ❌ Motore decisionale per priorità eventi
- ❌ Notifiche push frontend

**WhatsApp Integration (Fase 1 - ⏸️ Temporaneamente Disabilitata):**
- ⏸️ Integrazione WhatsApp (Selenium + pywhatkit) - DISABILITATA
- ⏸️ Lettura messaggi - DISABILITATA
- ⏸️ Integrazione nelle risposte (tool get_whatsapp_messages) - DISABILITATA
- ⏸️ Invio messaggi - DISABILITATA
- 📝 **Nota**: L'integrazione WhatsApp è stata temporaneamente disabilitata a causa di problemi con l'estrazione delle date. Sarà riabilitata in futuro utilizzando WhatsApp Business API invece di Selenium/Web scraping.

**Miglioramenti Memoria (Fase 2):**
- ✅ Indicizzazione email in memoria (completata in Fase 1)
- ✅ Indicizzazione contenuti web in memoria (completata in Fase 1)
- ✅ Test suite completa per indicizzazione email (10/10 test passati)
- ✅ Test suite completa per indicizzazione web (9/9 test passati)
- ❌ Auto-apprendimento migliorato da interazioni

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

**WhatsApp** ⏸️ Temporaneamente Disabilitata
- [x] Setup integrazione WhatsApp (Selenium/Web scraping - problemi con date extraction)
- [ ] **Pianificato**: Riimplementazione con WhatsApp Business API
- [ ] **Pianificato**: Lettura messaggi con Business API
- [ ] **Pianificato**: Integrazione nelle risposte (tool get_whatsapp_messages)

---

### Fase 2 - Proattività (3-4 settimane)

**Sistema Eventi:**
- [ ] Event Monitor Service
- [ ] Email Poller (controllo nuove email)
- [ ] Calendar Watcher (eventi imminenti)
- [ ] WhatsApp Monitor (messaggi in arrivo)

**WebSocket & Notifiche:**
- [ ] WebSocket server (FastAPI)
- [ ] Client WebSocket frontend
- [ ] Sistema notifiche real-time
- [ ] Priorità eventi (LOW, MEDIUM, HIGH, URGENT)

**Motore Decisionale:**
- [ ] Valutazione importanza eventi
- [ ] Configurazione utente per filtri
- [ ] Decisioni su quando interrompere utente

---

### Fase 3 - Advanced Features (4-6 settimane)

**Memoria Avanzata:**
- [ ] Auto-apprendimento migliorato
- [ ] Indicizzazione automatica email importanti
- [ ] Indicizzazione automatica contenuti web
- [ ] Sintesi e consolidamento memoria

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
- [ ] Notifiche push browser
- [ ] Dashboard avanzato con statistiche
- [ ] Export/Import sessioni
- [ ] Temi personalizzabili

---

### Fase 4 - Production Ready (2-3 settimane)

**Sicurezza:**
- [ ] Autenticazione utente
- [ ] Cifratura end-to-end (opzionale)
- [ ] Audit log
- [ ] Backup automatico

**Performance:**
- [ ] Ottimizzazione query database
- [ ] Caching intelligente
- [ ] Background jobs per indicizzazione
- [ ] Rate limiting API

**Deployment:**
- [ ] Docker compose completo
- [ ] Configurazione produzione
- [ ] Monitoring e logging
- [ ] Documentazione API completa

---

## 🎯 Prossimi Passi Suggeriti

**Opzione 1: Completare Fase 1** ✅ (Quasi completa)
- ✅ Navigazione web avanzata
- ✅ Indicizzazione email in memoria
- ✅ Indicizzazione contenuti web in memoria
- ✅ Toggle Web Search
- ⏸️ WhatsApp integration (pianificata con Business API)

**Opzione 2: Iniziare Fase 2** (Raccomandato)
- Sistema eventi
- WebSocket per proattività
- Notifiche real-time
- Monitoraggio email/calendario

**Opzione 3: Miglioramenti Core**
- Auto-apprendimento memoria
- Ricerca semantica avanzata
- UI/UX improvements
- Export/Import sessioni

## 📊 Statistiche Attuali

- **Test Coverage**: 19/19 test passati (100%)
  - Web Indexer: 9/9 ✅
  - Email Indexer: 10/10 ✅
- **Fase 1 Completamento**: ~95% (manca solo WhatsApp con Business API)
- **Code Quality**: Nessun warning, Pydantic V2 compatibile

Quale fase vuoi affrontare per prima?

