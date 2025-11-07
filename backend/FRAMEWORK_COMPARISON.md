# Confronto Framework Multi-Agente per Knowledge Navigator

## Framework Analizzati

1. **LangGraph** (LangChain/Anthropic)
2. **AutoGen** (Microsoft Research)
3. **CrewAI** (CrewAI)
4. **Google ADK** (Agent Development Kit)
5. **Semantic Kernel** (Microsoft)
6. **Pydantic AI**
7. **Google A2A Protocol**
8. **Custom Solution**

---

## 1. LangGraph

### Caratteristiche

- **Tipo**: Grafo di stato per orchestrazione workflow
- **Linguaggio**: Python
- **Ecosistema**: LangChain (molto maturo, grande community)
- **Paradigma**: State-based workflow con nodi e archi
- **LLM Support**: Tutti (OpenAI, Anthropic, Ollama, etc.)

### Architettura

```python
from langgraph.graph import StateGraph, END

# Definisci stato condiviso
class AgentState(TypedDict):
    messages: List[Message]
    next_agent: str
    context: Dict

# Crea grafo
workflow = StateGraph(AgentState)

# Aggiungi nodi (agenti)
workflow.add_node("event_handler", event_handler_node)
workflow.add_node("orchestrator", orchestrator_node)
workflow.add_node("integrity_agent", integrity_agent_node)
workflow.add_node("main_agent", main_agent_node)

# Definisci archi (transizioni)
workflow.add_edge("event_handler", "orchestrator")
workflow.add_conditional_edges(
    "orchestrator",
    route_to_agents,  # Funzione che decide prossimo nodo
    {"integrity": "integrity_agent", "main": "main_agent", END: END}
)

# Compila e esegui
app = workflow.compile()
result = await app.ainvoke({"messages": [user_message]})
```

### Pro

✅ **Maturità**: Framework molto maturo, community grande
✅ **Flessibilità**: Grafo di stato permette workflow complessi
✅ **Osservabilità**: Built-in support per tracing e monitoring
✅ **Integrazione LLM**: Supporto nativo per Ollama
✅ **State Management**: Gestione stato condiviso tra agenti
✅ **Conditional Routing**: Routing intelligente basato su stato
✅ **Persistenza**: Supporto per checkpoint e recovery
✅ **Streaming**: Supporto per streaming di risposte

### Contro

⚠️ **Complessità**: Curva di apprendimento per grafi complessi
⚠️ **LangChain Dependency**: Richiede ecosistema LangChain (può essere pesante)
⚠️ **Event-Driven**: Non nativamente event-driven (deve essere implementato)
⚠️ **Overhead**: Può essere overkill per use case semplici

### Integrazione con Knowledge Navigator

**Compatibilità**: ⭐⭐⭐⭐ (4/5)
- Supporta Ollama nativamente
- Può integrare agenti esistenti come nodi
- Richiede refactoring per adattare a grafo di stato

**Esempio Integrazione**:
```python
# Convertire BackgroundAgent in nodo LangGraph
async def integrity_agent_node(state: AgentState):
    agent = IntegrityAgent(...)
    result = await agent.check_contradictions(state["messages"][-1])
    state["integrity_result"] = result
    return state
```

---

## 2. AutoGen (Microsoft Research)

### Caratteristiche

- **Tipo**: Framework conversazionale multi-agente
- **Linguaggio**: Python
- **Ecosistema**: Microsoft Research (open-source, attivo)
- **Paradigma**: Conversazioni tra agenti con ruoli specializzati
- **LLM Support**: OpenAI, Azure, Ollama (con adapter)

### Architettura

```python
from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager

# Definisci agenti con ruoli
integrity_agent = AssistantAgent(
    name="integrity_checker",
    system_message="You are an integrity checker. Check for contradictions...",
    llm_config={"model": "ollama/phi3:mini"}
)

main_agent = AssistantAgent(
    name="main_chat",
    system_message="You are the main chat assistant...",
    llm_config={"model": "ollama/gpt-oss:20b"}
)

# Crea group chat
groupchat = GroupChat(
    agents=[integrity_agent, main_agent],
    messages=[],
    max_round=10
)

manager = GroupChatManager(groupchat=groupchat, llm_config={...})

# Avvia conversazione
user_proxy.initiate_chat(
    manager,
    message="User message here"
)
```

