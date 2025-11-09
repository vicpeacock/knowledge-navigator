# Architettura Multi-Agente con Orchestrazione

## Visione Generale

Sistema multi-agente dove:
- **Orchestrator** coordina e assegna ruoli
- **Event Handler** riceve eventi esterni e li distribuisce
- **Agenti Specializzati** lavorano in parallelo e si coordinano
- **Comunicazione** tramite Message Broker con protocolli standardizzati

## Framework Multi-Agente Esistenti

### Opzioni Principali

1. **LangGraph** (Anthropic/LangChain)
   - ✅ Grafo di stato per orchestrazione
   - ✅ Supporto nativo per multi-agenti
   - ✅ Integrazione con LLM
   - ⚠️ Richiede LangChain ecosystem

2. **AutoGen** (Microsoft)
   - ✅ Conversazioni multi-agente
   - ✅ Coordinamento intelligente
   - ✅ Supporto per diversi LLM
   - ⚠️ Più orientato a conversazioni che a task

3. **CrewAI** (CrewAI)
   - ✅ Agenti con ruoli e task
   - ✅ Orchestrazione automatica
   - ✅ Pianificazione collaborativa
   - ⚠️ Framework più nuovo, meno maturo

4. **Custom (Raccomandato per Knowledge Navigator)**
   - ✅ Controllo completo
   - ✅ Integrazione con architettura esistente
   - ✅ Ottimizzato per i nostri use case
   - ⚠️ Richiede più sviluppo

## Architettura Proposta

```
┌─────────────────────────────────────────────────────────────┐
│                    Event Sources                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Email   │  │ Calendar │  │ WhatsApp │  │  Chat    │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │              │              │         │
│       └─────────────┴──────────────┴──────────────┘         │
│                          │                                   │
│                          ▼                                   │
│              ┌──────────────────────┐                        │
│              │  Event Handler       │                        │
│              │  (Event Receiver)    │                        │
│              └──────────┬───────────┘                        │
│                         │                                     │
│                         ▼                                     │
│              ┌──────────────────────┐                        │
│              │   Orchestrator       │                        │
│              │   (Role Assigner)    │                        │
│              │   (Task Coordinator)│                        │
│              └──────────┬───────────┘                        │
│                         │                                     │
│         ┌───────────────┼───────────────┐                    │
│         │               │               │                    │
│         ▼               ▼               ▼                    │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐                 │
│  │ Integrity│   │   Main   │   │ Knowledge│                 │
│  │  Agent   │   │  Agent   │   │  Agent   │                 │
│  └──────────┘   └──────────┘   └──────────┘                 │
│         │               │               │                    │
│         └───────────────┼───────────────┘                    │
│                         │                                     │
│                         ▼                                     │
│              ┌──────────────────────┐                        │
│              │  Message Broker      │                        │
│              │  (Communication Hub) │                        │
│              └──────────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

## Componenti Principali

### 1. Event Handler (Event Receiver)

**Ruolo**: Riceve eventi da tutte le fonti esterne e li normalizza

```python
class EventHandler:
    """
    Riceve eventi da tutte le fonti e li normalizza in formato standard.
    Non decide cosa fare, solo riceve e normalizza.
    """
    
    async def receive_event(self, event: ExternalEvent):
        """Riceve evento esterno e lo normalizza"""
        normalized = self._normalize_event(event)
        await self.orchestrator.handle_event(normalized)
    
    def _normalize_event(self, event: ExternalEvent) -> NormalizedEvent:
        """Converte evento esterno in formato standard"""
        return NormalizedEvent(
            source=event.source,  # "email", "calendar", "chat", etc.
            type=event.type,      # "message_received", "event_starting", etc.
            content=event.content,
            metadata=event.metadata,
            timestamp=event.timestamp,
            priority=self._estimate_priority(event)
        )
