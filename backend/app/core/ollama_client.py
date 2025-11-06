import httpx
from typing import List, Dict, Optional, Any
from app.core.config import settings
import json


class OllamaClient:
    def __init__(self):
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_model
        self.client = httpx.AsyncClient(timeout=120.0)

    async def generate(
        self,
        prompt: str,
        context: Optional[List[Dict[str, str]]] = None,
        system: Optional[str] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate a response from Ollama
        
        Args:
            prompt: User prompt
            context: List of previous messages in format [{"role": "user", "content": "..."}, ...]
            system: System prompt
            stream: Whether to stream the response
            
        Returns:
            Response from Ollama API
        """
        messages = []
        
        if system:
            messages.append({"role": "system", "content": system})
        
        if context:
            messages.extend(context)
        
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream,
        }
        
        response = await self.client.post(
            f"{self.base_url}/api/chat",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    async def generate_with_context(
        self,
        prompt: str,
        session_context: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        retrieved_memory: Optional[List[str]] = None,
        tools_description: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        format: Optional[str] = None,
        return_raw: bool = False,
    ) -> str:
        """
        Generate response with session context and retrieved memory
        
        Args:
            prompt: Current user prompt
            session_context: Previous messages in the session
            system_prompt: System prompt
            retrieved_memory: Retrieved memory content to include
        """
        # Build system prompt with memory if available
        base_system_prompt = """Sei Knowledge Navigator, un assistente AI personale avanzato che aiuta l'utente a gestire informazioni, conoscenze e attività quotidiane.

=== CHI SEI ===
Sei un assistente AI conversazionale integrato nel sistema Knowledge Navigator, progettato per:
- Aiutare l'utente a organizzare e recuperare informazioni personali
- Gestire calendario, email e comunicazioni
- Apprendere dalle conversazioni per migliorare nel tempo
- Fornire risposte basate su conoscenze acquisite e ricerche web

=== FUNZIONALITÀ PRINCIPALI ===

1. **Memoria Multi-Livello:**
   - Short-term: Contesto della conversazione corrente
   - Medium-term: Memoria persistente per sessione (30 giorni)
   - Long-term: Memoria condivisa tra tutte le sessioni - apprendi automaticamente da ogni conversazione
   - Puoi ricordare informazioni personali, preferenze, eventi, progetti e contatti

2. **Integrazioni:**
   - Google Calendar: Puoi leggere eventi e appuntamenti
   - Gmail: Puoi leggere e riassumere email
   - Ricerca Web: Puoi cercare informazioni su internet e indicizzarle in memoria
   - File: Puoi analizzare file PDF, DOCX, XLSX, TXT caricati dall'utente

3. **Capacità:**
   - Ricerca semantica avanzata: Trovi informazioni usando similarità semantica e keyword
   - Auto-apprendimento: Estrai automaticamente conoscenze importanti dalle conversazioni
   - Ricerca cross-sessione: Accedi a informazioni da tutte le sessioni precedenti
   - Tool calling intelligente: Decidi autonomamente quando usare tool esterni

=== COME FUNZIONI ===

- **Apprendimento Automatico:** Quando l'utente fornisce informazioni (nome, preferenze, eventi, ecc.), le estrai e le salvi in memoria long-term automaticamente
- **Ricerca Intelligente:** Quando l'utente chiede qualcosa, cerchi nella memoria multi-livello e, se necessario, fai ricerche web
- **Contesto Persistente:** Ricordi informazioni tra sessioni diverse - se l'utente dice qualcosa in una chat, puoi ricordarlo in un'altra

=== REGOLE IMPORTANTI PER LE RISPOSTE ===

1. **Domande vs Affermazioni:**
   - Se l'utente fa una DOMANDA, rispondi in modo completo e utile, cercando nella memoria e usando tool se necessario
   - Se l'utente fa un'AFFERMAZIONE o fornisce informazioni SENZA fare domande, rispondi brevemente:
     * "Ok", "Perfetto", "Capito", "D'accordo" sono risposte appropriate
     * Non è necessario cercare sempre una risposta elaborata
     * Riconosci semplicemente l'informazione ricevuta (verrà salvata automaticamente in memoria)

2. **Uso della Memoria:**
   - Quando l'utente chiede qualcosa, controlla PRIMA nella memoria se hai già quella informazione
   - Se hai informazioni rilevanti in memoria, usale per rispondere
   - Se non hai informazioni sufficienti, puoi fare ricerche web o chiedere chiarimenti

3. **Naturalità:**
   - Sii naturale e conversazionale
   - Non essere verboso quando non necessario
   - Mostra che ricordi informazioni precedenti quando rilevanti

=== ESEMPI DI COMPORTAMENTO ===

**Affermazioni (risposte brevi):**
- Utente: "Il mio nome è Mario" → Risposta: "Ok, Mario. Piacere di conoscerti!"
- Utente: "Preferisco lavorare al mattino" → Risposta: "Capito, preferisci il mattino."
- Utente: "Il mio compleanno è il 15 marzo" → Risposta: "Perfetto, il 15 marzo. Lo ricorderò."

**Domande (risposte complete):**
- Utente: "Qual è la capitale d'Italia?" → Risposta: [risposta dettagliata]
- Utente: "Cosa sai su Python?" → Risposta: [cerca in memoria e/o web, risposta dettagliata]
- Utente: "Quando è il mio compleanno?" → Risposta: [cerca in memoria, risposta con informazione ricordata]

**Uso della Memoria:**
- Se l'utente ha detto "Preferisco Python" in una sessione precedente, e ora chiede "Qual è il mio linguaggio preferito?", rispondi: "Preferisci Python" (dalla memoria)
- Se l'utente chiede "Cosa ho detto che mi interessa?", cerca nella memoria long-term per trovare interessi menzionati in precedenza"""
        
        enhanced_system = system_prompt or base_system_prompt
        
        # Add time/location context if provided
        time_context = getattr(self, '_time_context', None)
        if time_context:
            enhanced_system = time_context + "\n\n" + enhanced_system
        
        if retrieved_memory:
            # Format memory context more clearly
            memory_context = "\n\n=== IMPORTANT: Context Information from Files and Memory ===\n"
            memory_context += "The following information has been retrieved from uploaded files and previous conversations.\n"
            memory_context += "You MUST use this information to answer questions accurately.\n\n"
            
            for i, mem in enumerate(retrieved_memory, 1):
                # Truncate very long content to avoid timeout and token limits
                # For file content, show enough to understand but not overwhelm the model
                max_chars = 5000  # Increased from 2000, but still limited
                if len(mem) > max_chars:
                    memory_context += f"{i}. {mem[:max_chars]}... [content truncated - file is {len(mem)} chars total]\n\n"
                else:
                    memory_context += f"{i}. {mem}\n\n"
            
            memory_context += "\n=== End of Context Information ===\n"
            memory_context += "IMPORTANT: When the user asks about files or documents, use the information provided above.\n"
            memory_context += "You can see and read the file contents shown above. Reference specific details from the files when answering.\n"
            enhanced_system += memory_context
        
        # Add tools description if provided
        if tools_description:
            enhanced_system += tools_description
        
        # Prepare messages
        messages = []
        if enhanced_system:
            messages.append({"role": "system", "content": enhanced_system})
        
        messages.extend(session_context)
        messages.append({"role": "user", "content": prompt})
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        
        # Add tools if provided (native Ollama tool calling)
        if tools:
            # Convert our tool format to Ollama/OpenAI format
            ollama_tools = []
            for tool in tools:
                ollama_tool = {
                    "type": "function",
                    "function": {
                        "name": tool.get("name", ""),
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {}),
                    }
                }
                ollama_tools.append(ollama_tool)
            payload["tools"] = ollama_tools
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Passing {len(ollama_tools)} tools to Ollama in native format")
        
        # Add format if specified (for JSON mode)
        if format:
            payload["format"] = format
        
        response = await self.client.post(
            f"{self.base_url}/api/chat",
            json=payload,
        )
        response.raise_for_status()
        result = response.json()
        
        # Debug: log the structure if response is empty
        import logging
        logger = logging.getLogger(__name__)
        
        # Try different possible response structures
        content = ""
        tool_calls_from_api = None
        
        if "message" in result:
            message = result["message"]
            if isinstance(message, dict):
                content = message.get("content", "")
                # Check for tool_calls in the message structure (new Ollama format)
                if "tool_calls" in message and message["tool_calls"]:
                    tool_calls_from_api = message["tool_calls"]
                    logger.info(f"Found {len(tool_calls_from_api)} tool_calls in Ollama response structure")
                    # If content is empty but we have tool_calls, that's expected
                    if not content and tool_calls_from_api:
                        logger.info("Content is empty but tool_calls present - this is expected for tool calling")
            elif isinstance(message, str):
                content = message
        elif "response" in result:
            content = result["response"]
        elif "content" in result:
            content = result["content"]
        else:
            # Log the full structure for debugging
            logger.warning(f"Unexpected Ollama response structure: {list(result.keys())}")
            # Try to extract text from any field
            content = str(result).replace("{", "").replace("}", "").replace("'", "")
        
        # Parse tool_calls from Ollama's native format (OpenAI-compatible)
        # Standard format: message.tool_calls[] with {"function": {"name": "tool_name", "arguments": {...}}}
        converted_tool_calls = []
        if tool_calls_from_api:
            for tc in tool_calls_from_api:
                if "function" in tc:
                    func = tc["function"]
                    func_name = func.get("name", "")
                    func_args = func.get("arguments", {})
                    
                    # Parse arguments - Ollama may return string or dict
                    if isinstance(func_args, str):
                        try:
                            func_args = json.loads(func_args)
                        except json.JSONDecodeError:
                            logger.warning(f"Could not parse tool arguments as JSON: {func_args}")
                            continue
                    
                    if func_name and isinstance(func_args, dict):
                        converted_tool_calls.append({
                            "name": func_name,
                            "parameters": func_args
                        })
            
            if converted_tool_calls:
                logger.info(f"Parsed {len(converted_tool_calls)} tool calls from Ollama: {[tc['name'] for tc in converted_tool_calls]}")
            else:
                logger.warning(f"Could not parse tool_calls. Raw structure: {tool_calls_from_api}")
        
        if not content:
            logger.warning(f"Empty content from Ollama. Result keys: {list(result.keys())}")
            # Try one more time to extract content - sometimes it's nested differently
            if "message" in result:
                msg = result["message"]
                if isinstance(msg, dict):
                    # Check all possible content fields
                    for key in ["content", "text", "response", "output"]:
                        if key in msg and msg[key]:
                            content = str(msg[key])
                            logger.info(f"Found content in message.{key}")
                            break
                    # If still empty, try to get the entire message as string
                    if not content and isinstance(msg, dict):
                        # Sometimes content is just the dict itself converted to string
                        try:
                            import json
                            content = json.dumps(msg, ensure_ascii=False)
                            if content and len(content) > 10:  # Make sure it's not just "{}"
                                logger.info("Using message dict as JSON string")
                        except:
                            pass
        
        if return_raw:
            return {"content": content, "raw_result": result, "_parsed_tool_calls": converted_tool_calls, "_raw_tool_calls": tool_calls_from_api}
        else:
            return content

    async def list_models(self) -> List[str]:
        """List available Ollama models"""
        response = await self.client.get(f"{self.base_url}/api/tags")
        response.raise_for_status()
        data = response.json()
        return [model["name"] for model in data.get("models", [])]

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()

