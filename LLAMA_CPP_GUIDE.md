# Guida Completa a llama.cpp su Mac

## Modelli Supportati

llama.cpp supporta una **vasta gamma di modelli LLM** in formato **GGUF** (GPT-Generated Unified Format). Ecco i principali:

### Modelli Meta (LLaMA)
- **Llama 3.2** - 1B, 3B, 11B, 70B, 405B
- **Llama 3.1** - 8B, 70B, 405B
- **Llama 3** - 8B, 70B
- **Llama 2** - 7B, 13B, 70B, 34B
- **Llama 1** - 7B, 13B, 30B, 65B

### Modelli Mistral AI
- **Mistral 7B** - Modello efficiente e performante
- **Mixtral 8x7B** - MoE (Mixture of Experts), 8 esperti da 7B
- **Mistral Small** - 1.2B
- **Mistral Medium** - Variante più grande

### Modelli Google
- **Gemma** - 2B, 7B
- **Gemma 2** - 2B, 9B, 27B

### Modelli Microsoft
- **Phi-3** - Mini (3.8B), Medium (14B), Large
- **Phi-2** - 2.7B
- **Phi-1.5** - 1.3B

### Modelli Alibaba
- **Qwen** - 0.5B, 1.5B, 2.5B, 4B, 7B, 14B, 32B, 72B
- **Qwen2** - 0.5B, 1.5B, 3B, 7B, 14B, 32B, 72B
- **Qwen2.5** - 0.5B, 1.5B, 3B, 7B, 14B, 32B, 72B

### Altri Modelli Popolari
- **Falcon** - 7B, 40B, 180B
- **Solar** - 10.7B
- **Yi** - 6B, 34B
- **Stable LM** - 1.6B, 3B, 7B
- **OpenAssistant** - Vari modelli
- **Vicuna** - Varianti fine-tuned di LLaMA
- **Alpaca** - Varianti fine-tuned di LLaMA
- **WizardLM** - Varianti fine-tuned
- **CodeLlama** - Specializzato per codice (7B, 13B, 34B)

### Modelli Specializzati
- **CodeLlama** - Per generazione codice
- **StarCoder** - Per codice
- **DeepSeek Coder** - Per codice
- **Nous Hermes** - Fine-tuned per conversazioni

## Formato GGUF

