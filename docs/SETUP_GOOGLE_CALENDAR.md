# Guida Completa: Setup Google Calendar

Questa guida ti accompagna passo-passo per configurare Google Calendar nel Knowledge Navigator.

## 📋 Prerequisiti

- Un account Google
- Accesso a Google Cloud Console (gratuito)

---

## 🚀 Passo 1: Creare le Credenziali OAuth su Google Cloud

### 1.1 Vai su Google Cloud Console

1. Apri il browser e vai su: **https://console.cloud.google.com/**
2. Accedi con il tuo account Google

### 1.2 Crea o Seleziona un Progetto

1. In alto a sinistra, clicca sul menu progetti (vicino a "Google Cloud")
2. Se hai già un progetto, selezionalo. Altrimenti:
   - Clicca su **"New Project"**
   - Nome: `Knowledge Navigator` (o qualsiasi nome tu preferisca)
   - Clicca **"Create"**
   - Seleziona il progetto appena creato

### 1.3 Abilita Google Calendar API

1. Nel menu a sinistra, vai su **"APIs & Services"** > **"Library"**
2. Nella barra di ricerca, digita: **"Google Calendar API"**
3. Clicca sul risultato **"Google Calendar API"**
4. Clicca il pulsante blu **"Enable"** (Abilita)
5. Attendi qualche secondo per l'abilitazione

### 1.4 Configura l'OAuth Consent Screen

1. Nel menu a sinistra, vai su **"APIs & Services"** > **"OAuth consent screen"**
2. Scegli **"External"** (per uso personale o testing)
3. Clicca **"Create"**
4. Compila il form:
   - **App name**: `Knowledge Navigator` (o qualsiasi nome)
   - **User support email**: Il tuo indirizzo email
   - **Developer contact information**: Il tuo indirizzo email
5. Clicca **"Save and Continue"**
6. Nella schermata "Scopes" (permessi), clicca **"Save and Continue"** (useremo i default)
7. Nella schermata "Test users" (utenti di test), aggiungi il tuo indirizzo email Google se necessario
8. Clicca **"Save and Continue"** fino a completare

### 1.5 Crea le Credenziali OAuth

1. Nel menu a sinistra, vai su **"APIs & Services"** > **"Credentials"**
2. In alto, clicca su **"+ CREATE CREDENTIALS"**
3. Seleziona **"OAuth client ID"**
4. Se è la prima volta, ti chiederà di configurare il consent screen (fai riferimento al passo 1.4)

5. Nella schermata "Create OAuth client ID":
   - **Application type**: Seleziona **"Web application"**
   - **Name**: `Knowledge Navigator Calendar` (o qualsiasi nome)
   
   - **Authorized redirect URIs**: Aggiungi questa URI (IMPORTANTE!):
     ```
     http://localhost:8000/api/integrations/calendars/oauth/callback
     ```
     Clicca **"+ ADD URI"** dopo averla inserita
   
6. Clicca **"Create"**

### 1.6 Copia Client ID e Client Secret

Dopo aver creato le credenziali, vedrai una finestra popup con:
- **Your Client ID**: Una stringa lunga che inizia con numeri (es: `123456789-abc...`)
- **Your Client Secret**: Una stringa che inizia con `GOCSPX-` (es: `GOCSPX-abc...`)

**⚠️ IMPORTANTE**: 
- Copia subito il Client Secret perché Google lo mostra solo una volta!
- Se lo perdi, dovrai crearne uno nuovo

---

## 📝 Passo 2: Configurare il Backend

### 2.1 Crea o Modifica il file .env

1. Vai nella cartella `backend` del progetto:
   ```bash
   cd backend
   ```

2. Crea un file chiamato `.env` se non esiste già:
   ```bash
   # Su Mac/Linux:
   touch .env
   
   # Oppure crealo manualmente con il tuo editor
   ```

3. Apri il file `.env` e aggiungi queste righe (sostituisci con i tuoi valori):

   ```env
   # Google OAuth2 Credentials (sostituisci con i tuoi valori!)
   GOOGLE_CLIENT_ID=123456789-abc...your-client-id...xyz.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=GOCSPX-your-client-secret-here
   GOOGLE_REDIRECT_URI=http://localhost:8000/api/integrations/calendars/oauth/callback
   
   # Encryption Key (genera una stringa casuale di 32 caratteri)
   # Puoi generarla con: python -c "import secrets; print(secrets.token_urlsafe(32))"
   CREDENTIALS_ENCRYPTION_KEY=your-random-32-character-key-here-change-me
   ```

   **Esempio concreto:**
   ```env
   GOOGLE_CLIENT_ID=123456789012-abcdefghijklmnopqrstuvwxyz123456.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=GOCSPX-1234567890abcdefghijklmnop
   GOOGLE_REDIRECT_URI=http://localhost:8000/api/integrations/calendars/oauth/callback
   CREDENTIALS_ENCRYPTION_KEY=abc123xyz456def789ghi012jkl345mno678
   ```