### Pro

✅ **Conversazioni Naturali**: Agenti "parlano" tra loro
✅ **Ruoli Specializzati**: Facile definire agenti con ruoli specifici
✅ **Coordinamento Automatico**: GroupChatManager coordina automaticamente
✅ **Human-in-the-Loop**: Supporto nativo per intervento umano
✅ **Tool Calling**: Supporto per tool/function calling
✅ **Code Execution**: Supporto per esecuzione codice Python

### Contro

⚠️ **Orientato Conversazioni**: Più adatto a conversazioni che a task asincroni
⚠️ **Event-Driven Limitato**: Non nativamente event-driven
⚠️ **Overhead Conversazionale**: Ogni interazione passa attraverso LLM
⚠️ **Ollama Support**: Richiede adapter personalizzato (non nativo)

### Integrazione con Knowledge Navigator

**Compatibilità**: ⭐⭐⭐ (3/5)
- Richiede adapter per Ollama
- Paradigma conversazionale non perfetto per event-driven
- Può essere lento (ogni step è una chiamata LLM)

**Esempio Integrazione**:
```python
# Adapter per Ollama
class OllamaLLMConfig:
    def __init__(self, model: str, base_url: str):
        self.model = model
        self.base_url = base_url

# Convertire agenti esistenti
integrity_agent = AssistantAgent(
    name="integrity",
    llm_config=OllamaLLMConfig("phi3:mini", "http://localhost:11435")
)
```

---

## 3. CrewAI

### Caratteristiche

- **Tipo**: Framework per agenti con ruoli e task
- **Linguaggio**: Python
- **Ecosistema**: CrewAI (framework più nuovo, community in crescita)
- **Paradigma**: Agenti con ruoli, task, e pianificazione collaborativa
- **LLM Support**: OpenAI, Anthropic, Ollama (con adapter)

### Architettura

```python
from crewai import Agent, Task, Crew

# Definisci agenti con ruoli
integrity_agent = Agent(
    role='Integrity Checker',
    goal='Check for contradictions in memory',
    backstory='You are an expert at detecting logical contradictions...',
    llm=OllamaLLM(model="phi3:mini")
)

main_agent = Agent(
    role='Chat Assistant',
    goal='Generate helpful responses to user',
    backstory='You are a helpful AI assistant...',
    llm=OllamaLLM(model="gpt-oss:20b")
)

# Definisci task
integrity_task = Task(
    description='Check if user message contradicts existing memory',
    agent=integrity_agent
)

chat_task = Task(
    description='Generate response to user message',
    agent=main_agent
)

# Crea crew e esegui
crew = Crew(
    agents=[integrity_agent, main_agent],
    tasks=[integrity_task, chat_task],
    verbose=True
)

result = crew.kickoff(inputs={"user_message": "..."})
```

### Pro

✅ **Ruoli Chiari**: Agenti con ruoli e goal ben definiti
✅ **Task-Based**: Approccio basato su task, facile da capire
✅ **Pianificazione**: Pianificazione collaborativa automatica
✅ **Tool Integration**: Supporto per tool esterni
✅ **Memory**: Supporto per memoria condivisa tra agenti

### Contro

⚠️ **Maturità**: Framework più nuovo, meno maturo
⚠️ **Documentazione**: Documentazione meno completa
⚠️ **Ollama Support**: Richiede adapter personalizzato
⚠️ **Event-Driven**: Non nativamente event-driven
⚠️ **Overhead**: Può essere pesante per task semplici

### Integrazione con Knowledge Navigator

**Compatibilità**: ⭐⭐⭐ (3/5)
- Richiede adapter per Ollama
- Paradigma task-based può essere rigido
- Meno maturo degli altri

---

## 4. Google ADK (Agent Development Kit)

### Caratteristiche

- **Tipo**: Framework completo per sviluppo agenti
- **Linguaggio**: Python
- **Ecosistema**: Google (open-source, in sviluppo attivo)
- **Paradigma**: Agenti autonomi con orchestrazione gerarchica
- **LLM Support**: Google Gemini, altri (Ollama non confermato)

