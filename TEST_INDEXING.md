# Guida Test Indicizzazione Contenuti Web

## 🎯 Obiettivo
Verificare che l'indicizzazione automatica dei contenuti web funzioni correttamente.

## 📋 Test da Eseguire

### Test 1: Indicizzazione web_search
**Cosa fare:**
1. Apri una nuova chat o usa una esistente
2. Chiedi all'AI di fare una ricerca web, ad esempio:
   ```
   Cerca informazioni su Python async programming
   ```
   oppure
   ```
   Fai una ricerca web su "machine learning"
   ```

**Cosa verificare:**
- L'AI dovrebbe usare il tool `web_search`
- Nei log del backend dovresti vedere:
  ```
  Auto-indexed X web search results
  ```
- Il risultato della chat dovrebbe includere `indexing_stats` nel risultato del tool

### Test 2: Indicizzazione web_fetch
**Cosa fare:**
1. Chiedi all'AI di recuperare una pagina web specifica:
   ```
   Recupera il contenuto di https://example.com
   ```
   oppure
   ```
   Leggi questa pagina: https://www.python.org/about/
   ```

**Cosa verificare:**
- L'AI dovrebbe usare il tool `web_fetch`
- Nei log del backend:
  ```
  Auto-indexed web fetch result for URL: ...
  ```

### Test 3: Indicizzazione browser_snapshot
**Cosa fare:**
1. Chiedi all'AI di navigare su una pagina web:
   ```
   Vai su https://example.com e dimmi cosa vedi
   ```
   oppure
   ```
   Naviga su https://www.python.org e fai uno snapshot della pagina
   ```

**Cosa verificare:**
- L'AI dovrebbe usare `mcp_browser_navigate` e poi `mcp_browser_snapshot`
- Nei log:
  ```
  Auto-indexed browser snapshot for URL: ...
  ```

### Test 4: Verifica Recupero dalla Memoria
**Cosa fare:**
1. Dopo aver indicizzato contenuti (Test 1-3), chiedi all'AI qualcosa di correlato:
   ```
   Cosa ricordi su Python async programming?
   ```
   oppure
   ```
   Hai informazioni su machine learning?
   ```

**Cosa verificare:**
- L'AI dovrebbe recuperare i contenuti indicizzati dalla memoria long-term
- La risposta dovrebbe includere informazioni dai contenuti precedentemente indicizzati

### Test 5: Verifica Database
**Cosa fare:**
1. Controlla i log del backend per vedere se vengono creati record in ChromaDB
2. Verifica nel database PostgreSQL la tabella `memory_long`:
   ```sql
   SELECT COUNT(*) FROM memory_long;
   SELECT content, importance_score, learned_from_sessions 
   FROM memory_long 
   ORDER BY id DESC 
   LIMIT 5;
   ```

## 🔍 Come Verificare i Log

### Backend Logs
I log mostrano:
- `Auto-indexed X web search results` - per web_search
- `Auto-indexed web fetch result for URL: ...` - per web_fetch
- `Auto-indexed browser snapshot for URL: ...` - per browser_snapshot
- `Indexed email ... into long-term memory` - per email

### Logs da Cercare
```bash
# Nel terminale dove gira il backend, cerca:
grep -i "auto-indexed\|indexed.*memory" backend/logs/backend.log

# Oppure guarda i log in tempo reale:
tail -f backend/logs/backend.log | grep -i "index"
```

## 📊 Verifica Risultati Tool

Nei risultati dei tool, dovresti vedere una chiave `indexing_stats`:
```json
{
  "success": true,
  "result": { ... },
  "indexing_stats": {
    "indexed": 2,
    "total": 2,
    "skipped": 0
  }
}
```

## 🐛 Troubleshooting

### Se l'indicizzazione non funziona:
1. **Verifica che `auto_index=True`** sia passato a `execute_tool`
2. **Verifica che `session_id`** sia fornito
3. **Controlla i log** per errori di indicizzazione:
   ```
   Failed to auto-index web search results: ...
   ```
4. **Verifica MemoryManager** sia inizializzato:
   - Dovrebbe essere inizializzato in `dependencies.py`
   - ChromaDB dovrebbe essere attivo

### Se la memoria non viene recuperata:
1. **Verifica ChromaDB** sia attivo e raggiungibile
2. **Controlla i log** per query alla memoria:
   ```
   Checking files for session ...: found X embeddings in ChromaDB
   ```
3. **Verifica importanza score** - contenuti con score troppo basso potrebbero non essere recuperati

## ✅ Checklist Test Completo

- [ ] Test 1: web_search indicizza risultati
- [ ] Test 2: web_fetch indicizza contenuto pagina
- [ ] Test 3: browser_snapshot indicizza snapshot
- [ ] Test 4: Memoria recuperata in query successive
- [ ] Test 5: Record presenti in database PostgreSQL
- [ ] Test 6: Embeddings presenti in ChromaDB
- [ ] Test 7: Log mostrano indicizzazione corretta
- [ ] Test 8: `indexing_stats` presente nei risultati tool

