# Sistema di Comunicazione tra Agenti basato su LLM

## Problema Attuale

Attualmente, la comunicazione tra agenti avviene tramite:
1. **Database** (notifiche) - Background Agent crea notifiche, Main le legge
2. **Polling** - Main recupera notifiche quando genera risposta
3. **Race conditions** - Possibili problemi di timing

**Limitazioni:**
- Comunicazione asincrona e indiretta
- Nessuna "negoziazione" tra agenti
- Il Main non può chiedere chiarimenti al Background Agent
- Il Background Agent non può ricevere feedback dal Main

## Proposta: Sistema di Comunicazione LLM-based

### Architettura

```
┌─────────────────┐         ┌──────────────────┐
│  Main Agent     │◄───────►│  Message Broker   │
│  (Chat LLM)     │         │  (LLM-based)      │
└─────────────────┘         └──────────────────┘
                                      ▲
                                      │
                                      ▼
                            ┌──────────────────┐
                            │ Background Agent  │
                            │ (Integrity LLM)  │
                            └──────────────────┘
```

### Componenti

#### 1. Message Broker (LLM-based)

Un servizio centrale che:
- **Riceve messaggi** da agenti (Main, Background, Future: Event Monitor, Todo Manager, etc.)
- **Comprende il contesto** usando un LLM per interpretare priorità, urgenza, relazioni
- **Decide routing** - quale agente deve ricevere il messaggio
- **Formatta risposte** - traduce tra "linguaggi" degli agenti
- **Gestisce negoziazioni** - permette scambio multi-turn tra agenti

#### 2. Agent Messages

Ogni agente può inviare messaggi strutturati:

```python
class AgentMessage(BaseModel):
    from_agent: str  # "background", "main", "event_monitor", etc.
    to_agent: Optional[str] = None  # None = broadcast
    message_type: str  # "contradiction", "event", "question", "response"
    content: Dict[str, Any]
    priority: str  # "high", "medium", "low"
    requires_response: bool = False
    context: Dict[str, Any] = {}  # Session ID, user message, etc.
```

#### 3. LLM Communication Layer

Il Message Broker usa un LLM per:
- **Interpretare messaggi** - capire l'intento e l'urgenza
- **Decidere azioni** - cosa fare con il messaggio
- **Formattare risposte** - tradurre per l'agente destinatario
- **Gestire conflitti** - se più agenti hanno messaggi contrastanti

### Esempio di Flusso

#### Scenario: Contraddizione Rilevata

1. **Background Agent** rileva contraddizione:
```python
message = AgentMessage(
    from_agent="background",
    to_agent="main",
    message_type="contradiction",
    content={
        "new_memory": "L'utente detesta i ravioli",
        "existing_memory": "L'utente ama la pastasciutta",
        "confidence": 0.95,
        "explanation": "Ravioli è un tipo di pastasciutta"
    },
    priority="high",
    requires_response=True,
    context={"session_id": "...", "user_message": "Detesto i ravioli"}
)
```

2. **Message Broker** riceve e interpreta:
   - LLM analizza: "Alta confidenza, contraddizione tassonomica, richiede chiarimento utente"
   - Decide: "Invia a Main con urgenza HIGH, formatta come notifica interattiva"

3. **Main Agent** riceve e risponde:
```python
response = AgentMessage(
    from_agent="main",
    to_agent="background",
    message_type="response",
    content={
        "action": "notify_user",
        "format": "interactive",
        "question": "Quale informazione è corretta?",
        "options": ["A) Prima", "B) Seconda", "C) Entrambe", "D) Cancella"]
    },
    priority="high"
)
```

4. **Message Broker** formatta per il frontend:
   - Crea notifica con formato interattivo
   - Include opzioni per risposta utente

### Vantaggi

1. **Comunicazione Intelligente**
   - Gli agenti possono "parlare" tra loro
   - Il LLM interpreta contesto e priorità
   - Negoziazione multi-turn possibile