### Pro

✅ **Completo**: Include orchestrazione, deployment, testing
✅ **Gerarchico**: Supporto per composizione gerarchica di agenti
✅ **Tool Integration**: Integrazione strumenti esterni
✅ **Deployment**: Supporto per deployment

### Contro

⚠️ **Google-Centric**: Orientato a Google Cloud/Gemini
⚠️ **Ollama Support**: Non chiaro se supporta Ollama
⚠️ **Maturità**: Framework relativamente nuovo
⚠️ **Documentazione**: Meno documentazione pubblica

### Integrazione con Knowledge Navigator

**Compatibilità**: ⭐⭐ (2/5)
- Orientato a Google ecosystem
- Supporto Ollama incerto
- Meno adatto per il nostro caso

---

## 5. Semantic Kernel (Microsoft)

### Caratteristiche

- **Tipo**: Framework per orchestrazione agenti AI
- **Linguaggio**: Python, C#
- **Ecosistema**: Microsoft (maturità media)
- **Paradigma**: Orchestrazione multi-agente con competenze specializzate
- **LLM Support**: Azure OpenAI, OpenAI, Ollama (con adapter)

### Pro

✅ **Orchestrazione**: Orchestrazione multi-agente nativa
✅ **Competenze**: Agenti con competenze specializzate
✅ **Microsoft Ecosystem**: Integrazione con Azure
✅ **Multi-Language**: Supporto Python e C#

### Contro

⚠️ **Azure-Centric**: Orientato a Microsoft Azure
⚠️ **Ollama Support**: Richiede adapter
⚠️ **Complessità**: Framework complesso
⚠️ **Documentazione**: Documentazione principalmente Azure-focused

### Integrazione con Knowledge Navigator

**Compatibilità**: ⭐⭐⭐ (3/5)
- Richiede adapter per Ollama
- Orientato a Azure
- Complessità elevata

---

## 6. Pydantic AI

### Caratteristiche

- **Tipo**: Framework per applicazioni/agent GenAI data-centriche
- **Linguaggio**: Python
- **Ecosistema**: Team Pydantic (nuovo ma in rapida evoluzione)
- **Paradigma**: Prompt + validazione strutturata dei dati
- **LLM Support**: Multi-provider (OpenAI, Anthropic, Gemini, Bedrock, Vertex, custom)

### Pro

✅ **Model-Agnostic**: Supporta molti provider LLM out-of-the-box  
✅ **Data Validation**: Tipizzazione/validazione rigorosa con Pydantic  
✅ **Observability**: Integrazione stretta con Pydantic Logfire (tracing, costi)  
✅ **Developer Experience**: API simile a FastAPI, facile integrazione Python  
✅ **Extensibility**: Possibilità di definire modelli custom e tool personali

### Contro

⚠️ **Multi-Agent Limitato**: Non fornisce orchestrazione/coordination nativa tra agenti  
⚠️ **Event-Driven**: Nessun supporto diretto, da implementare manualmente  
⚠️ **Maturità**: Prodotto relativamente nuovo, community ancora piccola  
⚠️ **Tooling**: Dipendenza da Logfire per osservabilità avanzata (servizio separato)

### Integrazione con Knowledge Navigator

**Compatibilità**: ⭐⭐⭐ (3/5)  
- Ottimo per definire agenti singoli con contratti dati chiari  
- Necessario implementare a parte orchestrazione/event handling  
- Può fungere da layer di validazione/observability sopra una soluzione esistente

---

## 7. Google A2A (Agent-to-Agent Protocol)

### Caratteristiche

- **Tipo**: Protocollo aperto di comunicazione tra agenti AI
- **Linguaggio**: Agnostico (specifica HTTP/SSE/JSON-RPC)
- **Ecosistema**: Google (donato alla Linux Foundation con supporto AWS, Cisco, Microsoft, Salesforce, SAP, ServiceNow)
- **Paradigma**: Task-oriented messaging, discovery & negotiation
- **LLM Support**: Indipendente dal modello (focus su interoperabilità)

