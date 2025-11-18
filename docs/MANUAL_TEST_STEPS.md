# Test Manuale: Email Auto-Session - Step by Step

## 🎯 Obiettivo

Verificare che quando arriva un'email che richiede un'azione, il sistema:
1. Analizza l'email con LLM
2. Rileva che richiede un'azione
3. Crea automaticamente una sessione
4. Crea una notifica con link alla sessione

---

## 📋 Checklist Pre-Test

Prima di iniziare, verifica:

- [ ] Backend in esecuzione
- [ ] Ollama/LLM disponibile e funzionante
- [ ] Gmail integration collegata e abilitata
- [ ] Frontend in esecuzione
- [ ] Utente loggato nel frontend

---

## 🚀 Test Step-by-Step

### Step 1: Prepara Email di Test

Invia un'email al tuo Gmail collegato con una richiesta chiara:

**📧 Email Consigliata:**
```
A: il_tuo_gmail@gmail.com
Oggetto: Please confirm your attendance for tomorrow's meeting
Corpo: 
Hi,

We need your confirmation for the meeting tomorrow at 2pm. 
Please reply ASAP to confirm your attendance.

Thanks!
```

**Perché questa email funziona:**
- ✅ Richiesta esplicita ("Please confirm")
- ✅ Urgenza ("ASAP")
- ✅ Azione chiara ("reply")
- ✅ Categoria "direct" (non mailing list)

---

### Step 2: Verifica Configurazione Backend

Controlla che l'analisi sia abilitata (dovrebbe essere di default):

```bash
# Verifica nei log del backend all'avvio:
# Dovresti vedere: "Email analysis services initialized"
```

Se non vedi questo messaggio, controlla:
- Ollama è in esecuzione?
- `EMAIL_ANALYSIS_ENABLED=true` (default: true)

---

### Step 3: Triggera Controllo Email

**Opzione A: Attendi polling automatico** (ogni 60 secondi)

**Opzione B: Triggera manualmente**

Usa lo script:
```bash
./scripts/test_email_auto_session.sh
```

Oppure manualmente:
```bash
curl -X POST http://localhost:8000/api/notifications/check-events \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json"
```

Oppure dal frontend:
- Apri una sessione qualsiasi
- Clicca sulla campanella 🔔
- Il sistema controllerà automaticamente

---

### Step 4: Monitora Log Backend

In un altro terminale, monitora i log:

```bash
# Se usi docker-compose:
docker-compose logs -f backend | grep -E "(Email analysis|Created automatic session|Created notification)"

# Oppure usa lo script:
./scripts/monitor_email_analysis.sh
```

**Cosa cercare nei log:**

✅ **Successo:**
```
Email analysis for {email_id}: category=direct, requires_action=True, action_type=reply, urgency=high
Created automatic session {session_id} for email {email_id}
Created notification for new email from {sender} (priority: high, action: reply)
```

⚠️ **Possibili problemi:**
```
Failed to initialize email analysis services: ...
Error analyzing email {email_id}: ...
Error processing email action for {email_id}: ...
```

---

### Step 5: Verifica Notifica

1. **Apri il frontend**
2. **Clicca sulla campanella 🔔**
3. **Cerca la notifica email**

**Dovresti vedere:**
- ✅ Notifica con oggetto email
- ✅ Mittente e snippet
- ✅ **Pulsante "Apri Sessione →"** (se sessione creata)
- ✅ Priorità alta (se urgency=high)

**Se NON vedi il pulsante "Apri Sessione":**
- La sessione potrebbe non essere stata creata
- Controlla i log per errori
- Verifica che l'integrazione abbia `user_id`

---

### Step 6: Verifica Sessione Automatica

1. **Vai alla lista sessioni** (sidebar o `/sessions`)
2. **Cerca nuova sessione** con:
   - Titolo: "Email: Please confirm your attendance..."
   - Descrizione: "Email da {mittente}"
   - Icona o indicatore che è da email

3. **Apri la sessione**

**Dovresti vedere:**
- ✅ Messaggio iniziale con riassunto email
- ✅ Suggerimenti per azioni (es. "Posso aiutarti a rispondere...")
- ✅ Risposta automatica dell'AI con suggerimenti

