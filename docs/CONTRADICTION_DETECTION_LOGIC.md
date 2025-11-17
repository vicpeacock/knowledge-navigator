# Logica di Rilevamento Contraddizioni - Analisi Completa

## Flusso Completo

### 1. **Estrazione Conoscenza (ConversationLearner)**

**Quando**: Dopo ogni messaggio dell'utente nella chat

**Cosa fa**:
- Analizza l'intera conversazione con un LLM
- Estrae conoscenze importanti (fatti, preferenze, info personali)
- Filtra per importanza minima (default: 0.6)
- Restituisce una lista di "knowledge items"

**Prompt LLM**:
```
Analizza questa conversazione e estrai conoscenze importanti...
- Fatti importanti (date, eventi, decisioni)
- Preferenze dell'utente (positive e negative)
- Informazioni personali rilevanti
- Contatti o riferimenti importanti
- Progetti o attività menzionate
```

**Output**: Lista di oggetti con:
- `type`: "fact", "preference", "personal_info", "contact", "project"
- `content`: descrizione della conoscenza
- `importance`: score 0.0-1.0

### 2. **Trigger Controllo Contraddizioni**

**Quando**: Dopo l'estrazione della conoscenza

**Cosa fa**:
- Per ogni knowledge item estratto, viene schedulato un controllo contraddizioni
- Il controllo viene eseguito in background (non blocca la risposta all'utente)
- Usa `BackgroundTaskManager.schedule_contradiction_check()`

### 3. **Ricerca Memorie Simili (SemanticIntegrityChecker)**

**Cosa fa**:
1. Prende il contenuto della nuova conoscenza
2. Rimuove prefissi tipo `[FACT]`, `[PREFERENCE]`, ecc.
3. Cerca memorie simili usando **semantic search** (embedding similarity)
4. Filtra per importanza minima (`integrity_min_importance = 0.7`)
5. Limita a `integrity_max_similar_memories = 5` memorie più simili

**Parametri Config**:
- `integrity_max_similar_memories = 5` (numero di memorie da controllare)
- `integrity_min_importance = 0.7` (filtra memorie poco importanti)
- `integrity_confidence_threshold = 0.85` (soglia di confidenza per considerare una contraddizione)

### 4. **Analisi LLM per Contraddizioni**

**Per ogni memoria simile trovata**:
1. Confronta la nuova conoscenza con la memoria esistente
2. Usa un LLM (llama.cpp background) per analizzare se c'è contraddizione
3. Il LLM valuta:
   - Contraddizioni dirette
   - Contraddizioni temporali
   - Contraddizioni numeriche
   - Contraddizioni di stato
   - **Contraddizioni di preferenza** (likes vs dislikes)
   - Contraddizioni di relazione
   - Contraddizioni fattuali
   - **Contraddizioni tassonomiche** (categoria vs istanza)

**Prompt LLM**:
```
Analyze if these two statements logically contradict each other.

EXISTING STATEMENT: "{existing_memory}"
NEW STATEMENT: "{new_memory}"

[Include detailed instructions about taxonomic relationships, 
preference contradictions, etc.]
```

**Output LLM**:
```json
{
    "is_contradiction": true/false,
    "confidence": 0.0-1.0,
    "explanation": "...",
    "contradiction_type": "direct|temporal|numerical|status|preference|relationship|factual|none"
}
```

### 5. **Filtraggio per Soglia**

**Cosa fa**:
- Se `is_contradiction == true` E `confidence >= threshold` (0.85)
- Aggiunge la contraddizione alla lista
- Altrimenti la ignora

### 6. **Creazione Notifica**

**Se ci sono contraddizioni**:
1. Crea una notifica nel database (`type="contradiction"`)
2. Crea un task nella coda (`type="resolve_contradiction"`)
3. Il task viene processato dal `TaskDispatcher`
4. Il dispatcher invia la richiesta di risoluzione all'utente tramite notification bell

## Problemi Identificati

### 1. **Troppo Sensibile - Falsi Positivi**

**Problema**: Il sistema rileva contraddizioni anche quando non ci sono

**Cause**:
- **Soglia di confidenza**: Anche se aumentata a 0.85, potrebbe essere ancora troppo bassa
- **Logica tassonomica troppo aggressiva**: "Likes pasta" vs "Hates spaghetti" viene considerata contraddizione, ma potrebbe essere legittimo (es. "mi piace la pasta in generale ma non gli spaghetti")
- **Mancanza di contesto**: Non considera che preferenze possono cambiare nel tempo o in contesti diversi
- **LLM troppo permissivo**: Il prompt potrebbe essere interpretato in modo troppo generico

### 2. **Estrazione Conoscenza Troppo Aggressiva**

**Problema**: `ConversationLearner` estrae troppe conoscenze, anche da affermazioni casuali

**Esempio**:
- Utente dice: "Oggi ho mangiato pasta"
- Sistema estrae: "L'utente mangia pasta" (come preferenza?)
- Poi: "Oggi ho mangiato risotto"
- Sistema rileva contraddizione perché ha estratto "preferisce pasta" dalla prima affermazione

**Causa**: Il prompt di estrazione non distingue bene tra:
- Affermazioni casuali/informative
- Preferenze dichiarate esplicitamente
- Fatti temporanei vs preferenze permanenti

### 3. **Mancanza di Contesto Temporale**

**Problema**: Non considera che:
- Preferenze possono cambiare nel tempo
- "Non mi piace X" in un contesto non significa "non mi piace sempre X"
- Fatti temporanei (es. "oggi ho fatto X") non dovrebbero essere confrontati con preferenze generali

### 4. **Memoria Sporca**

**Problema**: 
- Memorie duplicate o simili generano rumore
- Memorie obsolete che non dovrebbero più essere considerate
- Memorie estratte male (es. "L'utente ha detto X" invece di "L'utente preferisce X")

### 5. **Prompt LLM Troppo Complesso**

**Problema**: Il prompt per l'analisi contraddizioni è molto lungo e include molti esempi di contraddizioni tassonomiche, che potrebbero portare il LLM a essere troppo permissivo nel rilevare contraddizioni.

## Soluzioni Proposte

### 1. **Migliorare Estrazione Conoscenza**

**A. Distinguere meglio tra tipi di affermazioni**:
- **Preferenze esplicite**: "Mi piace X", "Preferisco Y", "Non mi piace Z"
- **Fatti temporanei**: "Oggi ho fatto X", "Ieri ho mangiato Y"
- **Informazioni casuali**: "Ho visto X", "Ho letto Y"

**B. Richiedere esplicita dichiarazione di preferenza**:
- Non estrarre preferenze da affermazioni casuali
- Richiedere verbi espliciti: "mi piace", "amo", "preferisco", "detesto", "odio"

**C. Aggiungere contesto temporale**:
- Se l'utente dice "oggi", "ieri", "questa settimana" → non estrarre come preferenza permanente

### 2. **Migliorare Prompt Analisi Contraddizioni**

**A. Essere più conservativo**:
- Aggiungere esempi di "NON contraddizioni" più chiari
- Enfatizzare che preferenze diverse in contesti diversi NON sono contraddizioni
- Enfatizzare che preferenze possono cambiare nel tempo

**B. Ridurre enfasi su contraddizioni tassonomiche**:
- Essere più conservativo: "Likes pasta" vs "Hates spaghetti" potrebbe NON essere contraddizione se c'è un contesto specifico
- Richiedere confidenza più alta per contraddizioni tassonomiche

### 3. **Aggiungere Filtri Pre-Analisi**

**A. Filtro per similarità semantica minima**:
- Prima di chiamare l'LLM, verificare che le memorie siano realmente simili
- Se la similarità è troppo bassa, saltare l'analisi

**B. Filtro per tipo di conoscenza**:
- Non confrontare "fatti temporanei" con "preferenze permanenti"
- Non confrontare conoscenze di tipo diverso (es. "fact" vs "preference")

### 4. **Aumentare Soglia di Confidenza**

**Proposta**: Aumentare `integrity_confidence_threshold` a **0.90** o **0.95**

**Razionale**: Meglio non rilevare una contraddizione che rilevarne una falsa

### 5. **Pulizia Periodica Memoria**

**A. Rimuovere memorie duplicate**:
- Consolidare memorie simili
- Rimuovere duplicati esatti

**B. Rimuovere memorie obsolete**:
- Memorie con importanza < 0.5 dopo 30 giorni
- Memorie che non sono state referenziate per molto tempo

**C. Validazione memorie**:
- Verificare che le memorie estratte siano ben formate
- Rimuovere memorie malformate o incomplete

## Configurazione Attuale

```python
# backend/app/core/config.py
integrity_confidence_threshold: float = 0.85  # Soglia confidenza
integrity_max_similar_memories: int = 5  # Numero memorie da controllare
integrity_min_importance: float = 0.7  # Importanza minima memorie
```

## Prossimi Passi

1. ✅ Pulire memoria esistente (fatto)
2. ⏳ Migliorare prompt estrazione conoscenza
3. ⏳ Migliorare prompt analisi contraddizioni (più conservativo)
4. ⏳ Aggiungere filtri pre-analisi
5. ⏳ Aumentare soglia confidenza a 0.90
6. ⏳ Implementare pulizia periodica memoria

