# Testing Checklist - Post Deployment Cloud Run

## 🧪 Test Necessari Dopo Deployment

### Test Base (Critici) ✅

#### 1. Health Checks
- [ ] `GET /health` - Backend health check
- [ ] Verifica che tutti i servizi siano healthy (PostgreSQL, ChromaDB Cloud)

#### 2. Authentication
- [ ] `POST /api/v1/auth/register` - Registrazione utente
- [ ] `POST /api/v1/auth/login` - Login utente
- [ ] `POST /api/v1/auth/refresh` - Refresh token
- [ ] `GET /api/v1/users/me` - Profilo utente

#### 3. Sessioni
- [ ] `GET /api/sessions` - Lista sessioni
- [ ] `POST /api/sessions` - Creazione sessione
- [ ] `GET /api/sessions/{id}` - Dettagli sessione

#### 4. Chat
- [ ] `POST /api/chat` - Invio messaggio
- [ ] Verifica risposta LLM (Gemini)
- [ ] Verifica tool calling (se necessario)

#### 5. Memoria
- [ ] `GET /api/memory/long/list` - Lista memoria long-term
- [ ] Verifica che ChromaDB Cloud funzioni
- [ ] Test aggiunta memoria
- [ ] Test query memoria

### Test Avanzati (Opzionali)

#### 6. Integrazioni
- [ ] Gmail OAuth callback (se configurato)
- [ ] Calendar OAuth callback (se configurato)
- [ ] Test lettura email
- [ ] Test lettura eventi calendario

#### 7. Tools
- [ ] `customsearch_search` - Web search
- [ ] Verifica che Google Custom Search funzioni

#### 8. Notifiche
- [ ] `GET /api/notifications/stream` - SSE stream
- [ ] `GET /api/notifications` - Lista notifiche

---

## 🚀 Test Rapido Post-Deployment

### Script di Test Rapido

```bash
# Dopo deployment, esegui questi test:

# 1. Health check
curl https://your-backend.run.app/health

# 2. Registrazione
curl -X POST https://your-backend.run.app/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123","name":"Test User"}'

# 3. Login
curl -X POST https://your-backend.run.app/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'

# 4. Chat (con token)
curl -X POST https://your-backend.run.app/api/chat \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message":"Ciao, come stai?","session_id":"SESSION_ID"}'
```

---

## ✅ Test Già Completati (Locali)

- ✅ ChromaDB Cloud connection
- ✅ MemoryManager con CloudClient
- ✅ Database Supabase connection
- ✅ Gemini API integration
- ✅ Security keys generation
- ✅ Configurazione completa

---

## 📝 Note

I test locali hanno verificato che:
- ChromaDB Cloud funziona correttamente
- MemoryManager integra CloudClient
- Database Supabase è accessibile
- Tutte le configurazioni sono corrette

I test post-deployment verificheranno:
- Che tutto funzioni su Cloud Run
- Che le connessioni esterne funzionino
- Che l'app sia accessibile pubblicamente

---

**Raccomandazione**: I test locali sono sufficienti. I test post-deployment sono per verifica finale.

**Ultimo aggiornamento**: 2025-11-22

