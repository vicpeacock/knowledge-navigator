# Email Intelligent Analysis - Design Document

## 📋 Panoramica

Sistema avanzato per analizzare automaticamente le email in arrivo usando LLM per:
1. **Categorizzazione**: Distinguere email dirette da mailing list
2. **Rilevamento azioni**: Identificare azioni richieste dall'utente
3. **Creazione sessioni automatiche**: Creare sessioni chat per azioni che richiedono input utente
4. **Memoria a lungo termine**: Aggiornare la memoria basandosi sulle risposte dell'utente

---

## 🏗️ Architettura Proposta

### Componenti Principali

```
EmailPoller
  ↓
EmailAnalyzer (nuovo servizio)
  ├─ Estrae labels Gmail (categorie)
  ├─ Analizza contenuto con LLM
  ├─ Determina tipo email (diretta/mailing list)
  ├─ Rileva azioni richieste
  └─ Decide se creare sessione automatica
  ↓
EmailActionProcessor (nuovo servizio)
  ├─ Crea sessione automatica se necessario
  ├─ Genera prompt iniziale con riassunto email
  └─ Triggera analisi memoria dopo risposta utente
```

---

## 🔍 1. Categorizzazione Email

### Opzione A: Usare Labels Gmail (Raccomandato)

Gmail API restituisce labels che includono:
- `CATEGORY_PERSONAL` / `CATEGORY_SOCIAL` / `CATEGORY_PROMOTIONS` / `CATEGORY_UPDATES` / `CATEGORY_FORUMS`
- Labels personalizzate dell'utente
- `UNREAD`, `STARRED`, ecc.

**Implementazione:**
```python
# In EmailService.get_gmail_messages()
email_data["labels"] = msg_detail.get("labelIds", [])
email_data["category"] = self._extract_category(msg_detail.get("labelIds", []))

def _extract_category(self, label_ids: List[str]) -> str:
    """Extract Gmail category from labels"""
    categories = {
        "CATEGORY_PERSONAL": "direct",
        "CATEGORY_SOCIAL": "social",
        "CATEGORY_PROMOTIONS": "promotional",
        "CATEGORY_UPDATES": "update",
        "CATEGORY_FORUMS": "mailing_list",
    }
    for label in label_ids:
        if label in categories:
            return categories[label]
    return "unknown"
```

### Opzione B: Analisi LLM (Fallback)

Se le labels non sono disponibili, usare LLM per analizzare:
- Mittente (singolo vs mailing list)
- Oggetto (pattern mailing list)
- Contenuto (formato standardizzato)

---

## 🤖 2. Rilevamento Azioni Richieste

### EmailAnalyzer Service

```python
class EmailAnalyzer:
    """Analyzes emails to detect required actions"""
    
    async def analyze_email(
        self,
        email: Dict[str, Any],
        ollama_client: OllamaClient,
    ) -> Dict[str, Any]:
        """
        Analyze email and return:
        - category: "direct" | "mailing_list" | "promotional" | "update"
        - requires_action: bool
        - action_type: "reply" | "calendar_event" | "task" | "info" | None
        - action_summary: str (description of required action)
        - urgency: "high" | "medium" | "low"
        """
```

### Prompt LLM per Analisi

```python
ANALYSIS_PROMPT = """
Analizza questa email e determina:

1. **Tipo email**: 
   - "direct": Email diretta all'utente (richiede risposta)
   - "mailing_list": Email da mailing list o gruppo
   - "promotional": Email promozionale/commerciale
   - "update": Notifica/aggiornamento automatico

2. **Azione richiesta**:
   - "reply": L'utente deve rispondere
   - "calendar_event": C'è un evento da aggiungere al calendario
   - "task": C'è un task/azione da completare
   - "info": Solo informativa, nessuna azione richiesta
   - None: Nessuna azione richiesta

3. **Urgenza**: "high" | "medium" | "low"

4. **Riassunto azione**: Breve descrizione dell'azione richiesta (se presente)

Email:
Mittente: {from}
Oggetto: {subject}
Contenuto: {body}

Rispondi in formato JSON:
{
  "category": "direct",
  "requires_action": true,
  "action_type": "reply",
  "action_summary": "L'utente deve confermare la partecipazione all'evento",
  "urgency": "high",
  "reasoning": "L'email contiene una richiesta esplicita di conferma"
}
"""
```

---

## 📝 3. Creazione Sessioni Automatiche

### EmailActionProcessor Service

