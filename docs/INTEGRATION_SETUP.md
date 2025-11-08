# Setup Integrazioni - Knowledge Navigator

## Google Calendar Setup

### 1. Creare OAuth2 Credentials su Google Cloud Console

1. Vai su https://console.cloud.google.com/
2. Crea un nuovo progetto o seleziona uno esistente
3. Vai su **APIs & Services** > **Credentials**
4. Clicca **Create Credentials** > **OAuth client ID**
5. Se richiesto, configura l'OAuth consent screen
6. Tipo: **Web application**
7. Authorized redirect URIs: `http://localhost:8000/api/integrations/calendars/oauth/callback`
8. Copia **Client ID** e **Client Secret**

### 2. Configurare nel Backend

Aggiungi al file `.env` nella root del progetto:

```env
GOOGLE_CLIENT_ID=your_client_id_here
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8000/api/integrations/calendars/oauth/callback
CREDENTIALS_ENCRYPTION_KEY=your-32-byte-key-here-change-me
```

### 3. Abilitare Google Calendar API

1. Vai su **APIs & Services** > **Library**
2. Cerca "Google Calendar API"
3. Clicca **Enable**

### 4. Collegare il Calendario

**Opzione A - Via API (raccomandato):**

```bash
# 1. Inizia OAuth flow
curl http://localhost:8000/api/integrations/calendars/oauth/authorize

# 2. Apri l'URL nel browser, autorizza, e otterrai un code
# 3. Il callback salverà automaticamente l'integrazione
```

**Opzione B - Via Frontend (da implementare):**
- Aggiungere UI per setup integrazioni
- Bottone "Connetti Google Calendar" che apre OAuth flow

### 5. Test Query Naturali

Una volta collegato, puoi chiedere al chatbot:
- "Ho eventi domani?"
- "Quali meeting ho questa settimana?"
- "Mostrami il calendario per il prossimo mese"
- "Ho appuntamenti oggi?"

Il sistema:
1. Rileva keyword del calendario nella query
2. Estrae date dalla query naturale (es: "domani" → domani 00:00 - 23:59)
3. Recupera eventi da Google Calendar
4. Aggiunge gli eventi al context del LLM
5. LLM risponde con le informazioni sul calendario

## Endpoint API Disponibili

### Calendario

- `GET /api/integrations/calendars/oauth/authorize` - Inizia OAuth flow
- `GET /api/integrations/calendars/oauth/callback` - Callback OAuth (chiamato da Google)
- `GET /api/integrations/calendars/events` - Ottieni eventi (con parametri start_time, end_time)
- `POST /api/integrations/calendars/query` - Query naturale (es: {"query": "eventi domani"})
- `GET /api/integrations/calendars/integrations` - Lista integrazioni configurate

## Esempi

### Query Eventi con Date Specifiche

```bash
curl -X GET "http://localhost:8000/api/integrations/calendars/events?provider=google&start_time=2024-01-01T00:00:00Z&end_time=2024-01-31T23:59:59Z"
```

### Query Naturale

```bash
curl -X POST "http://localhost:8000/api/integrations/calendars/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "eventi domani", "provider": "google"}'
```

## Note

- Le credenziali sono criptate nel database usando Fernet
- Il token viene rinfrescato automaticamente se scaduto
- Supporto per multipli calendar (primary, altri calendari Google)
- Parsing date supporta italiano e inglese