2. **Flessibilità**
   - Facile aggiungere nuovi agenti
   - Routing intelligente basato su contesto
   - Adattamento a nuovi tipi di messaggi

3. **Scalabilità**
   - Supporta molti agenti
   - Gestisce conflitti e priorità
   - Può aggregare messaggi simili

4. **Debugging**
   - Log chiari di tutte le comunicazioni
   - Tracciabilità delle decisioni
   - Possibilità di "ascoltare" le conversazioni

### Implementazione

#### Opzione 1: Message Broker con LLM Dedicato

```python
class MessageBroker:
    def __init__(self, llm_client: OllamaClient):
        self.llm = llm_client
        self.message_queue = asyncio.Queue()
        self.agents = {}  # Registered agents
    
    async def send_message(self, message: AgentMessage):
        """Send message through broker"""
        # LLM interprets and routes
        interpretation = await self.llm.interpret_message(message)
        # Route to appropriate agent(s)
        await self.route_message(message, interpretation)
    
    async def interpret_message(self, message: AgentMessage):
        """Use LLM to understand message intent and priority"""
        prompt = f"""
        Analyze this agent message and determine:
        1. Urgency (high/medium/low)
        2. Required action
        3. Which agent(s) should receive it
        4. How to format the response
        
        Message: {message.content}
        From: {message.from_agent}
        Type: {message.message_type}
        """
        # ... LLM call
```

#### Opzione 2: Direct LLM Communication

Agenti comunicano direttamente tramite LLM:

```python
class BackgroundAgent:
    async def communicate_with_main(self, content: Dict):
        """Send message to Main Agent via LLM"""
        prompt = f"""
        You are the Background Agent. You detected a contradiction.
        Communicate this to the Main Agent in a clear, actionable way.
        
        Contradiction: {content}
        
        Format your message as JSON with:
        - urgency: high/medium/low
        - action_required: what Main should do
        - user_message: how to present to user
        """
        response = await self.llm.generate(prompt)
        # Send to Main's message queue
        await main_agent.receive_message(response)
```

#### Opzione 3: Hybrid (Raccomandato)

- **Database** per persistenza e stato
- **LLM** per interpretazione e routing intelligente
- **Message Queue** per comunicazione real-time

### Considerazioni

**Pro:**
- Comunicazione più naturale e flessibile
- Possibilità di negoziazione tra agenti
- Adattamento a nuovi scenari senza hard-coding
- Debugging più facile (log delle "conversazioni")

**Contro:**
- Maggiore complessità
- Possibile latenza aggiuntiva (chiamate LLM)
- Costo computazionale maggiore
- Necessità di gestire errori LLM

### Prossimi Passi

1. **Fase 1: Prototipo**
   - Implementare MessageBroker base
   - Supportare comunicazione Main ↔ Background
   - Test con contraddizioni

2. **Fase 2: Estensione**
   - Aggiungere altri agenti (Event Monitor, Todo Manager)
   - Implementare negoziazione multi-turn
   - Aggiungere caching per ridurre chiamate LLM

3. **Fase 3: Ottimizzazione**
   - Fine-tuning del prompt per routing
   - Caching intelligente delle interpretazioni
   - Batch processing per ridurre latenza

## Domande Aperte

1. **Latenza**: Quanto è accettabile? (attualmente ~2-5s per controllo contraddizioni)
2. **Costo**: Quante chiamate LLM aggiuntive siamo disposti a fare?
3. **Complessità**: Vale la pena per i benefici?
4. **Alternativa**: Migliorare il sistema attuale (database + polling) invece?

## Raccomandazione

**Approccio Incrementale:**
1. Mantenere sistema attuale (database) come fallback
2. Aggiungere MessageBroker opzionale per comunicazioni avanzate
3. Usare LLM solo per routing/interpretazione, non per ogni messaggio
4. Valutare benefici dopo implementazione base

