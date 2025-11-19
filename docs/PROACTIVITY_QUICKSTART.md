# 🚀 Guida Rapida: Sistema Proattività in Azione

Questa guida ti mostra come vedere il sistema di proattività funzionare in tempo reale.

## 📋 Prerequisiti

- Backend in esecuzione
- Frontend in esecuzione
- PostgreSQL in esecuzione
- Account Google (per Gmail e Calendar)

---

## 🔧 Passo 1: Avviare i Servizi

```bash
# Dalla root del progetto
./scripts/start.sh

# Oppure manualmente:
# 1. Avvia PostgreSQL e ChromaDB
docker-compose up -d

# 2. Avvia backend
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# 3. Avvia frontend (in un altro terminale)
cd frontend
npm run dev
```

Verifica che tutto sia in esecuzione:
- Backend: http://localhost:8000/health
- Frontend: http://localhost:3003
- PostgreSQL: `docker-compose ps postgres`

---

## 🔐 Passo 2: Configurare Google OAuth

### 2.1 Crea Credenziali OAuth su Google Cloud

1. Vai su https://console.cloud.google.com/
2. Crea/Seleziona un progetto
3. Vai su **APIs & Services** > **Library**
4. Abilita:
   - ✅ **Gmail API**
   - ✅ **Google Calendar API**
5. Vai su **APIs & Services** > **Credentials**
6. Clicca **Create Credentials** > **OAuth client ID**
7. Tipo: **Web application**
8. Authorized redirect URIs:
   - `http://localhost:8000/api/integrations/emails/oauth/callback`
   - `http://localhost:8000/api/integrations/calendars/oauth/callback`
9. Copia **Client ID** e **Client Secret**

### 2.2 Configurare nel Backend

Crea/modifica `.env` nella root del progetto:

```env
# Google OAuth
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here

# Encryption key (usa una chiave sicura di 32 caratteri)
CREDENTIALS_ENCRYPTION_KEY=your-32-byte-key-change-me-12345

# Proactivity settings (opzionali, già configurati di default)
EVENT_MONITOR_ENABLED=true
EVENT_MONITOR_POLL_INTERVAL_SECONDS=60
EMAIL_POLLER_ENABLED=true
CALENDAR_WATCHER_ENABLED=true
```

Riavvia il backend dopo aver modificato `.env`.

---

## 📧 Passo 3: Collegare Gmail

### Opzione A: Via Frontend (Raccomandato)

1. Apri http://localhost:3003
2. Accedi al sistema
3. Vai su **Integrations** (o `/integrations`)
4. Clicca **"Connect Gmail"** o **"Collega Gmail"**
5. Autorizza l'accesso a Gmail
6. Verifica che l'integrazione appaia come "Active"

### Opzione B: Via API

```bash
# 1. Ottieni authorization URL
curl http://localhost:8000/api/integrations/emails/oauth/authorize \
  -H "X-API-Key: your-api-key"

# 2. Apri l'URL nel browser e autorizza
# 3. Il callback salverà automaticamente l'integrazione
```

---

## 📅 Passo 4: Collegare Google Calendar

### Opzione A: Via Frontend (Raccomandato)

1. Nella pagina **Integrations**
2. Clicca **"Connect Google Calendar"** o **"Collega Calendar"**
3. Autorizza l'accesso a Google Calendar
4. Verifica che l'integrazione appaia come "Active"

### Opzione B: Via API

```bash
# 1. Ottieni authorization URL
curl http://localhost:8000/api/integrations/calendars/oauth/authorize \
  -H "X-API-Key: your-api-key"

# 2. Apri l'URL nel browser e autorizza
# 3. Il callback salverà automaticamente l'integrazione
```

---

## ✅ Passo 5: Verificare che il Sistema Funzioni

### 5.1 Verifica Log Backend

Nel terminale del backend, dovresti vedere ogni minuto:

```
INFO: Checking 1 Gmail integrations for new emails
INFO: Checking 1 Calendar integrations for upcoming events
```

Se ci sono nuove email o eventi:
```
INFO: 📧 Found 2 new email events
INFO: Created notification for new email from sender@example.com (priority: high)
INFO: 📅 Found 1 upcoming calendar events
INFO: Created notification for event 'Meeting' starting in 15 minutes
```

### 5.2 Test Manuale (Opzionale)

Puoi triggerare manualmente un check:

```bash
curl -X POST http://localhost:8000/api/notifications/check-events \
  -H "X-API-Key: your-api-key"
```

Risposta:
```json
{
  "message": "Event check completed",
  "notifications_created": 3
}
```

### 5.3 Verifica Notifiche nel Database

```bash
# Connettiti a PostgreSQL
docker-compose exec postgres psql -U knavigator -d knowledge_navigator

# Query notifiche
SELECT id, type, urgency, content, created_at 
FROM notifications 
WHERE type IN ('email_received', 'calendar_event_starting')
ORDER BY created_at DESC 
LIMIT 10;
```