**Esempio messaggio iniziale:**
```
Ho ricevuto una nuova email che richiede attenzione:

**Da**: organizer@example.com
**Oggetto**: Please confirm your attendance

**Contenuto**: We need your confirmation for the meeting tomorrow...

**Azione richiesta**: User needs to confirm attendance

Come vuoi procedere? Posso aiutarti a:
- Rispondere all'email
- Solo archiviare l'email se non è importante
```

---

### Step 7: Verifica Database (Opzionale)

Se vuoi verificare direttamente nel database:

```bash
# Connettiti al database
docker-compose exec postgres psql -U knavigator -d knowledge_navigator

# Verifica sessioni create da email
SELECT id, title, description, 
       session_metadata->>'source' as source,
       session_metadata->>'email_id' as email_id,
       session_metadata->>'action_type' as action_type
FROM sessions 
WHERE session_metadata->>'source' = 'email_analysis'
ORDER BY created_at DESC
LIMIT 5;

# Verifica notifiche
SELECT id, type, urgency, 
       content->>'email_id' as email_id,
       content->>'auto_session_id' as session_id,
       content->>'subject' as subject
FROM notifications
WHERE type = 'email_received'
ORDER BY created_at DESC
LIMIT 5;
```

---

## ✅ Criteri di Successo

Il test è **riuscito** se:

1. ✅ **Log backend** mostrano:
   - Analisi email completata
   - Sessione creata (se email richiede azione)
   - Notifica creata

2. ✅ **Notifica** nel frontend:
   - Mostra dettagli email
   - Ha pulsante "Apri Sessione" (se sessione creata)

3. ✅ **Sessione automatica**:
   - Creata nella lista sessioni
   - Ha messaggio iniziale con riassunto
   - Ha risposta automatica dell'AI

4. ✅ **Database**:
   - Sessione salvata con metadata corretti
   - Notifica salvata con link alla sessione

---

## 🔍 Troubleshooting

### Problema: Nessuna sessione creata

**Checklist:**
1. ✅ Verifica che l'integrazione Gmail abbia `user_id` (necessario!)
2. ✅ Verifica che Ollama sia in esecuzione
3. ✅ Controlla i log per errori LLM
4. ✅ Verifica che l'email sia arrivata come "unread"
5. ✅ Verifica che l'analisi abbia rilevato `requires_action=True`

**Query per verificare integrazione:**
```sql
SELECT id, user_id, enabled, provider, service_type 
FROM integrations 
WHERE provider = 'google' AND service_type = 'email';
```

Se `user_id` è NULL, la sessione non può essere creata!

### Problema: Analisi non rileva azione

**Possibili cause:**
- Email troppo generica/informativa
- LLM non disponibile
- Snippet troppo corto

**Soluzione:** Prova con email più esplicite:
- "Please confirm"
- "Action required"
- "Please reply ASAP"
- "Urgent"

### Problema: Sessione creata ma senza messaggio

**Checklist:**
1. ✅ Verifica che la sessione abbia almeno un messaggio
2. ✅ Controlla i log per errori nella creazione del messaggio
3. ✅ Verifica che `_trigger_chat_response` sia stato chiamato

---

## 📊 Risultati Attesi

Dopo aver inviato un'email che richiede azione:

| Componente | Risultato Atteso |
|------------|------------------|
| **Log Backend** | "Created automatic session {id} for email {email_id}" |
| **Notifica** | Mostra email + pulsante "Apri Sessione" |
| **Sessione** | Creata con titolo "Email: {subject}" |
| **Messaggio** | Riassunto email + suggerimenti azioni |
| **AI Response** | Risposta automatica con suggerimenti |

---

## 🎬 Prossimi Passi Dopo il Test

Se il test è riuscito:

1. ✅ **Rispondi nella sessione** (es. "Sì, confermo")
2. ✅ **Verifica** che l'AI risponda appropriatamente
3. ✅ **Testa** altri tipi di email (calendar event, task, ecc.)

Se il test non è riuscito:

1. 🔍 **Controlla i log** per errori specifici
2. 🔍 **Verifica configurazione** (Ollama, integrazione, ecc.)
3. 🔍 **Riprova** con email più esplicite

---

## 💡 Tips

- **Email più efficaci**: Usa frasi esplicite come "Please confirm", "Action required", "Please reply"
- **Urgenza**: Email con "ASAP", "urgent", "important" hanno più probabilità di creare sessioni
- **Categoria**: Email "direct" (non mailing list) hanno più probabilità di richiedere azione
- **Timing**: Attendi 1-2 minuti dopo aver inviato l'email prima di triggerare il controllo

