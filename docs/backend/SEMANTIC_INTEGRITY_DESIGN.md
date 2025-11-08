# Design: Controllo Integrità Semantica e Sistema di Notifiche Proattive

## Obiettivo

Rilevare contraddizioni nella memoria long-term quando vengono aggiunte nuove conoscenze e implementare un sistema di notifiche proattive. Esempio:
- Memoria esistente: "L'utente è nato il 12 luglio"
- Nuova conoscenza: "Il compleanno dell'utente è il 15 agosto"
- **Contraddizione rilevata**: Date diverse per la stessa informazione
- **Notifica proattiva**: L'assistente informa l'utente nella prossima interazione

## Approccio Proposto

### 1. **Architettura: Agente Background + Servizio Dedicato**

#### 1.1. Agente Background per "Pensiero Autonomo"

Creare un nuovo servizio `BackgroundAgent` che gestisce:
- **Controllo integrità semantica** (contraddizioni nella memoria)
- **Eventi esterni** (email, calendario, WhatsApp - da implementare)
- **Consultazione todo list** (da implementare)
- **Altri controlli proattivi** (da estendere)

**Caratteristiche**:
- Esegue in background (non blocca le risposte)
- Analisi esaustiva (può controllare tutte le memorie simili)
- Genera notifiche che vengono gestite dal sistema di notifiche

#### 1.2. Servizio Controllo Integrità

Creare un servizio `SemanticIntegrityChecker` che:
- Viene chiamato dall'agente background dopo l'indicizzazione
- Usa una combinazione di tecniche per rilevare contraddizioni
- Restituisce informazioni sulla contraddizione con livello di urgenza
- **Sempre chiede all'utente** per le contraddizioni (non decide autonomamente)

### 2. **Strategia di Rilevamento (Multi-Livello)**

#### Livello 1: Similarità Semantica + Estrazione Entità
- **Quando**: Prima di salvare una nuova memoria
- **Come**:
  1. Cerca memorie simili usando embedding (similarità > 0.7)
  2. Estrai entità chiave da entrambe le memorie (date, numeri, nomi, valori)
  3. Confronta le entità per trovare discrepanze

**Esempio**:
```
Memoria 1: "L'utente è nato il 12 luglio 1990"
Memoria 2: "Il compleanno è il 15 agosto"
→ Entità estratte: date (12/07 vs 15/08) → CONTRADDIZIONE
```

#### Livello 2: LLM-Based Contradiction Detection
- **Quando**: Se il Livello 1 trova memorie simili con entità diverse
- **Come**: Usa l'LLM per analizzare se le memorie si contraddicono semanticamente

**Prompt esempio**:
```
Analizza queste due memorie e determina se si contraddicono:

Memoria 1: "[FACT] L'utente è nato il 12 luglio 1990"
Memoria 2: "[FACT] Il compleanno dell'utente è il 15 agosto"

Le memorie si contraddicono? (sì/no)
Se sì, quale informazione è corretta? (memoria 1, memoria 2, o entrambe potrebbero essere corrette)
Motivazione: [spiegazione]
```

#### Livello 3: Pattern Matching Specifici
- **Quando**: Per tipi di conoscenza comuni (date, numeri, preferenze)
- **Come**: Pattern predefiniti per rilevare contraddizioni comuni

**Pattern esempi**:
- Date: "nato il X" vs "compleanno Y" (se X ≠ Y)
- Numeri: "altezza X cm" vs "altezza Y cm" (se X ≠ Y)
- Preferenze: "preferisce X" vs "preferisce Y" (se X ≠ Y e sono mutuamente esclusivi)

### 3. **Tipi di Contraddizioni da Rilevare**

1. **Date/Eventi**:
   - Date di nascita vs compleanno
   - Date di eventi importanti
   - Scadenze o deadline

2. **Fatti Personali**:
   - Nome, età, altezza, peso
   - Indirizzo, città, paese
   - Lavoro, posizione, azienda

3. **Preferenze**:
   - Preferenze mutuamente esclusive
   - Cambiamenti drastici senza contesto

4. **Progetti/Attività**:
   - Stato del progetto (iniziato vs completato)
   - Scadenze diverse per lo stesso progetto

### 4. **Flusso di Integrazione**