### Pro

✅ **Interoperabilità**: Standard aperto per comunicazione cross-vendor  
✅ **Discovery**: Agent Card JSON per pubblicare capacità/endpoint  
✅ **Task Lifecycle**: Gestione strutturata dei task (creazione, aggiornamento, completamento)  
✅ **Security**: Progettato con autenticazione/autorizzazione enterprise  
✅ **Multimodal**: Supporto per contenuti testo/audio/video, allegati  
✅ **Ecosistema**: Sostenuto da Linux Foundation → roadmap condivisa

### Contro

⚠️ **Non è un Framework**: Fornisce protocollo, ma non orchestrazione/tooling  
⚠️ **Implementazione Necessaria**: Serve costruire agenti/servizi che parlano A2A  
⚠️ **Adoption**: Standard nuovo, tooling ancora in costruzione  
⚠️ **Complexity**: Richiede gestione endpoints, security, task registry

### Integrazione con Knowledge Navigator

**Compatibilità**: ⭐⭐⭐ (3/5)  
- Utile se vogliamo interoperare con agenti esterni o vendor diversi  
- Può diventare layer di comunicazione per orchestratore personalizzato  
- Richiede investimento per implementare spec (Agent Card, task API, SSE)  
- Non sostituisce un framework di orchestrazione interno

---

## 8. Custom Solution

### Caratteristiche

- **Tipo**: Framework personalizzato
- **Linguaggio**: Python
- **Ecosistema**: Controllo completo
- **Paradigma**: Event-driven, orchestrator-based
- **LLM Support**: Qualsiasi (Ollama nativo)

### Pro

✅ **Controllo Completo**: Design ottimizzato per Knowledge Navigator
✅ **Ollama Native**: Integrazione nativa con Ollama
✅ **Event-Driven**: Nativamente event-driven
✅ **Leggero**: Nessun overhead di framework generici
✅ **Flessibilità**: Facile adattare a esigenze specifiche

### Contro

⚠️ **Sviluppo**: Richiede sviluppo da zero
⚠️ **Manutenzione**: Responsabilità completa di manutenzione
⚠️ **Testing**: Nessun framework di test pre-costruito
⚠️ **Community**: Nessuna community esterna

---

## Confronto Dettagliato

| Framework | Maturità | Ollama Support | Event-Driven | Orchestrazione | Learning Curve | Raccomandazione |
|-----------|----------|----------------|--------------|----------------|----------------|-----------------|
| **LangGraph** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Media | ⭐⭐⭐⭐ |
| **AutoGen** | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | Media | ⭐⭐⭐ |
| **CrewAI** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | Bassa | ⭐⭐⭐ |
| **Google ADK** | ⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐ | Alta | ⭐⭐ |
| **Semantic Kernel** | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | Alta | ⭐⭐ |
| **Pydantic AI** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | Bassa | ⭐⭐⭐ |
| **Google A2A** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | Alta | ⭐⭐ |
| **Custom** | N/A | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | N/A | ⭐⭐⭐⭐ |

---

## Raccomandazione per Knowledge Navigator

### 🏆 Opzione 1: LangGraph (Raccomandato)

**Perché:**
1. ✅ **Maturità**: Framework molto maturo e stabile
2. ✅ **Ollama Support**: Supporto nativo per Ollama
3. ✅ **Flessibilità**: Grafo di stato permette workflow complessi
4. ✅ **Event-Driven**: Può essere adattato per event-driven
5. ✅ **Community**: Grande community, molti esempi
6. ✅ **Osservabilità**: Built-in tracing e monitoring

**Adattamento Necessario:**
- Convertire agenti esistenti in nodi LangGraph
- Implementare event handler come entry point del grafo
- Usare conditional edges per routing intelligente

**Esempio Architettura LangGraph**:
```python
# Event Handler → Orchestrator → Agenti (paralleli/sequenziali)
workflow = StateGraph(AgentState)
workflow.add_node("event_handler", handle_external_event)
workflow.add_node("orchestrator", decide_routing)
workflow.add_node("integrity", integrity_check)
workflow.add_node("main", generate_response)
workflow.add_node("knowledge", extract_knowledge)

# Routing condizionale basato su decisione orchestrator
workflow.add_conditional_edges(
    "orchestrator",
    route_based_on_decision,
    {
        "parallel": ["integrity", "main", "knowledge"],
        "sequential": ["integrity", "main"],
        "main_only": "main"
    }
)
```

