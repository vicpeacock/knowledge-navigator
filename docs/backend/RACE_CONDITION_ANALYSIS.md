# Analisi Race Condition e Soluzioni

## Problema: Race Condition nel Controllo Contraddizioni

### Situazione Attuale

```
1. User invia messaggio
2. Main Agent schedulata controllo contraddizioni (background task)
3. Main Agent genera risposta (può richiedere 2-10 secondi)
4. Main Agent recupera notifiche dal database
5. ⚠️ PROBLEMA: Controllo potrebbe non essere ancora completato
6. Notifica non trovata → non viene inviata al frontend
```

### Timing Reale (dai log)

- **Controllo contraddizioni**: 2-5 secondi (chiamate LLM multiple)
- **Generazione risposta**: 2-10 secondi (dipende da tool calls)
- **Timeout attuale**: 2 secondi (insufficiente se controllo richiede 5s)

## Soluzioni Possibili

### 1. ✅ Aumentare Timeout (Semplice)

**Pro:**
- Facile da implementare
- Risolve il problema nella maggior parte dei casi

**Contro:**
- Aggiunge latenza alla risposta (attesa fino a 5-10s)
- Non garantisce che il controllo sia completato
- Se controllo richiede > timeout, notifica persa

**Implementazione:**
```python
# Attualmente: 2 secondi
await asyncio.wait_for(contradiction_check_task, timeout=2.0)

# Proposta: 10 secondi
await asyncio.wait_for(contradiction_check_task, timeout=10.0)
```

### 2. ⚠️ Rendere Controllo Sincrono (Non Raccomandato)

**Pro:**
- Garantisce che notifica sia disponibile
- Nessuna race condition

**Contro:**
- **Rallenta la risposta** (aggiunge 2-5s di latenza)
- Blocca il thread principale
- Peggiora UX

### 3. ✅ Server-Sent Events (SSE) / WebSocket (Raccomandato)

**Pro:**
- Notifiche in tempo reale
- Nessuna race condition (notifica arriva quando pronta)
- Migliore UX (notifica appare quando disponibile)

**Contro:**
- Richiede modifiche al frontend
- Maggiore complessità

**Implementazione:**
```python
# Backend: Endpoint SSE
@router.get("/{session_id}/notifications/stream")
async def stream_notifications(session_id: UUID):
    async def event_generator():
        while True:
            # Controlla nuove notifiche
            notifications = await get_new_notifications(session_id)
            if notifications:
                yield f"data: {json.dumps(notifications)}\n\n"
            await asyncio.sleep(1)
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### 4. ⚠️ MessageBroker (Non Risolve Race Condition)

**Perché NON risolve:**
- Il MessageBroker è un sistema di **comunicazione intelligente**
- Non risolve il problema di **timing/asincronizzazione**
- Aggiunge un layer LLM che può **aumentare la latenza**

**Quando potrebbe aiutare:**
- Se implementato con **acknowledgment** e **sincronizzazione**
- Se gestisce **queue** con priorità
- Ma di per sé, non risolve la race condition

**Esempio di MessageBroker che NON risolve:**
```
Background Agent → MessageBroker (LLM interpreta) → Main Agent
```
Il problema rimane: quando Main Agent chiede notifiche, Background Agent potrebbe non aver ancora completato.

**Esempio di MessageBroker che POTREBBE aiutare:**
```
Background Agent → MessageBroker (con queue + acknowledgment)
Main Agent → MessageBroker (polling o callback)
```
Ma questo è essenzialmente un sistema di queue, non necessariamente LLM-based.

### 5. ✅ Ottimizzare Controllo Contraddizioni (Migliore)

**Pro:**
- Riduce tempo di controllo (da 5s a 1-2s)
- Riduce probabilità di race condition
- Migliora performance generale

**Strategie:**
- **Limitare memorie da controllare**: Top 5 invece di 15
- **Parallelizzare chiamate LLM**: Controlla più memorie in parallelo
- **Caching**: Cache risultati per memorie simili
- **Early exit**: Se trova contraddizione alta confidenza, ferma subito

**Implementazione:**
```python
# Attualmente: controlla 15 memorie sequenzialmente
for memory_content in similar_memories[:15]:  # 15 memorie
    contradiction = await self._analyze_with_llm(...)  # Sequenziale

# Proposta: controlla top 5 in parallelo
tasks = [
    self._analyze_with_llm(clean_content, mem, threshold)
    for mem in similar_memories[:5]  # Solo top 5
]
results = await asyncio.gather(*tasks)  # Parallelo
```

## Raccomandazione

**Approccio Combinato:**

1. **Immediato**: Aumentare timeout a 10 secondi
2. **Breve termine**: Ottimizzare controllo (top 5, parallelo)
3. **Medio termine**: Implementare SSE per notifiche real-time

**MessageBroker:**
- Utile per comunicazione intelligente tra agenti
- NON risolve la race condition di per sé
- Può essere aggiunto DOPO aver risolto la race condition

## Confronto Soluzioni

| Soluzione | Risolve Race Condition | Latenza | Complessità | Raccomandazione |
|-----------|----------------------|---------|-------------|-----------------|
| Aumentare timeout | Parziale | +2-10s | Bassa | ✅ Breve termine |
| Controllo sincrono | ✅ Sì | +2-5s | Bassa | ❌ Non raccomandato |
| SSE/WebSocket | ✅ Sì | 0s | Media | ✅ Medio termine |
| MessageBroker | ❌ No | +1-3s | Alta | ⚠️ Dopo race condition |
| Ottimizzare controllo | Parziale | -2-3s | Media | ✅ Breve termine |