```
Nuova conoscenza estratta
    ↓
ConversationLearner.index_extracted_knowledge()
    ↓
Memoria salvata in long-term (non bloccante)
    ↓
BackgroundAgent.check_integrity(new_knowledge) [ASYNC]
    ↓
    ├─→ Trova memorie simili (embedding) - top N (configurabile, default 10)
    ├─→ Estrai entità (date, numeri, nomi)
    ├─→ Confronta entità
    └─→ Se contraddizione: usa LLM per analisi approfondita
    ↓
Risultato: {
    "has_contradiction": bool,
    "contradicting_memories": List[str],
    "confidence": float,  # >= soglia configurabile (default 0.8)
    "urgency": "high" | "medium" | "low",
    "type": "contradiction"
}
    ↓
Sistema Notifiche:
    ├─→ Crea notifica con urgenza
    ├─→ Attiva "campanella" (badge/icona)
    └─→ Salva notifica in database per prossima interazione
    ↓
Prossima interazione utente:
    ├─→ Controlla notifiche pendenti
    ├─→ In base all'urgenza:
    │   ├─→ HIGH: Mostra subito nel messaggio (prima della risposta)
    │   ├─→ MEDIUM: Segnala esistenza e chiede conferma
    │   └─→ LOW: Solo campanella (utente può aprire)
    └─→ Per contraddizioni: SEMPRE chiedere all'utente
```

### 5. **Sistema di Notifiche Proattive**

#### 5.1. Campanella (Badge/Icona)

- Icona visibile nell'interfaccia (es: 🔔 con badge numerico)
- Si attiva quando ci sono notifiche pendenti
- L'utente può cliccare per vedere tutte le notifiche

#### 5.2. Livelli di Urgenza

**HIGH (Urgente)**:
- Mostrato **subito nel messaggio** prima della risposta alla domanda
- Formato: `[⚠️ IMPORTANTE] [messaggio notifica]`
- Esempio:
```
[⚠️ IMPORTANTE] Ho rilevato una contraddizione: in precedenza mi avevi detto che sei nato il 12 luglio, 
ma ora mi dici che il tuo compleanno è il 15 agosto. Quale informazione è corretta?

[Poi risposta normale alla domanda dell'utente]
```

**MEDIUM (Media Urgenza)**:
- Segnala l'esistenza e chiede conferma se l'utente vuole vedere la notifica
- Formato: `"Ho una notifica importante per te. Vuoi che te la mostri ora?"`
- Se l'utente dice sì → mostra la notifica completa

**LOW (Bassa Urgenza)**:
- Solo campanella attiva
- L'utente può aprire manualmente per vedere le notifiche
- Non interrompe il flusso della conversazione

#### 5.3. Gestione Contraddizioni

**Sempre chiedere all'utente** - mai decidere autonomamente:
- Mostrare entrambe le memorie contrastanti
- Chiedere quale è corretta
- Offrire opzioni: "La prima", "La seconda", "Entrambe sono corrette (spiega)", "Cancella entrambe"

**Esempio risposta (HIGH urgency)**:
```
[⚠️ CONTRADDIZIONE RILEVATA]

Ho notato una contraddizione nella memoria:

1. Memoria precedente: "L'utente è nato il 12 luglio 1990"
2. Memoria nuova: "Il compleanno dell'utente è il 15 agosto"

Quale informazione è corretta?
- A) La prima (12 luglio)
- B) La seconda (15 agosto)
- C) Entrambe sono corrette (spiega il contesto)
- D) Cancella entrambe

[Poi risposta normale alla domanda dell'utente]
```

### 6. **Implementazione Tecnica**

#### 6.1. Nuovo Servizio: `BackgroundAgent`

```python
class BackgroundAgent:
    """
    Agente in background per "pensiero autonomo" dell'assistente.
    Gestisce: integrità semantica, eventi esterni, todo list, ecc.
    """
    def __init__(self, memory_manager, ollama_client, db_session):
        self.memory_manager = memory_manager
        self.ollama_client = ollama_client
        self.db = db_session
        self.integrity_checker = SemanticIntegrityChecker(
            memory_manager, ollama_client
        )
        self.notification_service = NotificationService(db_session)
    
    async def process_new_knowledge(self, knowledge_item: Dict[str, Any]):
        """
        Processa nuova conoscenza in background:
        - Controlla integrità semantica
        - Genera notifiche se necessario
        """
        # Check integrity (esaustivo o limitato in base a config)
        contradiction_info = await self.integrity_checker.check_contradictions(
            knowledge_item,
            db=self.db,
            max_similar_memories=settings.integrity_max_similar_memories,  # default 10
            confidence_threshold=settings.integrity_confidence_threshold,  # default 0.8
        )
        
        if contradiction_info["has_contradiction"]:
            # Create notification (always HIGH urgency for contradictions)
            await self.notification_service.create_notification(
                type="contradiction",
                urgency="high",
                content=contradiction_info,
                user_id=knowledge_item.get("user_id"),  # se multi-user
            )
    
    async def check_external_events(self):
        """Controlla eventi esterni (email, calendario, ecc.) - da implementare"""
        pass
    
    async def check_todo_list(self):
        """Consulta todo list - da implementare"""
        pass
```

