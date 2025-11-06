# Guida Test Miglioramenti Core

## 🎯 Funzionalità Testate

### 1. Auto-Apprendimento dalle Conversazioni ✅
Il sistema estrae automaticamente conoscenze importanti dalle conversazioni e le salva in memoria long-term.

**Come testare:**
1. Apri una chat nel frontend
2. Fai una conversazione che contenga informazioni importanti, ad esempio:
   ```
   Utente: "Il mio compleanno è il 15 marzo"
   AI: [risponde]
   Utente: "Preferisco lavorare al mattino"
   AI: [risponde]
   ```
3. Verifica nei log del backend:
   ```
   Auto-learned X knowledge items from conversation
   ```
4. In una nuova chat, chiedi: "Quando è il mio compleanno?"
   - L'AI dovrebbe ricordare: "Il tuo compleanno è il 15 marzo"

**Test automatico:**
```bash
cd backend
source venv/bin/activate
python test_core_improvements.py
```

### 2. Ricerca Semantica Avanzata (Hybrid Search) ✅
Ricerca che combina similarità semantica e keyword matching.

**Come testare via API:**
```bash
curl -X POST http://localhost:8000/api/memory/search/hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Python async programming",
    "n_results": 5,
    "semantic_weight": 0.7,
    "keyword_weight": 0.3
  }'
```

**Endpoint disponibili:**
- `POST /api/memory/search/hybrid` - Ricerca ibrida
- `GET /api/memory/search/suggest?query=...` - Suggerimenti query
- `GET /api/memory/search/cross-session?query=...` - Ricerca cross-sessione

**Parametri ricerca ibrida:**
- `query`: Query di ricerca
- `n_results`: Numero di risultati (default: 5)
- `semantic_weight`: Peso ricerca semantica (0.0-1.0, default: 0.7)
- `keyword_weight`: Peso keyword matching (0.0-1.0, default: 0.3)
- `min_importance`: Filtro importanza minima (opzionale)
- `content_type`: Filtro tipo contenuto (opzionale: "fact", "preference", "email", "web", ecc.)

### 3. Consolidamento Memoria ✅
Rimuove duplicati e memorie simili, consolidandole.

**Come testare via API:**
```bash
# Consolidare duplicati
curl -X POST "http://localhost:8000/api/memory/consolidate/duplicates?similarity_threshold=0.85"

# Sintetizzare memorie vecchie
curl -X POST "http://localhost:8000/api/memory/consolidate/summarize?days_old=90&max_memories=50"
```

**Parametri:**
- `similarity_threshold`: Soglia similarità per considerare duplicati (0.0-1.0, default: 0.85)
- `days_old`: Età minima memorie da sintetizzare (default: 90 giorni)
- `max_memories`: Numero massimo memorie da sintetizzare (default: 50)

## 📊 Risultati Test Automatici

Esegui il test completo:
```bash
cd backend
source venv/bin/activate
python test_core_improvements.py
```

**Output atteso:**
```
✅ Passed: 3/3
❌ Failed: 0/3

🎉 All tests passed!
```

## 🔍 Verifica Manuale

### Test Auto-Apprendimento in Chat Reale

1. **Crea una nuova sessione** nel frontend
2. **Fai una conversazione** con informazioni personali:
   ```
   Tu: "Il mio nome è Mario e lavoro come sviluppatore"
   AI: [risponde]
   Tu: "Il mio indirizzo email è mario@example.com"
   AI: [risponde]
   ```
3. **Attendi qualche secondo** (l'auto-learning è in background)
4. **Crea una nuova sessione** e chiedi:
   ```
   Tu: "Qual è il mio nome?"
   AI: Dovrebbe rispondere: "Il tuo nome è Mario"
   ```
5. **Verifica nei log del backend:**
   ```bash
   tail -f backend/logs/backend.log | grep "Auto-learned"
   ```

### Test Ricerca Ibrida

1. **Aggiungi contenuti** alla memoria (via chat o indicizzazione)
2. **Esegui ricerca ibrida** via API o integrazione frontend
3. **Verifica risultati** combinano:
   - Similarità semantica (embedding)
   - Keyword matching (Jaccard similarity)

### Test Consolidamento

1. **Aggiungi memorie duplicate** manualmente o via chat
2. **Esegui consolidamento** via API
3. **Verifica** che i duplicati siano stati rimossi e consolidati

## 🐛 Troubleshooting

### Auto-apprendimento non funziona
- Verifica che `use_memory=True` nella richiesta chat
- Controlla i log per errori: `tail -f backend/logs/backend.log | grep -i "auto-learning"`
- Verifica che Ollama sia raggiungibile

### Ricerca ibrida non trova risultati
- Verifica che ci siano memorie in long-term memory
- Controlla che ChromaDB sia attivo: `curl http://localhost:8001/api/v1/heartbeat`
- Prova a ridurre `min_importance` o rimuoverlo

### Consolidamento non rimuove duplicati
- Aumenta `similarity_threshold` se troppo basso
- Verifica che ci siano effettivamente memorie duplicate
- Controlla i log per errori

## 📝 Note

- L'auto-apprendimento viene eseguito in **background** per non bloccare le risposte
- La ricerca ibrida combina semantic search (70%) e keyword matching (30%) di default
- Il consolidamento viene eseguito manualmente via API (non automatico)

