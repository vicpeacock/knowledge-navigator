# Testing Email Auto-Session Creation

## 🎯 Obiettivo

Testare la funzionalità di creazione automatica di sessioni quando arriva un'email che richiede un'azione da parte del ricevente.

---

## 🧪 Test Automatici

### E2E Tests

**File**: `backend/tests/test_email_auto_session.py`

**4 test** che coprono:

1. ✅ **test_email_analysis_creates_session_for_actionable_email**: Verifica che email che richiedono azione creino sessioni automatiche
2. ✅ **test_email_analysis_no_session_for_info_email**: Verifica che email informative NON creino sessioni
3. ✅ **test_email_analyzer_detects_action_required**: Testa l'analisi LLM per rilevare azioni richieste
4. ✅ **test_email_action_processor_creates_session**: Verifica che il processor crei correttamente la sessione

**Esecuzione**:
```bash
cd backend
source venv/bin/activate
pytest tests/test_email_auto_session.py -v
```

---

## 📧 Test Manuale con Email Reali

### Prerequisiti

1. ✅ Gmail integration configurata e collegata
2. ✅ Backend in esecuzione con `email_analysis_enabled=true`
3. ✅ Ollama/LLM disponibile e funzionante

### Step 1: Verificare Configurazione

Controlla che l'analisi email sia abilitata:

```bash
# Nel file .env o configurazione
EMAIL_ANALYSIS_ENABLED=true
EMAIL_ANALYSIS_AUTO_SESSION_ENABLED=true
EMAIL_ANALYSIS_MIN_URGENCY_FOR_SESSION=medium
```

### Step 2: Inviare Email di Test

Invia un'email al tuo Gmail collegato che richiede chiaramente un'azione:

**Esempio 1: Richiesta Conferma**
```
Oggetto: Please confirm your attendance
Da: organizer@example.com
Contenuto: 
Hi, we need your confirmation for the meeting tomorrow at 2pm. 
Please reply ASAP to confirm.
```

**Esempio 2: Richiesta Task**
```
Oggetto: Action Required: Review Document
Da: manager@example.com
Contenuto:
Please review the attached document and provide feedback by Friday.
This is urgent.
```

**Esempio 3: Creare Evento Calendar**
```
Oggetto: Meeting Invitation
Da: colleague@example.com
Contenuto:
Let's meet next Monday at 3pm to discuss the project.
Please add this to your calendar.
```

### Step 3: Triggerare Controllo Email

Attendi il polling automatico (ogni minuto) oppure triggera manualmente:

```bash
curl -X POST http://localhost:8000/api/notifications/check-events \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json"
```

Oppure usa l'endpoint delle sessioni:

```bash
curl -X POST http://localhost:8000/api/sessions/notifications/check-events \
  -H "Authorization: Bearer your-jwt-token"
```

### Step 4: Verificare Risultati

#### 4.1 Verificare Log Backend

Cerca nei log del backend:

```
Email analysis for {email_id}: category=direct, requires_action=True, action_type=reply, urgency=high
Created automatic session {session_id} for email {email_id}
Created notification for new email from {sender} (priority: high, action: reply)
```

#### 4.2 Verificare Notifica

1. Apri il frontend
2. Clicca sulla campanella 🔔
3. Dovresti vedere:
   - Notifica email con dettagli
   - Pulsante "Apri Sessione →" (se sessione creata)
   - Priorità alta (se urgency=high)

#### 4.3 Verificare Sessione Automatica

1. Vai alla lista sessioni (`/sessions`)
2. Dovresti vedere una nuova sessione con:
   - Titolo: "Email: {subject}"
   - Descrizione: "Email da {sender}"
   - Metadata: `source: "email_analysis"`

3. Apri la sessione
4. Dovresti vedere:
   - Messaggio iniziale con riassunto email
   - Suggerimenti per azioni (rispondere, creare evento, ecc.)
   - Risposta automatica dell'AI con suggerimenti

#### 4.4 Verificare Database

```bash
# Connettiti al database
docker-compose exec postgres psql -U knavigator -d knowledge_navigator

# Verifica sessioni create
SELECT id, title, description, session_metadata->>'source' as source, 
       session_metadata->>'email_id' as email_id
FROM sessions 
WHERE session_metadata->>'source' = 'email_analysis'
ORDER BY created_at DESC
LIMIT 5;

# Verifica notifiche
SELECT id, type, urgency, content->>'email_id' as email_id,
       content->>'auto_session_id' as session_id
FROM notifications
WHERE type = 'email_received'
ORDER BY created_at DESC
LIMIT 5;
```

---

## 🔍 Debugging

### Problema: Sessione non viene creata

**Checklist**:
1. ✅ Verifica che `EMAIL_ANALYSIS_ENABLED=true`
2. ✅ Verifica che `EMAIL_ANALYSIS_AUTO_SESSION_ENABLED=true`
3. ✅ Verifica che l'integrazione Gmail sia `enabled=true`
4. ✅ Verifica che l'email abbia `user_id` nell'integrazione (necessario per creare sessione)
5. ✅ Controlla i log per errori LLM
6. ✅ Verifica che `urgency >= medium` (configurabile)

