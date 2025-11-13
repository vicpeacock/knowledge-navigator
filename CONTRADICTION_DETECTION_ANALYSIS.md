# Analisi Algoritmo di Rilevazione Contraddizioni

## Problemi Identificati

### 1. **Troppo Sensibile - Falsi Positivi**
L'algoritmo attuale rileva contraddizioni anche quando non ci sono:
- **Soglia di confidenza troppo bassa**: `integrity_confidence_threshold = 0.7` (riga 66 in `config.py`)
- **Troppe memorie controllate**: `integrity_max_similar_memories = 15` (riga 67)
- **LLM troppo permissivo**: Il prompt LLM potrebbe essere troppo generico

### 2. **Problemi con Tassonomia**
Il prompt include logica tassonomica complessa che può generare falsi positivi:
- "Likes pasta" vs "Hates spaghetti" → CONTRADICTION
- Ma "Likes Italian food" vs "Likes pizza" → NO CONTRADICTION (dovrebbe essere complementare)

### 3. **Mancanza di Contesto Temporale**
L'algoritmo non considera:
- **Cambiamenti nel tempo**: Preferenze possono cambiare
- **Contesto diverso**: "Likes pasta at lunch" vs "Hates pasta at dinner" non è contraddizione

### 4. **Memoria Sporca**
- Memorie duplicate o simili che generano rumore
- Memorie obsolete che non dovrebbero più essere considerate
- Memorie con importanza bassa che vengono comunque controllate

## Soluzioni Proposte

### 1. **Aumentare Soglia di Confidenza**
```python
integrity_confidence_threshold: float = 0.85  # Da 0.7 a 0.85
```
- Riduce falsi positivi
- Richiede contraddizioni più evidenti

### 2. **Ridurre Numero di Memorie Controllate**
```python
integrity_max_similar_memories: int = 5  # Da 15 a 5
```
- Controlla solo le memorie più simili
- Riduce tempo di elaborazione
- Riduce falsi positivi da memorie poco rilevanti

### 3. **Filtrare Memorie per Importanza**
Modificare `_find_similar_memories` per considerare solo memorie con `importance_score >= 0.7`:
```python
async def retrieve_long_term_memory(
    self,
    query: str,
    n_results: int = 5,
    min_importance: float = 0.7,  # Filtra memorie poco importanti
) -> List[str]:
```

### 4. **Migliorare Prompt LLM**
Aggiungere esempi più specifici e regole più chiare:
- Distinguere tra contraddizioni logiche e preferenze diverse
- Considerare contesto temporale
- Essere più conservativo (meglio non rilevare che rilevare falsi positivi)

### 5. **Pulizia Periodica della Memoria**
- Rimuovere memorie duplicate
- Rimuovere memorie con importanza < 0.5 dopo 30 giorni
- Consolidare memorie simili

### 6. **Aggiungere Whitelist/Blacklist**
- Whitelist: entità che possono avere preferenze diverse senza contraddizione
- Blacklist: pattern noti che generano falsi positivi

## Script di Pulizia

È stato creato `backend/scripts/clean_long_term_memory.py` per:
- Rimuovere tutte le memorie long-term da PostgreSQL
- Rimuovere tutti i documenti da ChromaDB
- Permettere test end-to-end puliti

**Uso:**
```bash
cd backend
python scripts/clean_long_term_memory.py
```

## Prossimi Passi

1. ✅ Pulire memoria esistente
2. ⏳ Aumentare soglia di confidenza a 0.85
3. ⏳ Ridurre memorie controllate a 5
4. ⏳ Aggiungere filtro per importanza minima
5. ⏳ Migliorare prompt LLM con esempi più specifici
6. ⏳ Testare con memoria pulita

