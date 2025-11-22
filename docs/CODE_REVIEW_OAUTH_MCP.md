# Code Review: OAuth/MCP Integration - Problemi Strutturali

## Data: 2025-11-21
## Scope: Flusso OAuth per Google Workspace MCP

---

## 🔴 PROBLEMI CRITICI IDENTIFICATI

### 1. **Duplicazione della Logica OAuth Detection**
**File coinvolti:**
- `backend/app/api/integrations/mcp.py` (linee 99-105, 201-205, 284-288, 390-395, 768-773, 1204-1209)
- `backend/app/core/mcp_client.py` (linee 157-161)
- `backend/app/core/tool_manager.py` (linee 1145-1150)

**Problema:**
La logica per determinare se un server è OAuth è duplicata in almeno 6 posti diversi:
```python
is_oauth_server = (
    "workspace" in server_url.lower() or
    "8003" in server_url or
    "google" in server_url.lower()
)
```

**Impatto:**
- Difficile mantenere consistenza
- Se cambia la logica, devi modificare 6+ posti
- Alto rischio di bug

**Soluzione proposta:**
Creare una funzione centralizzata:
```python
# backend/app/core/oauth_utils.py
def is_oauth_server(server_url: str, oauth_required: bool = False) -> bool:
    """Centralized OAuth server detection"""
    return (
        oauth_required or
        "workspace" in server_url.lower() or
        "8003" in server_url or
        "google" in server_url.lower()
    )
```

---

### 2. **Token Refresh Logic nel Tool Manager**
**File:** `backend/app/core/tool_manager.py` (linee 1155-1222)

**Problema:**
Il refresh del token OAuth è implementato dentro `execute_tool`, creando:
- Complessità ciclomatica alta (troppi if/else annidati)
- Potenziali race conditions (due chiamate simultanee potrebbero refreshare lo stesso token)
- Difficile testare
- Violazione del principio Single Responsibility

**Impatto:**
- Codice difficile da debuggare
- Possibili deadlock o timeout
- Difficile gestire edge cases

**Soluzione proposta:**
Estrarre la logica di refresh in un servizio dedicato:
```python
# backend/app/services/oauth_token_manager.py
class OAuthTokenManager:
    async def get_valid_token(
        self, 
        integration: IntegrationModel, 
        user: User,
        db: AsyncSession
    ) -> Optional[str]:
        """Get valid OAuth token, refreshing if needed"""
        # Centralized token retrieval and refresh logic
```

---

### 3. **Mancanza di Separazione delle Responsabilità**
**File:** `backend/app/api/integrations/mcp.py` - `_get_mcp_client_for_integration()`

**Problema:**
La funzione `_get_mcp_client_for_integration` fa troppe cose:
1. Risoluzione URL (Docker vs localhost)
2. Detection OAuth server
3. Retrieval e decrittazione OAuth credentials
4. Creazione MCPClient

**Impatto:**
- Funzione troppo lunga (100+ linee)
- Difficile testare singole parti
- Violazione Single Responsibility Principle

**Soluzione proposta:**
Scomporre in funzioni più piccole:
```python
def _resolve_mcp_url(server_url: str) -> str:
    """Resolve MCP URL (Docker vs localhost)"""

def _get_oauth_token_for_user(
    integration: IntegrationModel, 
    user: User
) -> Optional[str]:
    """Get OAuth token for user from integration"""

def _create_mcp_client(
    server_url: str,
    use_auth_token: bool,
    oauth_token: Optional[str]
) -> MCPClient:
    """Create MCP client with proper configuration"""
```

---

### 4. **Exception Handling Duplicato**
**File coinvolti:**
- `backend/app/api/integrations/mcp.py` (linee 248-277, 751-760)
- `backend/app/core/mcp_client.py` (linee 126-154)

**Problema:**
La logica per estrarre errori da ExceptionGroup/TaskGroup è duplicata in 3+ posti:
```python
# Duplicato in più file
if hasattr(e, 'exceptions') and len(e.exceptions) > 0:
    real_error = e.exceptions[0]
    # ... logica complessa per estrarre errore ...
```

**Impatto:**
- Codice duplicato
- Difficile mantenere consistenza

**Soluzione proposta:**
Funzione helper centralizzata:
```python
# backend/app/core/error_utils.py
def extract_root_error(error: Exception, max_depth: int = 5) -> Exception:
    """Extract root cause from ExceptionGroup/TaskGroup"""
```

---

### 5. **Caching dei Client MCP con Token Scaduti**
**File:** `backend/app/core/tool_manager.py` (linee 292-300)

**Problema:**
I client MCP sono cachati per chiave `{integration_id}_{user_id}`, ma:
- Il token OAuth dentro il client può scadere
- Il cache non viene invalidato quando il token viene refreshato
- Potrebbero essere usati client con token scaduti

**Impatto:**
- Possibili 401 anche dopo refresh del token
- Comportamento inconsistente

**Soluzione proposta:**
- Non cachare i client MCP (crearli fresh ogni volta)
- OPPURE invalidare il cache quando il token viene refreshato
- OPPURE cachare solo la configurazione, non il client stesso