---

## 🔔 Passo 6: Vedere le Notifiche nel Frontend

### 6.1 Apri una Sessione Chat

1. Vai su http://localhost:3003
2. Crea o apri una sessione chat
3. Guarda l'icona **campanella** 🔔 in alto a destra

### 6.2 Quando Appaiono le Notifiche

Le notifiche appaiono automaticamente quando:
- ✅ Arriva una nuova email (controllo ogni minuto)
- ✅ Un evento calendar sta per iniziare (15 min o 5 min prima)

### 6.3 Visualizzare le Notifiche

1. Clicca sull'icona **campanella** 🔔
2. Vedrai un popup allargato (500px) con tutte le notifiche pendenti
3. Le notifiche mostrano:
   - **Email**: Mittente, oggetto, snippet
   - **Calendar**: Titolo evento, tempo rimanente, location
4. Il popup include bottoni semplificati (testo + icona):
   - **Segna Lette**: marca tutte le notifiche come lette
   - **Pulisci**: elimina tutte le notifiche pendenti
   - **Vedi Tutte**: link alla pagina dedicata `/notifications`
5. Ogni notifica ha un pulsante **[X]** per eliminazione individuale

### 6.4 Tipi di Notifiche

#### Email Notifications
- **High priority**: Email con "URGENT", "ASAP", "IMPORTANT" nell'oggetto
- **Medium priority**: Email molto recente (< 5 minuti)
- **Low priority**: Email normali

#### Calendar Notifications
- **High priority**: Evento che inizia tra 5 minuti
- **Medium priority**: Evento che inizia tra 15 minuti

---

## 🧪 Test Pratico

### Test Email

1. Invia una email al tuo account Gmail collegato
2. Attendi ~1 minuto (polling interval)
3. Controlla le notifiche nel frontend
4. Dovresti vedere la nuova email nella lista

### Test Calendar

1. Crea un evento su Google Calendar che inizia tra 15 minuti
2. Attendi che il sistema lo rilevi (controllo ogni minuto)
3. Controlla le notifiche nel frontend
4. Dovresti vedere un reminder a 15 minuti prima
5. Quando mancano 5 minuti, vedrai un altro reminder (high priority)

---

## 🔍 Troubleshooting

### Le notifiche non appaiono

1. **Verifica che Event Monitor sia abilitato:**
   ```bash
   # Controlla i log del backend
   # Dovresti vedere: "✅ Event Monitor started"
   ```

2. **Verifica le integrazioni:**
   ```bash
   # Query database
   SELECT id, provider, service_type, enabled 
   FROM integrations 
   WHERE enabled = true;
   ```

3. **Verifica i log:**
   ```bash
   # Cerca errori nei log del backend
   grep -i "error\|warning" backend/logs/backend.log
   ```

4. **Test manuale:**
   ```bash
   curl -X POST http://localhost:8000/api/notifications/check-events \
     -H "X-API-Key: your-api-key"
   ```

### Le integrazioni non si collegano

1. Verifica che `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` siano nel `.env`
2. Verifica che le API siano abilitate su Google Cloud Console
3. Verifica che i redirect URI siano corretti
4. Controlla i log del backend per errori OAuth

### Il polling non funziona

1. Verifica che `EVENT_MONITOR_ENABLED=true` nel `.env`
2. Riavvia il backend dopo modifiche al `.env`
3. Controlla i log per errori di autenticazione

---

## 📊 Monitoraggio

### Log Backend

Il sistema logga tutte le operazioni:

```
INFO: Checking 2 Gmail integrations for new emails
INFO: 📧 Found 3 new email events
INFO: Created notification for new email from sender@example.com (priority: high)
INFO: Checking 1 Calendar integrations for upcoming events
INFO: 📅 Found 2 upcoming calendar events
```

### Endpoint API Utili

```bash
# Verifica notifiche
GET /api/notifications?read=false

# Trigger manuale check
POST /api/notifications/check-events

# Verifica integrazioni
GET /api/integrations
```

---

## 🎯 Prossimi Passi

Una volta che il sistema funziona:

1. **Personalizza i filtri**: Modifica le priorità email nel codice
2. **Aggiungi più integrazioni**: Collega più account Gmail/Calendar
3. **Configura quiet hours**: (da implementare) Non disturbare in certi orari
4. **WebSocket real-time**: (da implementare) Notifiche push immediate

---

## 📚 Riferimenti

- [Documentazione Implementazione](PROACTIVITY_IMPLEMENTATION.md)
- [Setup Google Calendar](SETUP_GOOGLE_CALENDAR.md)
- [Setup Integrazioni](INTEGRATION_SETUP.md)