**Log da cercare**:
```
Email analysis for {email_id}: ...
Created automatic session {session_id} for email {email_id}
```

**Se non vedi questi log**:
- L'analisi potrebbe non rilevare azione richiesta
- L'urgenza potrebbe essere troppo bassa
- L'integrazione potrebbe non avere `user_id`

### Problema: Analisi LLM non funziona

**Checklist**:
1. ✅ Verifica che Ollama sia in esecuzione
2. ✅ Verifica che il modello LLM sia disponibile
3. ✅ Controlla i log per errori LLM

**Test manuale analisi**:
```python
from app.services.email_analyzer import EmailAnalyzer
from app.core.ollama_client import OllamaClient

analyzer = EmailAnalyzer(ollama_client=OllamaClient())
email = {
    "subject": "Please confirm",
    "from": "test@example.com",
    "snippet": "We need your confirmation ASAP",
    "category": "direct",
}
analysis = await analyzer.analyze_email(email)
print(analysis)
```

### Problema: Notifica senza link sessione

**Checklist**:
1. ✅ Verifica che la sessione sia stata creata (controlla database)
2. ✅ Verifica che `auto_session_id` sia nel content della notifica
3. ✅ Verifica che il frontend mostri il pulsante "Apri Sessione"

**Query database**:
```sql
SELECT id, content->>'auto_session_id' as session_id, content->>'email_id' as email_id
FROM notifications
WHERE type = 'email_received'
ORDER BY created_at DESC
LIMIT 1;
```

---

## 📊 Casi di Test

### Test Case 1: Email con Richiesta Esplicita

**Input**:
- Oggetto: "Action Required: Please Confirm"
- Contenuto: "Please confirm your attendance by replying to this email"

**Risultato Atteso**:
- ✅ `requires_action: true`
- ✅ `action_type: "reply"`
- ✅ `urgency: "high"`
- ✅ Sessione creata
- ✅ Notifica con link sessione

### Test Case 2: Email Informativa

**Input**:
- Oggetto: "Newsletter: Weekly Update"
- Contenuto: "Here's your weekly newsletter..."

**Risultato Atteso**:
- ✅ `requires_action: false`
- ✅ `action_type: null`
- ✅ `urgency: "low"`
- ❌ Nessuna sessione creata
- ✅ Notifica senza link sessione

### Test Case 3: Email con Invito Meeting

**Input**:
- Oggetto: "Meeting Invitation"
- Contenuto: "Let's meet Monday at 3pm. Please add to calendar."

**Risultato Atteso**:
- ✅ `requires_action: true`
- ✅ `action_type: "calendar_event"`
- ✅ `urgency: "medium"`
- ✅ Sessione creata
- ✅ Messaggio iniziale suggerisce creare evento

### Test Case 4: Email Mailing List

**Input**:
- Oggetto: "Discussion: Project Updates"
- Contenuto: "Here's the latest discussion..."
- Categoria Gmail: `CATEGORY_FORUMS`

**Risultato Atteso**:
- ✅ `category: "mailing_list"`
- ✅ `requires_action: false` (probabilmente)
- ❌ Nessuna sessione creata

---

## 🚀 Quick Test Script

Crea un file `test_email_auto_session_manual.py`:

```python
"""
Quick manual test for email auto-session creation
"""
import asyncio
from app.db.database import AsyncSessionLocal
from app.services.schedulers.email_poller import EmailPoller

async def test():
    async with AsyncSessionLocal() as db:
        poller = EmailPoller(db)
        events = await poller.check_new_emails()
        print(f"Found {len(events)} email events")
        for event in events:
            print(f"  - {event['type']}: {event.get('subject', 'N/A')}")
            if event.get('session_id'):
                print(f"    ✅ Session created: {event['session_id']}")
            else:
                print(f"    ℹ️  No session (info email)")

if __name__ == "__main__":
    asyncio.run(test())
```

Esegui:
```bash
cd backend
python test_email_auto_session_manual.py
```

---

## ✅ Checklist Test Completo

- [ ] Email con richiesta esplicita → Sessione creata
- [ ] Email informativa → Nessuna sessione
- [ ] Notifica mostra link sessione quando presente
- [ ] Sessione contiene messaggio iniziale con riassunto
- [ ] Messaggio iniziale suggerisce azioni appropriate
- [ ] Risposta automatica AI generata
- [ ] Metadata sessione contiene `email_id` e `source`
- [ ] Notifica contiene `auto_session_id` nel content
- [ ] Priorità notifica basata su urgenza analisi
- [ ] Duplicati evitati (stessa email non crea più sessioni)

---

## 📝 Note

- L'analisi LLM può richiedere alcuni secondi
- Le sessioni vengono create solo per email con `urgency >= medium` (default)
- Le sessioni vengono create solo se l'integrazione ha `user_id`
- Il sistema evita duplicati controllando se esiste già una sessione per lo stesso `email_id`