#### 6.2. Nuovo Servizio: `SemanticIntegrityChecker`

```python
class SemanticIntegrityChecker:
    def __init__(self, memory_manager, ollama_client):
        self.memory_manager = memory_manager
        self.ollama_client = ollama_client
        self.embedding_service = EmbeddingService()
    
    async def check_contradictions(
        self,
        new_knowledge: Dict[str, Any],
        db: AsyncSession,
        max_similar_memories: int = 10,  # Configurabile
        confidence_threshold: float = 0.8,  # Configurabile
    ) -> Dict[str, Any]:
        """
        Check if new knowledge contradicts existing memories.
        Eseguito in background, può essere esaustivo.
        """
        # 1. Find similar memories (top N configurabile)
        similar_memories = await self._find_similar_memories(
            new_knowledge, 
            n_results=max_similar_memories
        )
        
        # 2. Extract entities from new and existing memories
        new_entities = self._extract_entities(new_knowledge)
        
        # 3. Compare entities
        contradictions = []
        for memory in similar_memories:
            existing_entities = self._extract_entities(memory)
            if self._entities_conflict(new_entities, existing_entities):
                # 4. Use LLM for deep analysis
                contradiction = await self._analyze_with_llm(
                    new_knowledge, memory, confidence_threshold
                )
                if contradiction["is_contradiction"] and contradiction["confidence"] >= confidence_threshold:
                    contradictions.append(contradiction)
        
        return {
            "has_contradiction": len(contradictions) > 0,
            "contradictions": contradictions,
            "confidence": max([c["confidence"] for c in contradictions]) if contradictions else 0.0,
        }
    
    def _extract_entities(self, knowledge: Dict[str, Any]) -> Dict[str, Any]:
        """Extract entities (dates, numbers, names) from knowledge"""
        # Use regex + LLM for entity extraction
        # Return: {"dates": [...], "numbers": [...], "names": [...]}
        pass
    
    def _entities_conflict(self, new_entities, existing_entities) -> bool:
        """Check if extracted entities conflict"""
        # Compare dates, numbers, etc.
        pass
    
    async def _analyze_with_llm(
        self, 
        new_knowledge, 
        existing_memory, 
        confidence_threshold: float
    ) -> Dict:
        """Use LLM to analyze if memories contradict"""
        # Returns: {
        #   "is_contradiction": bool,
        #   "confidence": float,
        #   "explanation": str
        # }
        pass
```

#### 6.3. Nuovo Servizio: `NotificationService`

```python
class NotificationService:
    """Gestisce notifiche proattive dell'assistente"""
    
    async def create_notification(
        self,
        type: str,  # "contradiction", "event", "todo", ecc.
        urgency: str,  # "high", "medium", "low"
        content: Dict[str, Any],
        user_id: Optional[UUID] = None,
    ):
        """Crea una notifica e la salva nel database"""
        notification = Notification(
            type=type,
            urgency=urgency,
            content=content,
            user_id=user_id,
            created_at=datetime.now(),
            read=False,
        )
        db.add(notification)
        await db.commit()
    
    async def get_pending_notifications(
        self,
        user_id: Optional[UUID] = None,
        urgency: Optional[str] = None,
    ) -> List[Dict]:
        """Recupera notifiche pendenti"""
        pass
    
    async def mark_as_read(self, notification_id: UUID):
        """Segna notifica come letta"""
        pass
```

#### 6.4. Integrazione in `ConversationLearner`

```python
async def index_extracted_knowledge(self, ...):
    # Index knowledge first (non bloccante)
    for item in knowledge_items:
        await self.memory_manager.add_long_term_memory(...)
    
    # Then schedule background integrity check
    import asyncio
    from app.services.background_agent import BackgroundAgent
    from app.db.database import AsyncSessionLocal
    
    async def _check_integrity_background():
        async with AsyncSessionLocal() as db_session:
            agent = BackgroundAgent(
                memory_manager=self.memory_manager,
                ollama_client=self.ollama_client,
                db_session=db_session,
            )
            for item in knowledge_items:
                await agent.process_new_knowledge(item)
    
    # Schedule background task (fire and forget)
    asyncio.create_task(_check_integrity_background())
```

#### 6.5. Integrazione in Chat Response