---

### 6. **Gestione Errori Inconsistente**
**File:** Tutti i file OAuth/MCP

**Problema:**
Gli errori OAuth sono gestiti in modo diverso in posti diversi:
- A volte ritorna `{"error": "...", "oauth_required": True}`
- A volte solleva `HTTPException`
- A volte logga e continua
- A volte logga e solleva

**Impatto:**
- Difficile capire cosa succede quando c'è un errore
- Frontend riceve formati diversi di errore

**Soluzione proposta:**
Definire classi di errore standardizzate:
```python
# backend/app/core/exceptions.py
class OAuthTokenExpiredError(Exception):
    """OAuth token expired and refresh failed"""
    def __init__(self, integration_id: str, user_id: str):
        self.integration_id = integration_id
        self.user_id = user_id

class OAuthAuthenticationRequiredError(Exception):
    """OAuth authentication required"""
    def __init__(self, integration_id: str):
        self.integration_id = integration_id
```

---

### 7. **Mancanza di Logging Strutturato**
**Problema:**
I log sono inconsistenti:
- A volte usa `logger.info`, a volte `logger.warning`, a volte `logger.error`
- Non c'è un formato standard per i log OAuth
- Difficile tracciare il flusso completo di una richiesta OAuth

**Soluzione proposta:**
Usare logging strutturato con contesto:
```python
logger.info(
    "oauth_token_retrieved",
    extra={
        "integration_id": str(integration.id),
        "user_id": str(user.id),
        "has_refresh_token": bool(refresh_token),
    }
)
```

---

## 🟡 PROBLEMI MEDI

### 8. **Race Condition nel Token Refresh**
**File:** `backend/app/core/tool_manager.py` (linee 1175-1214)

**Problema:**
Se due richieste simultanee ricevono 401, entrambe potrebbero tentare di refreshare il token, causando:
- Doppio refresh (spreco)
- Possibili race conditions nel salvataggio

**Soluzione proposta:**
Usare un lock per serializzare i refresh:
```python
from asyncio import Lock

_refresh_locks: Dict[str, Lock] = {}

async def refresh_token_with_lock(integration_id: str, user_id: str):
    lock_key = f"{integration_id}_{user_id}"
    if lock_key not in _refresh_locks:
        _refresh_locks[lock_key] = Lock()
    
    async with _refresh_locks[lock_key]:
        # Refresh token logic
```

---

### 9. **Mancanza di Timeout per Token Refresh**
**File:** `backend/app/core/tool_manager.py` (linea 1181)

**Problema:**
Il refresh del token non ha timeout, potrebbe bloccare indefinitamente.

**Soluzione proposta:**
Aggiungere timeout:
```python
refresh_response = await asyncio.wait_for(
    http_client.post(...),
    timeout=10.0  # 10 secondi per refresh
)
```

---

### 10. **Hardcoded OAuth Scopes**
**File:** `backend/app/api/integrations/mcp.py` (linee 421-432, 581-592)

**Problema:**
Gli OAuth scopes sono hardcoded in due posti diversi. Se cambiano, devi modificare due liste.

**Soluzione proposta:**
Centralizzare in configurazione:
```python
# backend/app/core/config.py
GOOGLE_WORKSPACE_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    # ...
]
```

---

## 🟢 MIGLIORAMENTI SUGGERITI

### 11. **Unit Tests Mancanti**
Non ci sono test per:
- Token refresh logic
- OAuth error handling
- URL resolution (Docker vs localhost)

### 12. **Documentazione Inline**
Mancano docstring dettagliate per:
- `_get_mcp_client_for_integration`
- Token refresh flow
- OAuth error handling

---

## 📋 PIANO DI REFACTORING

### Fase 1: Centralizzazione (Bassa priorità, alta impatto)
1. Creare `oauth_utils.py` con funzioni helper
2. Creare `error_utils.py` per gestione errori
3. Estrarre OAuth scopes in configurazione

### Fase 2: Separazione Responsabilità (Media priorità)
1. Scomporre `_get_mcp_client_for_integration`
2. Creare `OAuthTokenManager` service
3. Spostare token refresh fuori da `tool_manager.py`

### Fase 3: Robustezza (Alta priorità)
1. Aggiungere lock per token refresh
2. Aggiungere timeout
3. Standardizzare error handling
4. Invalidare cache quando token refreshato

### Fase 4: Testing e Documentazione
1. Unit tests per OAuth flow
2. Integration tests
3. Documentazione inline

---

## 🎯 PRIORITÀ IMMEDIATE

1. **Risolvere il problema del backend bloccato** - Probabilmente causato da:
   - Timeout mancanti
   - Race conditions nel token refresh
   - Client MCP cachati con token scaduti

2. **Standardizzare error handling** - Per dare feedback chiaro al frontend

3. **Aggiungere timeout e lock** - Per prevenire deadlock

---

## 📝 NOTE

- Il codice funziona, ma è fragile e difficile da mantenere
- Le patch applicate hanno risolto problemi specifici ma hanno aumentato la complessità
- Serve un refactoring sistematico, non altre patch

