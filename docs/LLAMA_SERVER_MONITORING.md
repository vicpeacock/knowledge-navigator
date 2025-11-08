# Monitoraggio e Riavvio Automatico llama-server

## Problema

`llama-server` può fermarsi per vari motivi:
- Crash del processo
- Problemi di memoria
- Sleep del Mac
- Errori non gestiti
- Kill manuale

## Soluzione: Monitoraggio Automatico

Ho creato uno script di monitoraggio che controlla ogni 30 secondi se `llama-server` è in esecuzione e lo riavvia automaticamente se si ferma.

### Script Creati

1. **`scripts/monitor_llama_background.sh`**: Monitor che controlla ogni 30 secondi
2. **`scripts/start_llama_background_monitored.sh`**: Avvia llama-server + monitor
3. **`scripts/com.pallotta.llama-background.plist`**: Configurazione launchd per avvio automatico

### Uso

#### Opzione 1: Avvio Manuale con Monitor

```bash
./scripts/start_llama_background_monitored.sh
```

Questo avvia:
- `llama-server` sulla porta 11435
- Monitor che controlla ogni 30 secondi e riavvia se necessario

#### Opzione 2: Avvio Automatico con launchd (Raccomandato)

```bash
# Copia il file plist in LaunchAgents
cp scripts/com.pallotta.llama-background.plist ~/Library/LaunchAgents/

# Carica il servizio
launchctl load ~/Library/LaunchAgents/com.pallotta.llama-background.plist

# Verifica che sia caricato
launchctl list | grep llama-background
```

Il servizio:
- Si avvia automaticamente all'avvio del Mac
- Si riavvia automaticamente se si ferma (KeepAlive)
- Log in `/tmp/llama-background-launchd.log`

### Verifica Stato

```bash
# Verifica se llama-server è in esecuzione
lsof -i :11435

# Verifica il monitor
ps aux | grep monitor_llama_background

# Controlla i log
tail -f /tmp/llama-background.log
tail -f /tmp/llama-monitor.log
```

### Fermare il Monitor

```bash
# Trova il PID del monitor
ps aux | grep monitor_llama_background | grep -v grep

# Ferma il monitor
kill <PID>

# Ferma llama-server
lsof -ti:11435 | xargs kill -9
```

### Disabilitare Avvio Automatico

```bash
# Scarica il servizio launchd
launchctl unload ~/Library/LaunchAgents/com.pallotta.llama-background.plist

# Rimuovi il file plist
rm ~/Library/LaunchAgents/com.pallotta.llama-background.plist
```

## Troubleshooting

### Monitor non riavvia llama-server

Verifica i permessi:
```bash
chmod +x scripts/monitor_llama_background.sh
chmod +x scripts/start_llama_background.sh
```

### launchd non avvia il servizio

Controlla i log:
```bash
tail -f /tmp/llama-background-launchd.log
tail -f /tmp/llama-background-launchd-error.log
```

Verifica che il percorso nello script sia corretto:
```bash
cat scripts/com.pallotta.llama-background.plist
```

### Porta 11435 occupata

```bash
# Trova il processo
lsof -i :11435

# Ferma il processo
kill <PID>
```

## Note

- Il monitor controlla ogni 30 secondi (configurabile in `CHECK_INTERVAL`)
- Se llama-server si ferma, viene riavviato automaticamente
- I log sono in `/tmp/llama-background.log` e `/tmp/llama-monitor.log`

