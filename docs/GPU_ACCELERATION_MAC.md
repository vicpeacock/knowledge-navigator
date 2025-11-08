# GPU Acceleration su Mac - Ollama Background Agent

## Problema

Docker su macOS **non supporta nativamente l'accesso alla GPU Metal** a causa delle limitazioni del framework di virtualizzazione di Apple. Questo significa che Ollama eseguito in Docker non può utilizzare l'accelerazione GPU.

## Soluzioni

### Opzione 1: Ollama Nativo Multi-Istanza (Raccomandato per Mac)

Eseguire più istanze di Ollama in parallelo sul Mac (non in Docker) per sfruttare Metal:

1. **Installare Ollama nativo:**
   ```bash
   brew install ollama
   # oppure scaricare da https://ollama.com
   ```

2. **Avviare Ollama Main (porta 11434):**
   ```bash
   # Terminal 1
   ollama serve
   # Ollama sarà disponibile su http://localhost:11434
   ```

3. **Avviare Ollama Background (porta 11435):**
   ```bash
   # Terminal 2
   OLLAMA_HOST=0.0.0.0:11435 ollama serve
   # Oppure usando la variabile d'ambiente in modo permanente:
   export OLLAMA_HOST=0.0.0.0:11435
   ollama serve
   ```

4. **Configurare il backend:**
   - Modificare `backend/app/core/config.py`:
     ```python
     # Ollama Main (per chat)
     ollama_base_url: str = "http://localhost:11434"
     ollama_model: str = "gpt-oss:20b"  # Modello grande per chat
     
     # Ollama Background (per task in background)
     ollama_background_base_url: str = "http://localhost:11435"
     ollama_background_model: str = "llama3.2:3b"  # Modello piccolo per background
     ```

5. **Avviare automaticamente con launchd (opzionale):**
   
   Creare `~/Library/LaunchAgents/com.ollama.main.plist`:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>com.ollama.main</string>
       <key>ProgramArguments</key>
       <array>
           <string>/opt/homebrew/bin/ollama</string>
           <string>serve</string>
       </array>
       <key>RunAtLoad</key>
       <true/>
       <key>KeepAlive</key>
       <true/>
   </dict>
   </plist>
   ```
   
   Creare `~/Library/LaunchAgents/com.ollama.background.plist`:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>com.ollama.background</string>
       <key>ProgramArguments</key>
       <array>
           <string>/opt/homebrew/bin/ollama</string>
           <string>serve</string>
       </array>
       <key>EnvironmentVariables</key>
       <dict>
           <key>OLLAMA_HOST</key>
           <string>0.0.0.0:11435</string>
       </dict>
       <key>RunAtLoad</key>
       <true/>
       <key>KeepAlive</key>
       <true/>
   </dict>
   </plist>
   ```
   
   Caricare i servizi:
   ```bash
   launchctl load ~/Library/LaunchAgents/com.ollama.main.plist
   launchctl load ~/Library/LaunchAgents/com.ollama.background.plist
   ```

6. **Vantaggi:**
   - ✅ Accelera con Metal (GPU Mac)
   - ✅ Prestazioni migliori
   - ✅ Nessuna limitazione Docker
   - ✅ Due istanze separate (main e background)
   - ✅ Modelli diversi per scopi diversi

7. **Svantaggi:**
   - ⚠️ Richiede Ollama installato sul Mac
   - ⚠️ Non isolato in container
   - ⚠️ Consumo maggiore di risorse (due istanze)

### Opzione 2: Aumentare Risorse Docker Container

Anche senza GPU, aumentare CPU/RAM può aiutare:

```yaml
# docker-compose.yml
ollama-background:
  deploy:
    resources:
      limits:
        cpus: '4'  # Aumentare da 2 a 4
        memory: 16G  # Aumentare da 8G a 16G
```

### Opzione 3: Usare Ollama Main per Background Tasks

Se Ollama main è già in esecuzione nativamente (con Metal), usarlo anche per background:

```python
# backend/app/core/config.py
ollama_background_base_url: str = "http://localhost:11434"  # Stessa di Ollama main
ollama_background_model: str = "llama3.2:3b"  # Modello più piccolo per background
```

**Nota:** Questo potrebbe rallentare le risposte chat se il modello background è in uso.

## Ottimizzazioni Implementate

Per ridurre il carico sul LLM, abbiamo implementato:

1. **Fast Pre-filtering:**
   - Controllo veloce di date diverse (senza LLM)
   - Rilevamento di opposti diretti (single/sposato, ama/non ama)
   - Confidenza alta (0.9) per contraddizioni ovvie

2. **Limitazione Chiamate LLM:**
   - LLM chiamato solo per top 3 memorie più simili (se nessuna contraddizione trovata)
   - Skip LLM se fast check trova contraddizione

3. **Timeout Aumentato:**
   - 300s (5 minuti) per background agent
   - Processo completamente asincrono

## Test Performance

Per testare se Metal è attivo:

```bash
# Se Ollama è nativo
ollama run llama3.2:3b "Say hello"
# Dovrebbe essere veloce con Metal

# Verificare utilizzo GPU
# Activity Monitor > Window > GPU History
```

## Raccomandazione

Per Mac con Apple Silicon (M1/M2/M3), **Opzione 1 (Ollama Nativo)** è la migliore per prestazioni.