### 🥈 Opzione 2: Custom Solution (Alternativa)

**Perché:**
1. ✅ **Controllo Completo**: Design ottimizzato per Knowledge Navigator
2. ✅ **Event-Driven Native**: Nativamente event-driven
3. ✅ **Leggero**: Nessun overhead
4. ✅ **Ollama Native**: Integrazione perfetta con Ollama

**Svantaggi:**
- Richiede più sviluppo
- Nessuna community esterna
- Manutenzione completa

**Quando Scegliere:**
- Se LangGraph risulta troppo complesso
- Se hai bisogno di controllo totale
- Se vuoi evitare dipendenze esterne

---

## Piano di Implementazione con LangGraph

### Fase 1: Setup Base (Settimana 1)

```python
# Installazione
pip install langgraph langchain langchain-community

# Setup base
from langgraph.graph import StateGraph, END
from langchain_community.llms import Ollama

# Configurazione Ollama
llm_main = Ollama(model="gpt-oss:20b", base_url="http://localhost:11434")
llm_background = Ollama(model="phi3:mini", base_url="http://localhost:11435")
```

### Fase 2: Convertire Agenti Esistenti (Settimana 2-3)

```python
# Convertire BackgroundAgent → Nodo LangGraph
async def integrity_agent_node(state: AgentState):
    agent = IntegrityAgent(
        memory_manager=state["memory"],
        db=state["db"],
        ollama_client=llm_background
    )
    result = await agent.check_contradictions(
        state["current_message"]
    )
    state["integrity_result"] = result
    return state
```

### Fase 3: Orchestrator con LangGraph (Settimana 4)

```python
# Orchestrator come nodo con routing intelligente
async def orchestrator_node(state: AgentState):
    # Usa LLM per decidere routing
    decision = await llm_main.ainvoke(
        f"Decide which agents should handle: {state['event']}"
    )
    state["routing_decision"] = parse_decision(decision)
    return state

# Conditional routing
def route_to_agents(state: AgentState):
    decision = state["routing_decision"]
    if decision["parallel"]:
        return ["integrity", "main", "knowledge"]
    elif decision["needs_integrity"]:
        return ["integrity", "main"]
    else:
        return "main"
```

### Fase 4: Event Handler Integration (Settimana 5)

```python
# Event Handler come entry point
async def event_handler_node(state: AgentState):
    event = state["incoming_event"]
    normalized = normalize_event(event)
    state["event"] = normalized
    return state

# Grafo completo
workflow = StateGraph(AgentState)
workflow.add_node("event_handler", event_handler_node)
workflow.add_node("orchestrator", orchestrator_node)
workflow.add_node("integrity", integrity_agent_node)
workflow.add_node("main", main_agent_node)
workflow.add_node("knowledge", knowledge_agent_node)

workflow.set_entry_point("event_handler")
workflow.add_edge("event_handler", "orchestrator")
workflow.add_conditional_edges("orchestrator", route_to_agents)
workflow.add_edge("main", END)  # Main è sempre l'ultimo
```

---

## Conclusione

**Raccomandazione Finale**: **LangGraph**

**Motivi:**
1. Framework maturo e stabile
2. Supporto nativo per Ollama
3. Flessibilità per workflow complessi
4. Grande community e documentazione
5. Osservabilità built-in
6. Può essere adattato per event-driven

**Prossimi Passi:**
1. Installare LangGraph e testare integrazione base
2. Convertire un agente esistente (IntegrityAgent) in nodo LangGraph
3. Testare workflow semplice (event → orchestrator → agent)
4. Valutare performance e complessità
5. Decidere se procedere con LangGraph o custom

**Alternative da Considerare:**
- Se LangGraph risulta troppo complesso → Custom Solution
- Se serve più controllo → Custom Solution
- Se preferisci conversazioni → AutoGen (ma meno adatto)