```

**Eventi Supportati:**
- `chat_message`: Messaggio utente nella chat
- `email_received`: Nuova email arrivata
- `calendar_event`: Evento calendario (inizio, reminder, etc.)
- `whatsapp_message`: Messaggio WhatsApp
- `file_uploaded`: File caricato
- `system_event`: Eventi sistema (reminder, etc.)

### 2. Orchestrator (Role Assigner & Task Coordinator)

**Ruolo**: Decide quali agenti devono gestire l'evento e coordina task complessi

```python
class Orchestrator:
    """
    Coordina agenti, assegna ruoli, gestisce task complessi.
    Usa LLM per decisioni intelligenti su routing e coordinamento.
    """
    
    def __init__(self, llm_client: OllamaClient):
        self.llm = llm_client
        self.agents = {}  # Registry degli agenti disponibili
        self.message_broker = MessageBroker()
    
    async def handle_event(self, event: NormalizedEvent):
        """Decide quali agenti devono gestire l'evento"""
        
        # Usa LLM per decidere routing intelligente
        routing_decision = await self._decide_routing(event)
        
        # Assegna task agli agenti appropriati
        tasks = []
        for agent_role in routing_decision.required_agents:
            agent = self.agents[agent_role]
            task = agent.handle_event(event, routing_decision.context)
            tasks.append(task)
        
        # Esegui in parallelo se possibile
        if routing_decision.parallel:
            results = await asyncio.gather(*tasks)
        else:
            # Esegui sequenzialmente con dipendenze
            results = await self._execute_sequential(tasks, routing_decision.dependencies)
        
        # Coordina risultati se necessario
        if routing_decision.requires_coordination:
            await self._coordinate_results(results, event)
    
    async def _decide_routing(self, event: NormalizedEvent) -> RoutingDecision:
        """Usa LLM per decidere quali agenti devono gestire l'evento"""
        prompt = f"""
        Analyze this event and determine:
        1. Which agents should handle it (integrity, main, knowledge, etc.)
        2. Can they work in parallel or need coordination?
        3. What dependencies exist between agents?
        4. What context should each agent receive?
        
        Event: {event.type} from {event.source}
        Content: {event.content[:200]}
        Priority: {event.priority}
        
        Available agents:
        - integrity: Checks for contradictions in memory
        - main: Generates chat responses
        - knowledge: Extracts and indexes knowledge
        - todo: Manages todo list
        - event_monitor: Monitors external events
        
        Respond in JSON:
        {{
            "required_agents": ["agent1", "agent2"],
            "parallel": true/false,
            "dependencies": {{"agent2": ["agent1"]}},
            "context": {{"agent1": "...", "agent2": "..."}},
            "requires_coordination": true/false
        }}
        """
        response = await self.llm.generate(prompt)
        return RoutingDecision.parse(response)
```

### 3. Agenti Specializzati

#### 3.1 Integrity Agent

**Ruolo**: Verifica consistenza semantica della memoria

```python
class IntegrityAgent:
    """Verifica contraddizioni e consistenza nella memoria"""
    
    async def handle_event(self, event: NormalizedEvent, context: Dict) -> AgentResult:
        if event.type == "chat_message":
            # Controlla contraddizioni per ogni messaggio utente
            return await self.check_contradictions(event.content)
        elif event.type == "knowledge_extracted":
            # Controlla contraddizioni per nuova conoscenza
            return await self.check_contradictions(event.content)
        
    async def check_contradictions(self, content: str) -> AgentResult:
        # Usa SemanticIntegrityChecker esistente
        ...
```

#### 3.2 Main Agent (Chat Agent)

**Ruolo**: Genera risposte chat e gestisce interazioni utente

```python
class MainAgent:
    """Genera risposte chat e gestisce interazioni utente"""
    
    async def handle_event(self, event: NormalizedEvent, context: Dict) -> AgentResult:
        if event.type == "chat_message":
            # Genera risposta
            response = await self.generate_response(event.content, context)
            
            # Controlla se ci sono notifiche da mostrare
            notifications = context.get("notifications", [])
            if notifications:
                response.notifications = notifications
            
            return response
```

#### 3.3 Knowledge Agent

**Ruolo**: Estrae e indicizza conoscenza dalle conversazioni

```python
class KnowledgeAgent:
    """Estrae e indicizza conoscenza dalle conversazioni"""
    
    async def handle_event(self, event: NormalizedEvent, context: Dict) -> AgentResult:
        if event.type == "chat_message":
            # Estrae conoscenza dalla conversazione
            knowledge = await self.extract_knowledge(event.content, context)
            
            # Indicizza in memoria long-term
            await self.index_knowledge(knowledge)
            
            return AgentResult(knowledge_items=knowledge)
```

#### 3.4 Event Monitor Agent

**Ruolo**: Monitora eventi esterni (email, calendario, etc.)

```python
class EventMonitorAgent:
    """Monitora eventi esterni e li segnala"""
    
    async def handle_event(self, event: NormalizedEvent, context: Dict) -> AgentResult:
        if event.type == "email_received":
            # Valuta se email è importante
            importance = await self.evaluate_importance(event.content)
            
            if importance > threshold:
                # Crea notifica per Main Agent
                await self.message_broker.send(
                    to="main",
                    message=NotificationMessage(
                        type="email_important",
                        content=event.content,
                        priority="high"
                    )
                )