### 2.2 Genera una Chiave di Criptazione Sicura (Opzionale ma Raccomandato)

Per generare una chiave sicura di 32 caratteri, esegui:

```bash
cd backend
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Copia l'output e incollalo come valore di `CREDENTIALS_ENCRYPTION_KEY` nel file `.env`.

---

## ✅ Passo 3: Verificare la Configurazione

### 3.1 Riavvia il Backend

Se il backend è già in esecuzione, fermalo (Ctrl+C) e riavvialo per caricare le nuove variabili d'ambiente:

```bash
cd backend
source venv/bin/activate  # Se usi un virtual environment
uvicorn app.main:app --reload
```

### 3.2 Verifica che il Backend Funzioni

Apri un browser e vai su:
```
http://localhost:8000/health
```

Dovresti vedere:
```json
{"status": "healthy"}
```

---

## 🎯 Passo 4: Testare il Collegamento

### 4.1 Avvia il Frontend

In un altro terminale:

```bash
cd frontend
npm run dev
```

### 4.2 Vai sulla Pagina Integrazioni

Apri il browser e vai su:
```
http://localhost:3003/integrations
```

### 4.3 Collega Google Calendar

1. Dovresti vedere una sezione "Google Calendar" con stato "Non collegato"
2. Clicca il pulsante **"Connetti Google Calendar"**
3. Verrai reindirizzato a Google per autorizzare l'accesso
4. Seleziona il tuo account Google
5. Leggi i permessi richiesti e clicca **"Consenti"** (o "Allow")
6. Verrai reindirizzato automaticamente alla pagina integrazioni con messaggio "Collegato"

### 4.4 Testa la Connessione

1. Clicca il pulsante **"Test Connessione"**
2. Dovresti vedere un messaggio che conferma la connessione e il numero di eventi trovati

---

## 🗣️ Passo 5: Testare nel Chatbot

### 5.1 Vai a una Sessione

1. Vai alla dashboard: `http://localhost:3003`
2. Crea o apri una sessione esistente

### 5.2 Fai Domande sul Calendario

Prova a chiedere al chatbot:

- "Ho eventi domani?"
- "Quali meeting ho questa settimana?"
- "Mostrami gli appuntamenti di oggi"
- "Ho appuntamenti il 15 marzo?"
- "Eventi prossima settimana"

Il chatbot dovrebbe recuperare automaticamente gli eventi dal tuo Google Calendar e rispondere con le informazioni.

---

## ❌ Risoluzione Problemi

### Problema: "Google OAuth credentials not configured"

**Soluzione**: Verifica che:
1. Il file `.env` esista nella cartella `backend/`
2. Le variabili `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` siano presenti
3. Il backend sia stato riavviato dopo aver aggiunto le variabili

### Problema: "redirect_uri_mismatch"

**Soluzione**: Verifica che l'URI nel file `.env` corrisponda esattamente a quello in Google Cloud Console:
- Deve essere: `http://localhost:8000/api/integrations/calendars/oauth/callback`
- Controlla anche che non ci siano spazi o caratteri extra

### Problema: "access_denied" durante OAuth

**Soluzione**: 
- Assicurati di aver abilitato Google Calendar API (passo 1.3)
- Verifica che il tuo account sia aggiunto come "Test user" nel consent screen

### Problema: Il callback non funziona

**Soluzione**: 
- Verifica che il backend sia in ascolto sulla porta 8000
- Controlla che il redirect URI in Google Cloud Console sia esattamente:
  `http://localhost:8000/api/integrations/calendars/oauth/callback`

---

## 📚 Riferimenti

- [Google Calendar API Documentation](https://developers.google.com/calendar/api)
- [OAuth 2.0 Setup Guide](https://developers.google.com/identity/protocols/oauth2)

---

**Nota**: Per uso in produzione, dovrai:
1. Cambiare `localhost` con il tuo dominio
2. Usare HTTPS invece di HTTP
3. Aggiornare il redirect URI in Google Cloud Console

