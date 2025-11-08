# Fix: Perché llama-server si ferma

## Problema Identificato

`llama-server` si fermava quando:
1. **Il terminale si chiudeva**: Il processo riceveva `SIGHUP` (hangup signal)
2. **Il Mac andava in sleep**: Alcuni processi vengono terminati durante il sleep
3. **Il parent process terminava**: Anche se il processo era in background, non era protetto

## Causa Root

Lo script `start_llama_background.sh` avviava `llama-server` con `&` ma **senza protezione da SIGHUP**:

```bash
llama-server ... > "$LOG_FILE" 2>&1 &  # ❌ Non protetto da SIGHUP
```

Quando il terminale si chiude o il parent process termina, il processo riceve `SIGHUP` e viene terminato.

## Soluzione Implementata

Ho modificato lo script per usare `nohup` e `disown`:

```bash
nohup llama-server ... > "$LOG_FILE" 2>&1 &  # ✅ Protetto da SIGHUP
PID=$!
disown $PID  # ✅ Rimuove dalla job table della shell
```

### Cosa fa `nohup`:
- **Ignora SIGHUP**: Il processo non viene terminato quando il terminale si chiude
- **Reindirizza output**: Se non specificato, reindirizza a `nohup.out`
- **Protegge da disconnessione**: Il processo continua anche se il parent termina

### Cosa fa `disown`:
- **Rimuove dalla job table**: Il processo non è più associato alla shell
- **Previene terminazione**: Se la shell termina, il processo continua

## Verifica

Dopo il fix, `llama-server` dovrebbe:
- ✅ Continuare anche se chiudi il terminale
- ✅ Continuare anche se il Mac va in sleep
- ✅ Continuare anche se il parent process termina

### Test

```bash
# Avvia llama-server
./scripts/start_llama_background.sh

# Chiudi il terminale e verifica che sia ancora in esecuzione
ps aux | grep llama-server | grep -v grep

# Dovresti vedere il processo ancora attivo
```

## Alternative (già implementate)

Se il problema persiste, usa:

1. **Monitor automatico** (`start_llama_background_monitored.sh`):
   - Rileva se llama-server si ferma
   - Lo riavvia automaticamente

2. **launchd** (`com.pallotta.llama-background.plist`):
   - Avvio automatico all'avvio del Mac
   - Riavvio automatico se si ferma (KeepAlive)
   - Gestione completa del ciclo di vita

## Note

- `nohup` è la soluzione più semplice e diretta
- `launchd` è la soluzione più robusta per produzione
- Il monitor è utile come fallback se ci sono crash del processo stesso