```

### 4. Message Broker (Communication Hub)

**Ruolo**: Gestisce comunicazione tra agenti

```python
class MessageBroker:
    """
    Gestisce comunicazione asincrona tra agenti.
    Supporta:
    - Publish/Subscribe
    - Request/Response
    - Broadcast
    - Queue con priorità
    """
    
    def __init__(self):
        self.subscribers = {}  # agent_id -> callback
        self.message_queue = asyncio.Queue()
        self.pending_requests = {}  # request_id -> future
    
    async def send(self, to: str, message: AgentMessage):
        """Invia messaggio a agente specifico"""
        if to in self.subscribers:
            await self.subscribers[to](message)
        else:
            # Queue per agente non disponibile
            await self.message_queue.put((to, message))
    
    async def broadcast(self, message: AgentMessage, filter_fn=None):
        """Invia messaggio a tutti gli agenti (opzionalmente filtrati)"""
        for agent_id, callback in self.subscribers.items():
            if filter_fn is None or filter_fn(agent_id):
                await callback(message)
    
    async def request(self, to: str, message: AgentMessage, timeout: float = 30.0) -> AgentMessage:
        """Richiesta con risposta (request/response pattern)"""
        request_id = str(uuid.uuid4())
        message.request_id = request_id
        
        future = asyncio.Future()
        self.pending_requests[request_id] = future
        
        await self.send(to, message)
        
        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            del self.pending_requests[request_id]
            raise
```

### 5. Agent Base Class

**Ruolo**: Classe base per tutti gli agenti

```python
class Agent(ABC):
    """Classe base per tutti gli agenti"""
    
    def __init__(
        self,
        agent_id: str,
        role: str,
        llm_client: Optional[OllamaClient] = None,
        message_broker: Optional[MessageBroker] = None
    ):
        self.agent_id = agent_id
        self.role = role
        self.llm = llm_client
        self.broker = message_broker
        self.capabilities = []  # Cosa può fare questo agente
    
    @abstractmethod
    async def handle_event(self, event: NormalizedEvent, context: Dict) -> AgentResult:
        """Gestisce evento assegnato"""
        pass
    
    async def send_message(self, to: str, message: AgentMessage):
        """Invia messaggio ad altro agente"""
        await self.broker.send(to, message)
    
    async def request_help(self, question: str, from_agent: str) -> AgentMessage:
        """Chiede aiuto ad altro agente"""
        message = AgentMessage(
            from_agent=self.agent_id,
            to_agent=from_agent,
            type="request_help",
            content={"question": question},
            requires_response=True
        )
        return await self.broker.request(from_agent, message)
```

## Flusso di Esecuzione

### Esempio 1: Messaggio Chat Utente

```
1. User invia "Mi piace la pastasciutta"
   ↓
2. Event Handler riceve evento
   Event: {type: "chat_message", source: "chat", content: "..."}
   ↓
3. Orchestrator decide routing
   LLM analizza: "Richiede Main Agent (risposta) + Integrity Agent (controllo) + Knowledge Agent (estrazione)"
   Decisione: {agents: ["main", "integrity", "knowledge"], parallel: true}
   ↓
4. Agenti eseguono in parallelo:
   - Main Agent: Genera risposta "Capito"
   - Integrity Agent: Controlla contraddizioni (in background)
   - Knowledge Agent: Estrae "L'utente ama la pastasciutta"
   ↓
5. Orchestrator coordina risultati
   - Main Agent risponde immediatamente
   - Integrity Agent completa dopo, invia notifica se contraddizione
   - Knowledge Agent indicizza conoscenza
   ↓
