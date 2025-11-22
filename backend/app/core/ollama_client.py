import httpx
from typing import List, Dict, Optional, Any
from app.core.config import settings
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
        base_system_prompt = """Sei Knowledge Navigator, un assistente AI personale che aiuta l'utente a gestire informazioni, conoscenze e attività quotidiane.

Hai accesso a memoria multi-livello (short/medium/long-term), integrazioni (Gmail, Calendar, web), e tool per eseguire azioni.

IMPORTANTE - Regole per l'uso dei tool:
1. EMAIL: Se l'utente chiede di leggere, vedere, controllare email, o domande come "ci sono email non lette?", "email nuove", "leggi le email" → USA SEMPRE get_emails (NON web_search)
2. CALENDARIO: Se l'utente chiede eventi, appuntamenti, meeting, impegni → USA get_calendar_events (NON web_search)
3. WEB SEARCH: Usa web_search SOLO per informazioni generali che NON sono email/calendario (es: "cerca informazioni su X", "notizie su Y")
4. MAI usare web_search per domande su email o calendario dell'utente

Esempi:
- "Ci sono email non lette?" → usa get_emails con query='is:unread'
- "Cosa ho in calendario domani?" → usa get_calendar_events
- "Cerca informazioni su Python" → usa web_search
- "Email di oggi" → usa get_emails (NON web_search)

Rispondi in modo naturale e diretto basandoti sui dati ottenuti dai tool."""
        
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

