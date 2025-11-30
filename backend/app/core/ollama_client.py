import httpx
from typing import List, Dict, Optional, Any
from app.core.config import settings
from app.core.system_prompts import get_base_self_awareness_prompt
import json


class OllamaClient:
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize Ollama client.
        
        Args:
            base_url: Ollama base URL (default: settings.ollama_base_url)
            model: Ollama model name (default: settings.ollama_model)
        """
        self.base_url = base_url or settings.ollama_base_url
        self.model = model or settings.ollama_model
        # Use longer timeout for background agent (phi3:mini can be very slow)
        # Increased timeouts to handle Gmail API calls and LangGraph execution
        actual_base_url = self.base_url
        timeout_value = 600.0 if actual_base_url == settings.ollama_background_base_url else 300.0  # 10 minutes for background, 5 minutes for main
        self.client = httpx.AsyncClient(timeout=timeout_value)

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
        from app.core.tracing import trace_span, set_trace_attribute, add_trace_event
        from app.core.metrics import increment_counter, observe_histogram
        import time
        
        start_time = time.time()
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
        
        with trace_span("llm.generate", {
            "llm.model": self.model,
            "llm.stream": str(stream),
            "llm.messages_count": len(messages),
            "llm.prompt_length": len(prompt)
        }):
            set_trace_attribute("llm.model", self.model)
            add_trace_event("llm.request.started", {"model": self.model})
            
            increment_counter("llm_requests_total", labels={"model": self.model, "stream": str(stream)})
            
            try:
                response = await self.client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
                
                duration = time.time() - start_time
                observe_histogram("llm_request_duration_seconds", duration, labels={"model": self.model, "stream": str(stream)})
                
                # Extract response length if available
                response_text = result.get("message", {}).get("content", "")
                if response_text:
                    set_trace_attribute("llm.response_length", len(response_text))
                    add_trace_event("llm.response.completed", {
                        "model": self.model,
                        "response_length": len(response_text)
                    })
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                observe_histogram("llm_request_duration_seconds", duration, labels={"model": self.model, "error": "true"})
                increment_counter("llm_requests_errors_total", labels={"model": self.model, "error_type": type(e).__name__})
                add_trace_event("llm.response.error", {"model": self.model, "error": str(e)})
                raise

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
        disable_safety_filters: bool = False,  # Ignored for Ollama (no safety filters), kept for compatibility
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
        # System prompt for Ollama - uses web_search tool
        base_system_prompt = """You are Knowledge Navigator, a personal AI assistant that helps users manage information, knowledge, and daily activities.

You have access to multi-level memory (short/medium/long-term), integrations (Gmail, Calendar, web search), and tools to perform actions.

CRITICAL - Tool Usage Rules:
1. EMAIL: When the user asks to read, view, check emails, or questions like "are there unread emails?", "new emails", "read emails" → ALWAYS use get_emails (NOT web_search)
2. CALENDAR: When the user asks about events, appointments, meetings, commitments → use get_calendar_events (NOT web_search)
3. WEB SEARCH: Use web_search ONLY for general information that is NOT email/calendar related (e.g., "search for information about X", "news about Y")
4. NEVER use web_search for questions about the user's email or calendar

Examples:
- "Are there unread emails?" → use get_emails with query='is:unread'
- "What do I have in my calendar tomorrow?" → use get_calendar_events
- "Search for information about Python" → use web_search
- "Today's emails" → use get_emails (NOT web_search)