6. Risultato finale inviato al frontend
```

## Sistema di Notifiche Coordinato

### Notification Center (hub in-memory)

- Ogni nodo/agente produce notifiche strutturate (`Notification`) con:
  - `type`, `priority`, `channel`, `tags`
  - `source` (`agent`, `feature`, `reference_id`)
  - `payload` (`title`, `message`, `summary`, `data`, `actions`)
- Le notifiche sono normalizzate da `NotificationCenter` e rese disponibili in forma serializzabile (`to_transport_dict`).
- Le priorità (`critical`, `high`, `medium`, `low`, `info`) definiscono i canali:
  - `blocking`: blocca la UI (es. servizi critici down)
  - `immediate`: feed in-session (es. aggiornamenti pianificazione)
  - `async`: inbox da consultare successivamente
  - `digest`: riepiloghi periodici
  - `log`: solo telemetria interna

### Cooperazione tra agenti

| Tipo evento                           | Agente (producer)                  | Contenuto notifica                                               | Priorità/canale            |
|--------------------------------------|------------------------------------|------------------------------------------------------------------|----------------------------|
| Stato pianificazione                 | Planner / Tool Loop                | Fasi del piano, richiesta conferme, esito step                   | `medium/high` → `immediate`|
| Contraddizioni / anomalie servizi    | Integrity Checker, Service Health  | Disallineamenti dati, servizi offline                            | `high/critical` → `blocking`|
| Aggiornamenti conoscenza             | Knowledge / Learner                | Nuove fonti, gap informativi, suggerimenti di studio             | `medium` → `async/digest`  |
| Eventi calendario e comunicazioni    | Calendar Sentinel, Communication Watcher | Inviti, email urgenti, deleghe completate                         | `high/medium` → `immediate/async` |
| Benessere e routine                  | Wellbeing Agent (futuro)           | Reminder pause, deviazioni dalla routine                         | `low` → `digest/async`     |

### Pipeline nel grafo LangGraph

1. Ogni nodo (`tool_loop`, `knowledge_agent`, `integrity_agent`, ecc.) pubblica notifiche nel `NotificationCenter`.
2. `notification_collector_node` consolida le notifiche e produce due viste:
   - `notifications` (tutte)
   - `high_urgency_notifications` (priorità ≥ `high`)
3. `response_formatter_node` serializza il conteggio e la lista urgente dentro `ChatResponse`.
4. Frontend/UI:
   - Mostra badge con `notifications_count`
   - Pannello "Status Updates" popolato con `high_urgency_notifications`
   - Eventuali canali `blocking` attivano la health-gate esistente

### Estensioni previste

- **Persistenza**: scrivere notifiche critiche nel DB per audit e ripristino dopo refresh.
- **Routing canali**: mappare `channel` su diversi surface (toast, inbox, email).
- **Azioni suggerite**: `NotificationAction` consente di offrire bottoni contestuali (es. “Apri email”, “Conferma delega”).
- **Policy utente**: preferenze personalizzate per silenziare categorie/tag.

### Esempio 2: Contraddizione Rilevata

```
1. Integrity Agent rileva contraddizione
   "L'utente ama pastasciutta" vs "L'utente detesta ravioli"
   ↓
2. Integrity Agent invia messaggio a Orchestrator
   Message: {type: "contradiction_detected", content: {...}, priority: "high"}
   ↓
3. Orchestrator decide azione
   LLM analizza: "Alta confidenza, richiede chiarimento utente"
   Decisione: {action: "notify_user", format: "interactive", agent: "main"}
   ↓
4. Orchestrator assegna task a Main Agent
   Task: "Mostra notifica interattiva all'utente"
   ↓
5. Main Agent formatta notifica
   "⚠️ Contraddizione rilevata: Quale informazione è corretta? A/B/C/D"
   ↓
6. Notifica inviata al frontend via WebSocket/SSE
```

### Esempio 3: Email Importante

```
1. Email Monitor rileva email importante
   Event: {type: "email_received", source: "email", priority: "high"}
   ↓
2. Event Handler normalizza evento
   ↓
3. Orchestrator decide routing
   LLM analizza: "Email importante, richiede notifica immediata"
   Decisione: {agents: ["event_monitor", "main"], parallel: false}
   ↓
4. Event Monitor Agent valuta importanza
   Result: {importance: 0.9, action: "notify_immediately"}
   ↓
5. Main Agent genera notifica
   "📧 Email importante da [mittente]: [oggetto]"
   ↓
6. Notifica inviata al frontend
```

## Protocolli di Comunicazione

### Agent Message Format

```python
class AgentMessage(BaseModel):
    """Formato standard per messaggi tra agenti"""
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    from_agent: str
    to_agent: Optional[str] = None  # None = broadcast
    type: str  # "event", "request", "response", "notification", "error"
    content: Dict[str, Any]
    priority: str = "medium"  # "low", "medium", "high", "urgent"
    requires_response: bool = False
    request_id: Optional[str] = None  # Per request/response
    context: Dict[str, Any] = {}  # Contesto aggiuntivo
    timestamp: datetime = Field(default_factory=datetime.now)
