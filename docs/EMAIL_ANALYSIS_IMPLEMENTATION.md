# Email Intelligent Analysis - Implementation Summary

## ✅ Implementazione Completata

Sistema di analisi intelligente delle email implementato con successo!

---

## 🏗️ Componenti Implementati

### 1. EmailService Esteso ✅
- **File**: `backend/app/services/email_service.py`
- **Funzionalità**:
  - Estrae labels Gmail (categorie automatiche)
  - Mappa categorie: `CATEGORY_PERSONAL` → "direct", `CATEGORY_FORUMS` → "mailing_list", ecc.
  - Aggiunge `labels` e `category` ai dati email

### 2. EmailAnalyzer Service ✅
- **File**: `backend/app/services/email_analyzer.py`
- **Funzionalità**:
  - Analizza email usando LLM per determinare:
    - **Categoria**: direct, mailing_list, promotional, update, social, unknown
    - **Azione richiesta**: reply, calendar_event, task, info, null
    - **Urgenza**: high, medium, low
    - **Riassunto azione**: Descrizione dell'azione richiesta
  - Usa Gmail labels se disponibili, altrimenti analisi LLM
  - Parsing robusto delle risposte JSON da LLM

### 3. EmailActionProcessor Service ✅
- **File**: `backend/app/services/email_action_processor.py`
- **Funzionalità**:
  - Crea sessioni automatiche per email che richiedono azione
  - Genera messaggio iniziale con riassunto email e suggerimenti azioni
  - Triggera risposta chat automatica
  - Evita duplicati (controlla se sessione esiste già)
  - Filtra per urgenza (solo medium+ per default)

### 4. Integrazione con EmailPoller ✅
- **File**: `backend/app/services/schedulers/email_poller.py`
- **Funzionalità**:
  - Analizza ogni nuova email quando viene rilevata
  - Crea notifiche con risultati analisi
  - Crea sessioni automatiche se necessario
  - Collega notifiche alle sessioni create

### 5. Configurazione ✅
- **File**: `backend/app/core/config.py`
- **Settings aggiunti**:
  ```python
  email_analysis_enabled: bool = True
  email_analysis_llm_model: Optional[str] = None
  email_analysis_auto_session_enabled: bool = True
  email_analysis_min_urgency_for_session: str = "medium"
  email_analysis_learn_from_responses: bool = True
  ```

---

## 🔄 Flusso di Funzionamento

```
1. EmailPoller trova nuova email
   ↓
2. EmailAnalyzer analizza email:
   - Estrae categoria da Gmail labels (se disponibili)
   - Usa LLM per analisi approfondita azioni
   ↓
3. Se requires_action == True e urgency >= medium:
   ↓
4. EmailActionProcessor:
   - Verifica se sessione esiste già (evita duplicati)
   - Crea sessione automatica
   - Crea messaggio iniziale con riassunto
   - Triggera risposta chat automatica
   ↓
5. Notifica creata con:
   - Risultati analisi
   - Link a sessione automatica (se creata)
   ↓
6. Utente vede:
   - Notifica nella campanella
   - Nuova sessione nella lista (se creata)
   - Messaggio iniziale con suggerimenti azioni
```

---

## 📊 Dati Analisi Salvati

Ogni notifica email ora contiene:

```json
{
  "email_id": "...",
  "from": "...",
  "subject": "...",
  "category": "direct" | "mailing_list" | ...,
  "analysis": {
    "category": "direct",
    "requires_action": true,
    "action_type": "reply",
    "action_summary": "L'utente deve confermare...",
    "urgency": "high",
    "reasoning": "..."
  },
  "auto_session_id": "..." // Se sessione creata
}
```

---

## 🎯 Esempi di Utilizzo

### Email che Richiede Risposta
- **Analisi**: `action_type: "reply"`, `urgency: "high"`
- **Azione**: Crea sessione automatica
- **Messaggio**: "Ho ricevuto una nuova email che richiede attenzione... Come vuoi procedere? Posso aiutarti a rispondere..."

### Email con Evento Calendar
- **Analisi**: `action_type: "calendar_event"`, `urgency: "medium"`
- **Azione**: Crea sessione automatica
- **Messaggio**: "... Posso aiutarti a creare un evento nel calendario..."

### Email Informativa
- **Analisi**: `action_type: null`, `requires_action: false`
- **Azione**: Solo notifica, nessuna sessione
- **Messaggio**: Notifica standard

---

## ⚙️ Configurazione

### Abilitare/Disabilitare Analisi

Nel file `.env`:
```env
# Abilita analisi intelligente
EMAIL_ANALYSIS_ENABLED=true

# Abilita creazione sessioni automatiche
EMAIL_ANALYSIS_AUTO_SESSION_ENABLED=true

# Urgenza minima per creare sessioni (medium o high)
EMAIL_ANALYSIS_MIN_URGENCY_FOR_SESSION=medium

# Usa modello LLM specifico per analisi (opzionale)
EMAIL_ANALYSIS_LLM_MODEL=llama3.2
```

---

## 🧪 Testing

### Test Manuale

1. **Invia email di test** al tuo Gmail collegato
2. **Attendi polling** (ogni minuto) o triggera manualmente:
   ```bash
   curl -X POST http://localhost:8000/api/notifications/check-events \
     -H "X-API-Key: your-api-key"
   ```
3. **Verifica**:
   - Notifica creata nella campanella
   - Se richiede azione → Sessione automatica creata
   - Messaggio iniziale nella sessione

### Verifica Log

Cerca nei log del backend:
```
Email analysis for {email_id}: category=direct, requires_action=True, action_type=reply, urgency=high
Created automatic session {session_id} for email {email_id}
```

---

## 🚧 Limitazioni Attuali

1. **Body Email**: Usa solo snippet per analisi (non body completo)
   - Sufficiente per la maggior parte dei casi
   - Può essere esteso in futuro se necessario

2. **Performance**: Analisi LLM può essere lenta
   - Processata in background
   - Non blocca il polling

3. **Memoria a Lungo Termine**: 
   - Il `ConversationLearner` esistente gestisce già l'estrazione conoscenze
   - Funziona automaticamente quando l'utente risponde nella sessione

---

## 🔮 Prossimi Miglioramenti

1. **Cache Analisi**: Cache risultati per email simili
2. **Filtri Utente**: Permettere configurazione personalizzata
3. **Template Risposte**: Suggerire template basati su storia
4. **Integrazione Calendar**: Estrarre eventi direttamente da email
5. **Notifiche Intelligenti**: Raggruppare email simili

---

## 📝 Note Tecniche

- **Deduplicazione**: Controlla `email_id` per evitare notifiche duplicate
- **Sessioni Duplicate**: Controlla `session_metadata.email_id` per evitare sessioni duplicate
- **Urgenza**: Solo email medium+ creano sessioni automatiche (configurabile)
- **Fallback**: Se LLM non disponibile, usa solo Gmail labels

---

## ✅ Status

- ✅ Estrazione labels Gmail
- ✅ Analisi LLM email
- ✅ Rilevamento azioni
- ✅ Creazione sessioni automatiche
- ✅ Integrazione con sistema notifiche
- ✅ Configurazione completa
- ⏳ Test con email reali (da fare)

