# Quick Test: Email Auto-Session Creation

## 🚀 Test Rapido (5 minuti)

### Step 1: Verifica Configurazione

Assicurati che nel backend sia abilitato:

```bash
# Nel file .env o configurazione backend
EMAIL_ANALYSIS_ENABLED=true
EMAIL_ANALYSIS_AUTO_SESSION_ENABLED=true
EMAIL_ANALYSIS_MIN_URGENCY_FOR_SESSION=medium
```

### Step 2: Invia Email di Test

Invia un'email al tuo Gmail collegato con una richiesta chiara:

**Opzione A: Email con Richiesta Conferma**
```
A: il_tuo_gmail@gmail.com
Oggetto: Please confirm your attendance
Corpo: Hi, we need your confirmation for the meeting tomorrow at 2pm. Please reply ASAP to confirm.
```

**Opzione B: Email con Richiesta Task**
```
A: il_tuo_gmail@gmail.com
Oggetto: Action Required: Review Document
Corpo: Please review the attached document and provide feedback by Friday. This is urgent.
```

### Step 3: Triggera Controllo Email

**Opzione 1: Attendi polling automatico** (ogni minuto)

**Opzione 2: Triggera manualmente**:
```bash
curl -X POST http://localhost:8000/api/notifications/check-events \
  -H "X-API-Key: your-api-key"
```

Oppure usa il frontend: vai su una sessione qualsiasi e clicca sulla campanella 🔔 - il sistema controllerà automaticamente.

### Step 4: Verifica Risultati

#### ✅ Verifica Notifica

1. Apri il frontend
2. Clicca sulla campanella 🔔
3. Dovresti vedere:
   - Notifica email con oggetto e mittente
   - Pulsante **"Apri Sessione →"** (se sessione creata)

#### ✅ Verifica Sessione Automatica

1. Vai alla lista sessioni (`/sessions` o sidebar)
   - **Nota**: I bottoni "Integrazioni" e "Memoria" sono stati rimossi da SessionList e sono disponibili solo nel menu principale
2. Cerca una nuova sessione con:
   - Titolo: "Email: {oggetto email}"
   - Descrizione: "Email da {mittente}"
3. Apri la sessione
4. Dovresti vedere:
   - Messaggio iniziale con riassunto email
   - Suggerimenti per azioni (es. "Posso aiutarti a rispondere...")
   - Risposta automatica dell'AI

### Step 5: Verifica Log Backend

Cerca nei log del backend:

```bash
# Dovresti vedere:
Email analysis for {email_id}: category=direct, requires_action=True, action_type=reply, urgency=high
Created automatic session {session_id} for email {email_id}
Created notification for new email from {sender} (priority: high, action: reply)
✅ Successfully deleted notification... (se elimini la notifica)
```

---

## 🔍 Troubleshooting

### Problema: Nessuna sessione creata

**Checklist**:
1. ✅ Verifica che l'integrazione Gmail abbia `user_id` (necessario per creare sessione)
2. ✅ Verifica che Ollama/LLM sia in esecuzione
3. ✅ Controlla i log per errori LLM
4. ✅ Verifica che l'email sia arrivata come "non letta" (unread)

**Query database per verificare integrazione**:
```sql
SELECT id, user_id, enabled, provider, service_type 
FROM integrations 
WHERE provider = 'google' AND service_type = 'email';
```

Se `user_id` è NULL, la sessione non può essere creata. Deve essere collegata a un utente specifico.

### Problema: Analisi non rileva azione

**Possibili cause**:
- Email troppo generica/informativa
- LLM non disponibile o errore
- Snippet email troppo corto

**Soluzione**: Prova con email più esplicite che contengano:
- "Please confirm"
- "Action required"
- "Please reply"
- "Urgent"

### Problema: Sessione creata ma senza messaggio iniziale

**Checklist**:
1. ✅ Verifica che la sessione abbia almeno un messaggio
2. ✅ Controlla i log per errori nella creazione del messaggio
3. ✅ Verifica che `_trigger_chat_response` sia stato chiamato

---

## 📊 Esempi Email per Test

### ✅ Email che DOVREBBE creare sessione:

1. **Richiesta Conferma**:
   ```
   Oggetto: Please confirm your attendance
   Corpo: We need your confirmation for the meeting tomorrow. Please reply ASAP.
   ```

2. **Richiesta Task**:
   ```
   Oggetto: Action Required: Review Document
   Corpo: Please review the attached document and provide feedback by Friday. This is urgent.
   ```

3. **Invito Meeting**:
   ```
   Oggetto: Meeting Invitation
   Corpo: Let's meet next Monday at 3pm to discuss the project. Please add this to your calendar.
   ```

### ❌ Email che NON dovrebbe creare sessione:

1. **Newsletter**:
   ```
   Oggetto: Newsletter: Weekly Update
   Corpo: Here's your weekly newsletter with updates...
   ```

2. **Notifica Automatica**:
   ```
   Oggetto: Your order has been shipped
   Corpo: Your order #12345 has been shipped. Track it here...
   ```

3. **Email Informativa**:
   ```
   Oggetto: System Maintenance Notice
   Corpo: We will perform maintenance on Sunday from 2am to 4am...
   ```

---

## 🎯 Risultato Atteso

Dopo aver inviato un'email che richiede azione:

1. ✅ **Notifica creata** nella campanella
2. ✅ **Sessione automatica creata** nella lista sessioni
3. ✅ **Messaggio iniziale** nella sessione con riassunto
4. ✅ **Link sessione** nella notifica (pulsante "Apri Sessione")
5. ✅ **Risposta automatica** dell'AI con suggerimenti

---

## 🔄 Test Completo End-to-End

1. **Invia email** con richiesta chiara
2. **Attendi** polling (1 minuto) o triggera manualmente
3. **Verifica notifica** nella campanella
4. **Clicca "Apri Sessione"** nella notifica
5. **Verifica sessione** con messaggio iniziale
6. **Rispondi** nella sessione (es. "Sì, confermo")
7. **Verifica** che l'AI risponda appropriatamente

---

## 📝 Note

- Le sessioni vengono create solo per email con `urgency >= medium`
- Le sessioni vengono create solo se l'integrazione ha `user_id`
- Il sistema evita duplicati (non crea più sessioni per la stessa email)
- L'analisi LLM può richiedere alcuni secondi