```python
class EmailActionProcessor:
    """Processes email actions and creates sessions if needed"""
    
    async def process_email_action(
        self,
        db: AsyncSession,
        email: Dict[str, Any],
        analysis: Dict[str, Any],
        tenant_id: UUID,
        user_id: UUID,
    ) -> Optional[UUID]:  # Returns session_id if created
        """
        Create automatic session if action is required.
        Returns session_id if session was created.
        """
        if not analysis.get("requires_action"):
            return None
        
        # Create session with email context
        session = SessionModel(
            tenant_id=tenant_id,
            user_id=user_id,
            name=f"Email: {email['subject'][:50]}",
            title=email['subject'],
            description=f"Email da {email['from']}",
            status="active",
            session_metadata={
                "source": "email_analysis",
                "email_id": email['id'],
                "action_type": analysis['action_type'],
                "email_date": email['date'],
            }
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        
        # Create initial message with email summary and action request
        initial_message = self._create_initial_message(email, analysis)
        
        # Save initial message
        message = MessageModel(
            session_id=session.id,
            tenant_id=tenant_id,
            role="user",
            content=initial_message,
        )
        db.add(message)
        await db.commit()
        
        # Trigger chat response (async, in background)
        asyncio.create_task(
            self._trigger_chat_response(db, session.id, initial_message)
        )
        
        return session.id
    
    def _create_initial_message(
        self,
        email: Dict[str, Any],
        analysis: Dict[str, Any],
    ) -> str:
        """Create initial chat message summarizing email and action"""
        action_summary = analysis.get("action_summary", "")
        email_preview = email.get("snippet", "")[:200]
        
        return f"""Ho ricevuto una nuova email da {email['from']}:

**Oggetto**: {email['subject']}

**Contenuto**: {email_preview}

**Azione richiesta**: {action_summary}

Come vuoi procedere? Posso aiutarti a:
- Rispondere all'email
- Creare un evento nel calendario
- Creare un task/ricordo
- Solo archiviare l'email"""
```

---

## 🧠 4. Aggiornamento Memoria a Lungo Termine

### Integrazione con ConversationLearner

Quando l'utente risponde nella sessione creata automaticamente:

1. **Durante la chat**: Il `ConversationLearner` esistente estrae automaticamente conoscenze
2. **Dopo la risoluzione**: Analizza la conversazione completa per aggiornare:
   - Preferenze su come gestire certi tipi di email
   - Pattern di azioni comuni
   - Contatti importanti e loro pattern di comunicazione

### Esempio Prompt per Memoria

```python
MEMORY_UPDATE_PROMPT = """
Analizza questa conversazione generata da un'email e estrai:

1. **Preferenze gestione email**:
   - Come l'utente preferisce gestire certi tipi di email
   - Pattern di risposta (es. "L'utente risponde sempre rapidamente a email da X")

2. **Contatti importanti**:
   - Chi sono i contatti più importanti
   - Pattern di comunicazione con loro

3. **Azioni comuni**:
   - Tipi di azioni che l'utente compie spesso
   - Pattern di comportamento

Conversazione:
{conversation}

Email originale:
{email_summary}

Risposta utente:
{user_response}
"""
```

---

## 🔄 Flusso Completo

```
1. EmailPoller trova nuova email
   ↓
2. EmailAnalyzer analizza email:
   - Estrae labels Gmail (categoria)
   - Usa LLM per analisi approfondita
   - Determina se richiede azione
   ↓
3. Se requires_action == True:
   ↓
4. EmailActionProcessor:
   - Crea sessione automatica
   - Crea messaggio iniziale con riassunto
   - Triggera risposta chat automatica
   ↓
5. Utente interagisce nella sessione
   ↓
6. ConversationLearner (già esistente):
   - Estrae conoscenze dalla conversazione
   - Aggiorna memoria a lungo termine
   ↓
7. Sistema impara pattern per future email simili
```

---

## 📊 Configurazione

### Settings da aggiungere

```python
# In app/core/config.py

# Email Analysis
email_analysis_enabled: bool = True
email_analysis_llm_model: str = "llama3.2"  # Model for analysis
email_analysis_auto_session_enabled: bool = True  # Auto-create sessions
email_analysis_min_urgency_for_session: str = "medium"  # Only create sessions for medium+ urgency
email_analysis_learn_from_responses: bool = True  # Update memory from user responses
```

---

## 🎯 Vantaggi

1. **Proattività**: Il sistema anticipa le azioni necessarie
2. **Efficienza**: L'utente non deve leggere ogni email manualmente
3. **Apprendimento**: Il sistema impara dalle preferenze dell'utente
4. **Integrazione**: Sfrutta componenti esistenti (ConversationLearner, Session, Memory)

---

## 🚧 Considerazioni

### Performance
- Analisi LLM può essere costosa → Cache risultati per email simili
- Processare in background per non bloccare polling

### Privacy
- Email contengono dati sensibili → Crittografare in storage
- Logging limitato (solo metadata, non contenuto completo)

### Fallback
- Se LLM non disponibile → Usare solo labels Gmail
- Se analisi fallisce → Creare notifica standard

---

## 📝 Prossimi Passi

1. ✅ Estendere `EmailService` per estrarre labels Gmail
2. ✅ Creare `EmailAnalyzer` service
3. ✅ Creare `EmailActionProcessor` service
4. ✅ Integrare con `EmailPoller`
5. ✅ Aggiungere configurazione
6. ✅ Test con email reali
7. ✅ Documentazione utente

---

## 💡 Suggerimenti Aggiuntivi

### 1. Filtri Utente Personalizzabili
Permettere all'utente di configurare:
- Quali tipi di email creano sessioni automatiche
- Soglia di urgenza minima
- Domini/contatti da ignorare

### 2. Template Risposte
Il sistema può suggerire template di risposta basati su:
- Tipo di email
- Contenuto
- Storia precedente con quel mittente

### 3. Integrazione Calendar
Se l'email contiene date/eventi:
- Estrarre automaticamente informazioni evento
- Creare evento calendar direttamente
- Chiedere conferma all'utente

### 4. Notifiche Intelligenti
- Notifiche solo per email che richiedono azione
- Raggruppare email simili
- Priorità basata su analisi LLM

