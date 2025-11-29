# Piano Miglioramenti Rilevamento Contraddizioni

**Data**: 2025-11-29  
**Status**: In Planning

## ✅ Stato Attuale

Il sistema di rilevamento contraddizioni è già implementato con:
- ✅ `SemanticIntegrityChecker` funzionante
- ✅ Soglia confidenza: **0.85** (già aumentata da 0.7)
- ✅ Numero memorie controllate: **5** (già ridotto da 15)
- ✅ Filtro importanza minima: **0.7**
- ✅ LLM-based analysis completo

## 🎯 Miglioramenti Proposti

### 1. Aumentare Soglia Confidenza a 0.90-0.95 ⭐ PRIORITÀ ALTA

**Problema**: Anche con 0.85, ci possono essere falsi positivi  
**Soluzione**: Aumentare a 0.90 o 0.95 per essere più conservativi

**Modifiche**:
```python
# backend/app/core/config.py
integrity_confidence_threshold: float = 0.90  # Da 0.85 a 0.90
```

**Impatto**: 
- ✅ Riduce drasticamente falsi positivi
- ⚠️ Potrebbe perdere alcune contraddizioni reali (trade-off accettabile)

### 2. Filtri Pre-Analisi: Non Confrontare Tipi Diversi ⭐ PRIORITÀ ALTA

**Problema**: Confronta memorie di tipo diverso (fact vs preference) che non dovrebbero essere confrontate  
**Soluzione**: Filtrare prima dell'analisi LLM

**Modifiche**:
```python
# backend/app/services/semantic_integrity_checker.py
def _should_compare(self, new_knowledge: Dict, existing_memory: str) -> bool:
    """Check if two memories should be compared"""
    new_type = new_knowledge.get("type", "").lower()
    existing_type = self._extract_type_from_memory(existing_memory)
    
    # Don't compare different types (fact vs preference)
    if new_type != existing_type and new_type and existing_type:
        return False
    
    # Don't compare preferences with facts
    if (new_type == "preference" and existing_type == "fact") or \
       (new_type == "fact" and existing_type == "preference"):
        return False
    
    return True
```

**Impatto**:
- ✅ Riduce falsi positivi da confronti non validi
- ✅ Migliora performance (meno chiamate LLM)

### 3. Migliorare Estrazione Conoscenza ⭐ PRIORITÀ MEDIA

**Problema**: Estrae anche affermazioni casuali come preferenze  
**Soluzione**: Migliorare prompt per distinguere meglio

**Modifiche**:
```python
# backend/app/services/conversation_learner.py
extraction_prompt = f"""...
IMPORTANTE: Distingui tra:
- Preferenze esplicite ("mi piace", "amo", "detesto")
- Affermazioni casuali ("ho mangiato pasta ieri" NON è una preferenza)
- Fatti temporanei ("oggi ho fatto X") vs permanenti ("sono nato il X")

Per le preferenze:
- Solo se esplicitamente dichiarate con verbi di preferenza
- Non estrarre come preferenza se è solo menzione casuale
..."""
```

**Impatto**:
- ✅ Riduce rumore nella memoria
- ✅ Migliora qualità estrazione

### 4. Migliorare Prompt LLM per Analisi ⭐ PRIORITÀ MEDIA

**Problema**: Prompt troppo generico può generare falsi positivi  
**Soluzione**: Prompt più conservativo con esempi specifici

**Modifiche**:
```python
# backend/app/services/semantic_integrity_checker.py
prompt = f"""...
**CONSERVATIVE APPROACH**: 
- Se non sei sicuro al 95% che sia una contraddizione logica → NO CONTRADICTION
- Meglio non rilevare una contraddizione che rilevarne una falsa
- Considera sempre il contesto temporale e situazionale

**ESEMPI DI NON-CONTRADIZIONI**:
- "Likes pasta" vs "Ate pizza yesterday" → NO (diversi contesti temporali)
- "Likes Italian food" vs "Likes pizza" → NO (complementari, non contraddittori)
- "Born in 1990" vs "Age 35" → NO (compatibili se calcolati correttamente)

**ESEMPI DI CONTRADIZIONI REALI**:
- "Born July 12" vs "Born August 15" → YES (date incompatibili)
- "Likes pasta" vs "Hates pasta" → YES (preferenze opposte esplicite)
- "Height 180cm" vs "Height 160cm" → YES (valori incompatibili)
..."""
```

**Impatto**:
- ✅ Riduce falsi positivi
- ✅ Migliora accuratezza

### 5. Aggiungere Contesto Temporale ⭐ PRIORITÀ BASSA

**Problema**: Non considera che preferenze possono cambiare nel tempo  
**Soluzione**: Aggiungere analisi temporale

**Modifiche**:
```python
# Estrai date/timestamps dalle memorie
# Se memorie hanno date molto distanti (> 1 anno), essere più conservativi
# Se memorie hanno date vicine, essere più rigorosi
```

**Impatto**:
- ✅ Migliora accuratezza per preferenze che cambiano
- ⚠️ Complessità aggiuntiva

### 6. Pulizia Periodica Memoria ⭐ PRIORITÀ BASSA

**Problema**: Memorie duplicate o obsolete generano rumore  
**Soluzione**: Script di pulizia periodica

**Modifiche**:
- Usare `MemoryConsolidator` esistente
- Schedulare pulizia periodica (es. settimanale)
- Rimuovere memorie con importanza < 0.5 dopo 30 giorni

**Impatto**:
- ✅ Riduce rumore
- ✅ Migliora performance

## 📋 Piano di Implementazione

### Fase 1: Quick Wins (1-2 giorni)
1. ✅ Aumentare soglia confidenza a 0.90
2. ✅ Aggiungere filtri pre-analisi (tipi diversi)
3. ✅ Migliorare prompt LLM (più conservativo)

### Fase 2: Miglioramenti Estrazione (2-3 giorni)
4. ✅ Migliorare estrazione conoscenza (distinguere casuali vs preferenze)

### Fase 3: Ottimizzazioni Avanzate (opzionale)
5. ⏳ Aggiungere contesto temporale
6. ⏳ Implementare pulizia periodica memoria

## 🎯 Risultati Attesi

Dopo Fase 1:
- **Riduzione falsi positivi**: ~70-80%
- **Mantenimento accuratezza**: ~95%+ per contraddizioni reali
- **Miglioramento performance**: ~20-30% (meno chiamate LLM)

## 📝 Note

- La soglia 0.90 è un buon compromesso tra accuratezza e falsi positivi
- I filtri pre-analisi sono critici per evitare confronti non validi
- Il prompt migliorato è fondamentale per accuratezza LLM