Tutti i modelli devono essere in formato **GGUF** (Ggerganov's Unified Format):
- ✅ Formato ottimizzato per llama.cpp
- ✅ Supporta quantizzazione (1.5-bit, 2-bit, 3-bit, 4-bit, 5-bit, 6-bit, 8-bit, f16, f32)
- ✅ Riduce dimensioni file e uso memoria
- ✅ Migliora tempi di caricamento

## Quantizzazione

llama.cpp supporta diversi livelli di quantizzazione:

| Quantizzazione | Dimensione | Qualità | Velocità |
|----------------|------------|---------|----------|
| **Q8_0** | ~100% | Eccellente | Media |
| **Q6_K** | ~75% | Molto Buona | Buona |
| **Q5_K_M** | ~62% | Buona | Buona |
| **Q4_K_M** | ~50% | Buona | Veloce |
| **Q3_K_M** | ~37% | Media | Veloce |
| **Q2_K** | ~25% | Bassa | Molto Veloce |

**Raccomandazione:** Q4_K_M o Q5_K_M per buon equilibrio qualità/velocità.

## Installazione su Mac

### Metodo 1: Homebrew (Più Semplice)

```bash
# Installare llama.cpp
brew install llama.cpp

# Verificare installazione
llama-server --help
```

### Metodo 2: Compilare da Sorgente (Più Controllo)

```bash
# Clonare repository
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp

# Compilare con supporto Metal (per Apple Silicon)
make clean
LLAMA_METAL=1 make -j

# I binari saranno in ./bin/
# - llama-server: server HTTP
# - llama-cli: CLI per test
```

### Metodo 3: Pre-compilato

```bash
# Scaricare release da GitHub
# https://github.com/ggerganov/llama.cpp/releases
```

## Download Modelli

### Opzione 1: Hugging Face (Raccomandato)

```bash
# Usare huggingface-cli
pip install huggingface-hub

# Scaricare modello (esempio: Llama 3.2 3B Q4_K_M)
huggingface-cli download TheBloke/Llama-3.2-3B-Instruct-GGUF \
  llama-3.2-3b-instruct-q4_k_m.gguf \
  --local-dir ./models

# Altri esempi:
# Qwen2.5 3B
huggingface-cli download Qwen/Qwen2.5-3B-Instruct-GGUF \
  qwen2.5-3b-instruct-q4_k_m.gguf \
  --local-dir ./models

# Phi-3 Mini
huggingface-cli download microsoft/Phi-3-mini-4k-instruct-gguf \
  Phi-3-mini-4k-instruct-q4_k_m.gguf \
  --local-dir ./models
```

### Opzione 2: TheBloke (Popolare per GGUF)

TheBloke su Hugging Face converte molti modelli in GGUF:
- https://huggingface.co/TheBloke

Esempi popolari:
- `TheBloke/Llama-3.2-3B-Instruct-GGUF`
- `TheBloke/Qwen2.5-3B-Instruct-GGUF`
- `TheBloke/Mistral-7B-Instruct-v0.2-GGUF`
- `TheBloke/Phi-3-mini-4k-instruct-GGUF`

### Opzione 3: Manuale

1. Andare su Hugging Face
2. Cercare modello + "GGUF"
3. Scaricare file `.gguf`
4. Salvare in `./models/`

## Esecuzione Modelli

### Metodo 1: Server HTTP (Raccomandato per API)

```bash
# Avviare server su porta 8080
./llama-server \
  -m ./models/llama-3.2-3b-instruct-q4_k_m.gguf \
  -p 8080 \
  --ctx-size 4096 \
  --threads 8 \
  --n-gpu-layers 1

# Con Metal (Apple Silicon)
./llama-server \
  -m ./models/llama-3.2-3b-instruct-q4_k_m.gguf \
  -p 8080 \
  --ctx-size 4096 \
  --threads 8 \
  --n-gpu-layers 999  # Usa tutte le layer su GPU
```

### Metodo 2: CLI (Per Test)

```bash
# Eseguire modello
./llama-cli \
  -m ./models/llama-3.2-3b-instruct-q4_k_m.gguf \
  -p "Ciao, come stai?" \
  --ctx-size 4096 \
  --threads 8 \
  --n-gpu-layers 999
```

### Metodo 3: Multi-Istanza (Parallelo)

```bash
# Terminal 1 - Istanza 1 (porta 8080)
./llama-server \
  -m ./models/llama-3.2-3b-instruct-q4_k_m.gguf \
  -p 8080 \
  --n-gpu-layers 999

# Terminal 2 - Istanza 2 (porta 8081)
./llama-server \
  -m ./models/qwen2.5-3b-instruct-q4_k_m.gguf \
  -p 8081 \
  --n-gpu-layers 999
```

## API Compatibile OpenAI

llama-server supporta API compatibile OpenAI:

```bash
# Avviare con flag --api
./llama-server \
  -m ./models/llama-3.2-3b-instruct-q4_k_m.gguf \
  -p 8080 \
  --api \
  --n-gpu-layers 999
```

Poi usare come OpenAI:
```python
import openai

client = openai.OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="not-needed"
)

response = client.chat.completions.create(
    model="llama-3.2-3b",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

## Configurazione per Knowledge Navigator

### 1. Installare llama.cpp

```bash
brew install llama.cpp
```

### 2. Creare Directory Modelli

```bash
mkdir -p ~/models/llama-cpp
```

### 3. Scaricare Modelli

```bash
# Modello per background agent (piccolo)
cd ~/models/llama-cpp
huggingface-cli download TheBloke/Llama-3.2-3B-Instruct-GGUF \
  llama-3.2-3b-instruct-q4_k_m.gguf \
  --local-dir .

# Modello per chat (grande, opzionale)
huggingface-cli download TheBloke/Llama-3.1-8B-Instruct-GGUF \
  llama-3.1-8b-instruct-q4_k_m.gguf \
  --local-dir .
```

### 4. Avviare Server Background

```bash
# Creare script: ~/scripts/llama-background.sh
#!/bin/bash
llama-server \
  -m ~/models/llama-cpp/llama-3.2-3b-instruct-q4_k_m.gguf \
  -p 11435 \
  --api \
  --ctx-size 4096 \
  --threads 8 \
  --n-gpu-layers 999 \
  --keep-alive 5m

# Rendere eseguibile
chmod +x ~/scripts/llama-background.sh
```

### 5. Modificare Config Backend

```python
# backend/app/core/config.py
ollama_background_base_url: str = "http://localhost:11435/v1"  # Nota /v1 per OpenAI API
ollama_background_model: str = "llama-3.2-3b"  # Nome modello
```

### 6. Creare Adapter per llama.cpp

```python
# backend/app/core/llama_cpp_client.py
import httpx
from typing import Optional, List, Dict, Any

class LlamaCppClient:
    def __init__(self, base_url: str, model: str):
        self.base_url = base_url
        self.model = model
        self.client = httpx.AsyncClient(timeout=300.0)
    
    async def generate_with_context(
        self,
        prompt: str,
        session_context: List[Dict[str, str]] = None,
        **kwargs
    ) -> str:
        # Usare API compatibile OpenAI
        messages = session_context or []
        messages.append({"role": "user", "content": prompt})
        
        response = await self.client.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "messages": messages,
                "temperature": 0.7,
            }
        )
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
```

## Modelli Consigliati per Mac

### Per Background Agent (Piccolo, Veloce)
- **Llama 3.2 3B Q4_K_M** - ~2GB, buone prestazioni
- **Qwen2.5 3B Q4_K_M** - ~2GB, multilingue
- **Phi-3 Mini Q4_K_M** - ~2.3GB, molto veloce
- **Gemma 2B Q4_K_M** - ~1.5GB, leggero

### Per Chat (Grande, Qualità)
- **Llama 3.1 8B Q4_K_M** - ~5GB, ottima qualità
- **Mistral 7B Q4_K_M** - ~4.5GB, molto performante
- **Qwen2.5 7B Q4_K_M** - ~4.5GB, multilingue
- **Mixtral 8x7B Q4_K_M** - ~26GB, eccellente (richiede molta RAM)

## Performance su Mac

### Apple Silicon (M1/M2/M3)
- ✅ Supporto Metal nativo
- ✅ Memoria unificata (efficiente)
- ✅ Prestazioni eccellenti con `--n-gpu-layers 999`
- ✅ Consumo energetico ottimizzato

### Intel Mac
- ⚠️ Solo CPU (no Metal)
- ⚠️ Prestazioni inferiori
- ⚠️ Consumo energetico più alto

## Confronto con Ollama

| Caratteristica | llama.cpp | Ollama |
|----------------|-----------|--------|
| **Prestazioni** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **Facilità** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Modelli** | Molti (GGUF) | Molti (proprietario) |
| **Metal/GPU** | ✅ | ✅ |
| **API OpenAI** | ✅ | ✅ |
| **Multi-Istanza** | ✅ | ✅ |
| **Quantizzazione** | ✅✅ | ✅ |

## Prossimi Passi

1. **Installare llama.cpp:**
   ```bash
   brew install llama.cpp
   ```

2. **Scaricare modello di test:**
   ```bash
   huggingface-cli download TheBloke/Llama-3.2-3B-Instruct-GGUF \
     llama-3.2-3b-instruct-q4_k_m.gguf \
     --local-dir ~/models/llama-cpp
   ```

3. **Testare:**
   ```bash
   llama-server -m ~/models/llama-cpp/llama-3.2-3b-instruct-q4_k_m.gguf \
     -p 8080 --api --n-gpu-layers 999
   ```

4. **Testare API:**
   ```bash
   curl http://localhost:8080/v1/models
   ```

## Risorse

- **GitHub:** https://github.com/ggerganov/llama.cpp
- **Documentazione:** https://github.com/ggerganov/llama.cpp/blob/master/README.md
- **Modelli GGUF:** https://huggingface.co/TheBloke
- **Lista Modelli Supportati:** https://github.com/ggml-org/llama.cpp/discussions/5141

