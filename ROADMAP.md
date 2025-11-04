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

### 🚧 In Progress / Da Completare

**Navigazione Web (Fase 1 - Incompleta):**
- ⚠️ Integrazione MCP Gateway parziale
- ❌ Ricerca web avanzata e indicizzazione
- ❌ Navigazione autonoma web
- ❌ Estrazione e indicizzazione contenuti web visitati

**Proattività (Fase 2 - Non iniziata):**
- ❌ Sistema eventi per monitorare email/calendario/WhatsApp
- ❌ WebSocket per notifiche real-time
- ❌ Motore decisionale per priorità eventi
- ❌ Notifiche push frontend

**WhatsApp Integration (Fase 1 - Non iniziata):**
- ❌ Integrazione WhatsApp (whatsapp-web.py o alternativa)
- ❌ Lettura messaggi
- ❌ Invio messaggi (opzionale)

**Miglioramenti Memoria (Fase 2):**
- ❌ Indicizzazione email in memoria
- ❌ Indicizzazione contenuti web in memoria
- ❌ Auto-apprendimento migliorato da interazioni

---

## 📋 Roadmap Dettagliata

### Fase 1 - Core Integrations (2-3 settimane) - 70% Completa

**Calendario** ✅
- [x] Lettura eventi
- [x] Query naturali
- [x] Tool calling automatico

**Email** ✅
- [x] Lettura email
- [x] Riassunti automatici
- [ ] Indicizzazione email in memoria

**Navigazione Web** ⚠️
- [ ] Ricerca web avanzata con MCP gateway
- [ ] Indicizzazione contenuti web visitati
- [ ] Integrazione ricerca web nelle risposte chatbot

**WhatsApp** ❌
- [ ] Setup integrazione WhatsApp
- [ ] Lettura messaggi
- [ ] Integrazione nelle risposte

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

**Opzione 1: Completare Fase 1**
- Navigazione web avanzata
- Indicizzazione email in memoria
- WhatsApp integration

**Opzione 2: Iniziare Fase 2**
- Sistema eventi
- WebSocket per proattività
- Notifiche real-time

**Opzione 3: Miglioramenti Core**
- Auto-apprendimento memoria
- Ricerca semantica avanzata
- UI/UX improvements

Quale fase vuoi affrontare per prima?