```

### Event Types

```python
class EventType(str, Enum):
    # Chat
    CHAT_MESSAGE = "chat_message"
    CHAT_RESPONSE = "chat_response"
    
    # Email
    EMAIL_RECEIVED = "email_received"
    EMAIL_IMPORTANT = "email_important"
    
    # Calendar
    CALENDAR_EVENT_STARTING = "calendar_starting"
    CALENDAR_REMINDER = "calendar_reminder"
    
    # Knowledge
    KNOWLEDGE_EXTRACTED = "knowledge_extracted"
    KNOWLEDGE_INDEXED = "knowledge_indexed"
    
    # Integrity
    CONTRADICTION_DETECTED = "contradiction_detected"
    INTEGRITY_CHECK_COMPLETE = "integrity_check_complete"
    
    # System
    SYSTEM_EVENT = "system_event"
    AGENT_REQUEST = "agent_request"
    AGENT_RESPONSE = "agent_response"
```

## Implementazione

### Fase 1: Core Infrastructure (Settimana 1-2)

1. **Message Broker**
   - Implementare classe base
   - Supporto per send/broadcast/request
   - Queue con priorità

2. **Orchestrator**
   - Implementare routing base
   - Supporto per decisioni LLM
   - Gestione task paralleli/sequenziali

3. **Event Handler**
   - Normalizzazione eventi
   - Integrazione con fonti esistenti

### Fase 2: Agenti Base (Settimana 3-4)

1. **Refactoring Agenti Esistenti**
   - Convertire BackgroundAgent → IntegrityAgent
   - Convertire chat handler → MainAgent
   - Convertire ConversationLearner → KnowledgeAgent

2. **Agent Base Class**
   - Classe astratta comune
   - Metodi helper per comunicazione

### Fase 3: Coordinamento Avanzato (Settimana 5-6)

1. **Task Complessi**
   - Supporto per dipendenze tra agenti
   - Coordinamento risultati
   - Gestione errori e retry

2. **Proattività**
   - Event Monitor Agent
   - Notifiche real-time
   - Priorità e filtri

## Vantaggi Architettura Multi-Agente

1. **Scalabilità**: Facile aggiungere nuovi agenti
2. **Parallelismo**: Agenti lavorano in parallelo quando possibile
3. **Coordinamento**: Orchestrator gestisce task complessi
4. **Flessibilità**: Agenti possono comunicare direttamente
5. **Proattività**: Event Handler permette reazioni immediate
6. **Manutenibilità**: Agenti isolati, facili da testare

## Considerazioni

### Performance
- Orchestrator usa LLM per routing → possibile latenza
- **Soluzione**: Cache decisioni comuni, fallback a regole

### Complessità
- Sistema più complesso del monolitico attuale
- **Soluzione**: Implementazione incrementale, test estensivi

### Debugging
- Più difficile tracciare flussi complessi
- **Soluzione**: Logging dettagliato, tracing delle comunicazioni

## Prossimi Passi

1. **Valutare Framework**: Testare LangGraph vs Custom
2. **Prototipo**: Implementare Orchestrator + 2 agenti base
3. **Migrazione Incrementale**: Convertire agenti esistenti uno alla volta
4. **Testing**: Test estensivi per coordinamento e comunicazione

### Stato della pipeline LangGraph

- [x] Pianificazione con LLM dedicato + logging nel pannello status
- [x] Persistenza piano (`pending_plan` in session metadata) e resume su conferma
- [ ] Loop tool fully migrated (attuale: mix pipeline legacy + LangGraph)

### Approccio Pianificazione

1. Analizza la richiesta con planner dedicato; se è semplice, `needs_plan=false`.
2. Se servono tool o conferme, `needs_plan=true` con JSON di step (`tool/respond/wait_user`).
3. Step `wait_user` bloccano la pipeline finché l’utente conferma.
4. Step `tool` invocano `ToolManager`; i risultati vengono sintetizzati dall’LLM principale (`summarize_plan_results`).
5. Piano completato → notifiche `completed`; in caso di sospensione → `waiting_confirmation`.

### Glossario Stato/Node

- **planner_client**: LLM dedicato alla generazione del piano.

### Logging / Monitoring

- `planning.generated`, `planning.waiting_confirmation`, `planning.completed`       
- `planning.analysis`: risultato del planner LLM (reason + bozza step)

### TODO / Evolutions

- Caching planner / fallback multi-modello
- Pianificazione come nodo separato nel grafo o agente indipendente

