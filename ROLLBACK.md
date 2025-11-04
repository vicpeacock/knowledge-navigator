# Rollback Guide

Questa guida spiega come fare rollback a versioni funzionanti del progetto.

## Versioni Disponibili

### v0.1.1-working (Current)
**Tag:** `v0.1.1-working`  
**Data:** 2025-11-04  
**Stato:** ✅ Funzionante  
**Descrizione:** Stato funzionante dopo Fase 1. Backend risponde correttamente a tutti gli endpoint.

### v0.1.0
**Tag:** `v0.1.0` (se presente)  
**Stato:** Versione iniziale

## Comandi per Rollback

### 1. Vedere tutte le versioni/tag disponibili
```bash
git tag -l
git log --oneline --decorate -10
```

### 2. Fare rollback a una versione specifica
```bash
# Rollback a v0.1.1-working
git checkout v0.1.1-working

# Oppure rollback a un commit specifico
git checkout <commit-hash>
```

### 3. Creare un branch da una versione funzionante
```bash
# Crea un branch da una versione funzionante
git checkout -b restore-working v0.1.1-working
```

### 4. Ripristinare solo file specifici
```bash
# Ripristina un file specifico da una versione
git checkout v0.1.1-working -- path/to/file.py
```

### 5. Vedere le differenze tra versioni
```bash
# Confronta la versione corrente con v0.1.1-working
git diff v0.1.1-working

# Confronta due versioni specifiche
git diff v0.1.0 v0.1.1-working
```

## Creare una Nuova Versione Funzionante

Quando raggiungi uno stato funzionante, crea un nuovo tag:

```bash
# 1. Committa le modifiche
git add -A
git commit -m "Descrizione delle modifiche"

# 2. Crea un tag
git tag -a v0.1.2-working -m "Descrizione dello stato funzionante"

# 3. (Opzionale) Push del tag al repository remoto
git push origin v0.1.2-working
```

## Best Practices

1. **Crea sempre un tag dopo ogni stato funzionante**
   - Dopo ogni fix importante
   - Dopo ogni feature completata e testata
   - Prima di modifiche significative

2. **Usa messaggi di commit descrittivi**
   - Spiega cosa è stato fatto
   - Indica lo stato funzionante

3. **Testa sempre prima di committare**
   - Verifica che il backend si avvii
   - Testa gli endpoint principali
   - Verifica che i dati siano preservati

4. **Mantieni un log delle versioni**
   - Aggiorna questo file quando crei nuove versioni
   - Documenta cosa funziona e cosa no in ogni versione

## Auto-Versioning

Il progetto include un sistema di auto-versioning che salva automaticamente lo stato prima di modifiche importanti.

### Script Disponibili

1. **auto_version.sh** - Script bash per auto-commits
2. **auto_version.py** - Script Python per auto-commits

### Uso

```bash
# Commit automatico dello stato corrente
./auto_version.sh commit "Before editing memory_manager"

# Crea snapshot prima di modifiche importanti
./auto_version.sh snapshot "Before major refactoring"

# Monitora file e committa automaticamente (in background)
./auto_version.sh watch
```

### Python

```bash
# Commit automatico
python auto_version.py commit "Before modifications"

# Snapshot
python auto_version.py snapshot "Before refactoring"

# Verifica stato corrente
python auto_version.py check
```

### Integrazione con Cursor/IDE

Il sistema può essere integrato con pre-commit hooks o chiamato manualmente prima di modifiche importanti.

## Stato Corrente

**Versione Attuale:** v0.1.2-auto-versioning  
**Data:** 2025-11-04  
**Changelog:** Sistema di auto-versioning aggiunto

**Versione Precedente:** v0.1.1-working  
**Data:** 2025-11-04  
**Funzionalità Verificate:**
- ✅ Backend si avvia correttamente
- ✅ Endpoint `/api/sessions/` funziona (8 sessioni caricate)
- ✅ Endpoint `/api/integrations/calendars/integrations` funziona
- ✅ Endpoint `/api/integrations/emails/integrations` funziona
- ✅ Endpoint `/api/integrations/mcp/integrations` funziona
- ✅ ChromaDB connesso e funzionante
- ✅ PostgreSQL connesso e funzionante
- ✅ Tutte le dipendenze installate (selenium, pywhatkit)