```python
# In sessions.py chat endpoint
async def chat(...):
    # ... existing code ...
    
    # Check for pending notifications
    from app.services.notification_service import NotificationService
    notification_service = NotificationService(db)
    
    pending_notifications = await notification_service.get_pending_notifications(
        user_id=session.user_id if hasattr(session, 'user_id') else None
    )
    
    # Group by urgency
    high_urgency = [n for n in pending_notifications if n["urgency"] == "high"]
    medium_urgency = [n for n in pending_notifications if n["urgency"] == "medium"]
    low_urgency = [n for n in pending_notifications if n["urgency"] == "low"]
    
    # Build response with notifications
    response_text = ""
    
    # HIGH: Show immediately before response
    if high_urgency:
        for notif in high_urgency:
            response_text += format_notification(notif, show_immediately=True)
            response_text += "\n\n"
    
    # ... generate normal response ...
    
    # MEDIUM: Ask if user wants to see
    if medium_urgency:
        response_text += "\n\n"
        response_text += "Ho alcune notifiche importanti. Vuoi che te le mostri ora? (sì/no)\n"
    
    # LOW: Just update badge count (handled in frontend)
    
    return ChatResponse(
        response=response_text,
        notifications_count=len(pending_notifications),
        high_urgency_notifications=high_urgency,
        # ... other fields ...
    )
```

#### 6.6. Configurazione

```python
# In app/core/config.py
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Semantic Integrity Check
    integrity_confidence_threshold: float = 0.8  # Soglia confidenza contraddizioni
    integrity_max_similar_memories: int = 10  # Numero memorie simili da controllare
    integrity_check_exhaustive: bool = False  # Se True, controlla tutte (più lento)
```

#### 6.7. Frontend: Campanella e Notifiche

```typescript
// Componente NotificationsBell
interface Notification {
  id: string;
  type: 'contradiction' | 'event' | 'todo';
  urgency: 'high' | 'medium' | 'low';
  content: any;
  created_at: string;
  read: boolean;
}

// Badge con count
<BellIcon>
  {notificationsCount > 0 && (
    <Badge>{notificationsCount}</Badge>
  )}
</BellIcon>

// Pannello notifiche (apribile cliccando)
<NotificationsPanel>
  {notifications.map(notif => (
    <NotificationItem 
      urgency={notif.urgency}
      content={notif.content}
    />
  ))}
</NotificationsPanel>
```

### 7. **Vantaggi di Questo Approccio**

✅ **Non Blocca**: Le nuove memorie vengono sempre salvate, anche se c'è una contraddizione
✅ **Proattivo**: Primo livello di proattività dell'assistente
✅ **Background**: Analisi esaustiva senza rallentare le risposte
✅ **Multi-Livello**: Combina tecniche diverse per maggiore accuratezza
✅ **Flessibile**: Può essere esteso con nuovi controlli (eventi, todo, ecc.)
✅ **User-Friendly**: Notifiche con livelli di urgenza appropriati
✅ **Configurabile**: Parametri modificabili dall'utente
✅ **Performance**: Usa embedding per filtrare prima di analisi LLM costose

### 8. **Considerazioni**

- **False Positives**: Due date diverse potrebbero essere corrette (es: compleanno vs anniversario)
  - **Soluzione**: Sempre chiedere all'utente, mai decidere autonomamente
- **Context Matters**: Alcune "contraddizioni" potrebbero essere aggiornamenti legittimi
  - **Soluzione**: LLM analizza il contesto, utente decide
- **Performance**: LLM analysis è costosa → eseguita in background, non blocca risposte
- **Storage**: Notifiche salvate in database, possono essere lette/non lette
- **Scalabilità**: BackgroundAgent può essere esteso con altri controlli senza modificare il core

### 9. **Prossimi Passi**

1. ✅ Creare `BackgroundAgent` service (gestore principale)
2. ✅ Creare `SemanticIntegrityChecker` service
3. ✅ Creare `NotificationService` service
4. ✅ Implementare estrazione entità (date, numeri, nomi)
5. ✅ Implementare confronto entità
6. ✅ Integrare LLM per analisi approfondita
7. ✅ Integrare nel flusso di indicizzazione (background)
8. ✅ Implementare sistema notifiche (campanella + livelli urgenza)
9. ✅ Aggiungere parametri configurabili (soglia confidenza, max memorie)
10. ✅ Frontend: campanella e pannello notifiche
11. ✅ Test con casi reali

## Decisioni Prese

1. **Quando notificare?**: ✅ Nella prossima risposta, con livelli di urgenza
2. **Cosa fare con memorie contraddittorie?**: ✅ Sempre chiedere all'utente, mai decidere autonomamente
3. **Soglia di confidenza**: ✅ Parametro configurabile, default 0.8
4. **Performance**: ✅ Parametro configurabile (max memorie simili), default 10. Analisi in background può essere esaustiva
5. **Architettura**: ✅ BackgroundAgent per "pensiero autonomo", estendibile per eventi esterni, todo, ecc.
6. **Sistema notifiche**: ✅ Campanella + livelli urgenza (high/medium/low) + gestione nella risposta