Respond naturally and directly based on the data obtained from tools. Use clear, factual language and avoid unnecessary complexity."""
        
        enhanced_system = system_prompt or base_system_prompt
        
        # Add self-awareness prompt
        self_awareness_prompt = get_base_self_awareness_prompt()
        
        # Add time/location context if provided
        time_context = getattr(self, '_time_context', None)
        if time_context:
            enhanced_system = self_awareness_prompt + "\n\n" + time_context + "\n\n" + enhanced_system
        else:
            enhanced_system = self_awareness_prompt + "\n\n" + enhanced_system
        
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
            
            # Check if any memory contains file content
            has_file_content = any("[Content from uploaded file" in mem or "uploaded file" in mem.lower() for mem in retrieved_memory)
            
            if has_file_content:
                memory_context += "\n🚨🚨🚨 CRITICAL: DISTINGUERE TRA FILE CARICATI E FILE DRIVE 🚨🚨🚨\n\n"
                memory_context += "=== FILE CARICATI NELLA SESSIONE (IN MEMORIA) ===\n"
                memory_context += "I file con il prefisso '[Content from uploaded file]' sono stati CARICATI DIRETTAMENTE nella sessione corrente.\n"
                memory_context += "Questi file sono GIÀ DISPONIBILI nel contesto e NON richiedono tool.\n\n"
                memory_context += "QUANDO L'UTENTE CHIEDE DI:\n"
                memory_context += "- 'riassumi il file', 'analizza il file', 'spiegami il file'\n"
                memory_context += "- 'riassumi il documento', 'cosa contiene il file'\n"
                memory_context += "- 'ultimo file', 'file caricato', 'file in memoria'\n"
                memory_context += "→ Cerca '[Content from uploaded file]' nel contesto sopra e usa quel contenuto DIRETTAMENTE.\n"
                memory_context += "→ NON usare tool - il contenuto è già disponibile.\n\n"
                memory_context += "=== FILE SU GOOGLE DRIVE ===\n"
                memory_context += "I file su Google Drive NON sono nel contesto e richiedono tool specifici.\n\n"
                memory_context += "QUANDO L'UTENTE CHIEDE DI:\n"
                memory_context += "- 'file su Drive', 'file su Google Drive', 'file Drive'\n"
                memory_context += "- 'leggi il file [nome] su Drive', 'apri il file [nome] da Drive'\n"
                memory_context += "- 'file con ID [id] su Drive', 'file Drive con nome [nome]'\n"
                memory_context += "→ Usa il tool 'mcp_get_drive_file_content' o 'drive_get_file' per accedere al file.\n"
                memory_context += "→ Questi file NON sono nel contesto e devono essere recuperati da Drive.\n\n"
                memory_context += "REGOLA GENERALE:\n"
                memory_context += "1. Se vedi '[Content from uploaded file]' → usa quel contenuto direttamente (NO tool)\n"
                memory_context += "2. Se l'utente menziona 'Drive', 'Google Drive', o un nome file specifico non nel contesto → usa tool Drive\n"
                memory_context += "3. Se l'utente dice solo 'il file' senza menzionare Drive → probabilmente si riferisce al file caricato\n\n"
            else:
                memory_context += "\n🚨 CRITICAL INSTRUCTIONS - DISTINGUERE TRA FILE CARICATI E FILE DRIVE:\n\n"
                memory_context += "=== FILE CARICATI NELLA SESSIONE ===\n"
                memory_context += "Se vedi '[Content from uploaded file]' nel contesto sopra, quello è un file CARICATO nella sessione.\n"
                memory_context += "Usa quel contenuto DIRETTAMENTE senza tool.\n\n"
                memory_context += "=== FILE SU GOOGLE DRIVE ===\n"
                memory_context += "Se l'utente menziona 'Drive', 'Google Drive', o un nome file specifico non nel contesto:\n"
                memory_context += "→ Usa 'mcp_get_drive_file_content' o 'drive_get_file' per accedere al file.\n\n"
                memory_context += "REGOLA: File caricati = già nel contesto (NO tool). File Drive = richiede tool.\n\n"
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
            # CRITICAL: Filter out web_search and web_fetch BEFORE converting to Ollama format
            # This is a safety net in case tool_manager didn't filter them correctly
            filtered_tools = []
            for tool in tools:
                tool_name = tool.get("name", "")
                # NEVER pass web_search or web_fetch to Ollama - they are internal tools
                # Ollama has its own web_search API that we call directly, not via tool calling
                if tool_name in ["web_search", "web_fetch"]:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"🚨🚨🚨 CRITICAL: Filtering out {tool_name} before passing to Ollama - this should have been filtered by tool_manager!")
                    continue
                filtered_tools.append(tool)
            
            # Convert our tool format to Ollama/OpenAI format
            ollama_tools = []
            for tool in filtered_tools:
                tool_name = tool.get("name", "")
                ollama_tool = {
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "description": tool.get("description", ""),
                        "parameters": tool.get("parameters", {}),
                    }
                }
                ollama_tools.append(ollama_tool)
            payload["tools"] = ollama_tools
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Passing {len(ollama_tools)} tools to Ollama in native format (filtered from {len(tools)} original tools)")
            # Log tool names for debugging
            tool_names = [t.get("function", {}).get("name", "unknown") for t in ollama_tools]
            mcp_tools = [n for n in tool_names if n.startswith("mcp_")]
            web_tools = [n for n in tool_names if "web" in n.lower()]
            logger.info(f"   Tool breakdown: {len(mcp_tools)} MCP tools, {len(web_tools)} web tools")
            if mcp_tools:
                logger.info(f"   MCP tools: {', '.join(mcp_tools[:5])}{'...' if len(mcp_tools) > 5 else ''}")
                # Log Drive tools specifically
                drive_tools = [n for n in tool_names if 'drive' in n.lower()]
                if drive_tools:
                    logger.info(f"   📁 Drive tools passed to LLM: {', '.join(drive_tools[:10])}{'...' if len(drive_tools) > 10 else ''}")
                else:
                    logger.warning(f"   ⚠️  No Drive tools found in tools passed to LLM!")
            if web_tools:
                logger.error(f"   🚨🚨🚨 CRITICAL: Web tools still found after filtering: {', '.join(web_tools)}")
            else:
                logger.info(f"   ✅ No web tools (web_search/web_fetch) in tools list - correctly filtered")
            
            # CRITICAL CHECK: Verify web_search is NOT in the list
            if "web_search" in tool_names:
                logger.warning(f"⚠️  web_search is STILL in tools passed to Ollama after filtering! Removing it.")
                logger.warning(f"   All tools: {tool_names}")
                import sys
                print(f"[OLLAMA_CLIENT] WARNING: web_search in tools list after filtering: {tool_names}", file=sys.stderr)
                # Remove it as a last resort
                ollama_tools = [t for t in ollama_tools if t.get("function", {}).get("name") not in ["web_search", "web_fetch"]]
                payload["tools"] = ollama_tools
                tool_names = [t.get("function", {}).get("name", "unknown") for t in ollama_tools]
                logger.warning(f"   Removed web_search/web_fetch as last resort. New tool count: {len(ollama_tools)}")
            else:
                logger.info(f"✅ Verified: web_search NOT in tools passed to Ollama")
        
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

