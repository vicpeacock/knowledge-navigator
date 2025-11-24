"""
Gemini Client Adapter - Compatible with OllamaClient interface

This adapter allows using Google Gemini API as a drop-in replacement for OllamaClient.
All methods maintain the same signature and return format as OllamaClient for seamless integration.
"""
import logging
from typing import List, Dict, Optional, Any
from app.core.config import settings
import json
import time

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("google-generativeai not installed. Install with: pip install google-generativeai")


class GeminiClient:
    """
    Gemini API client compatible with OllamaClient interface.
    
    This class provides the same methods as OllamaClient but uses Google Gemini API
    instead of Ollama. All responses are normalized to match Ollama's format.
    """
    
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize Gemini client.
        
        Args:
            base_url: Ignored for Gemini (uses API key instead)
            model: Gemini model name (default: settings.gemini_model)
        """
        if not GEMINI_AVAILABLE:
            raise ImportError(
                "google-generativeai is not installed. "
                "Install with: pip install google-generativeai"
            )
        
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is required but not set. "
                "Set it in your .env file or environment variables."
            )
        
        # Configure Gemini API
        genai.configure(api_key=settings.gemini_api_key)
        
        self.model_name = model or settings.gemini_model
        self.client = None  # Will be initialized on first use
        
    def _get_model(self):
        """Get or create Gemini model instance"""
        if self.client is None:
            self.client = genai.GenerativeModel(self.model_name)
        return self.client
    
    async def generate(
        self,
        prompt: str,
        context: Optional[List[Dict[str, str]]] = None,
        system: Optional[str] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate a response from Gemini (compatible with OllamaClient.generate)
        
        Args:
            prompt: User prompt
            context: List of previous messages in format [{"role": "user", "content": "..."}, ...]
            system: System prompt
            stream: Whether to stream the response (not fully supported yet)
            
        Returns:
            Response in Ollama-compatible format
        """
        from app.core.tracing import trace_span, set_trace_attribute, add_trace_event
        from app.core.metrics import increment_counter, observe_histogram
        
        start_time = time.time()
        
        # Build messages for Gemini
        messages = []
        if system:
            # Gemini uses system instruction differently
            # We'll prepend it to the first user message
            messages.append({"role": "user", "parts": [f"[SYSTEM]: {system}"]})
        
        if context:
            # Convert context messages to Gemini format
            for msg in context:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    # System messages are prepended to user messages
                    if messages and messages[-1]["role"] == "user":
                        messages[-1]["parts"][0] = f"[SYSTEM]: {content}\n\n{messages[-1]['parts'][0]}"
                    else:
                        messages.append({"role": "user", "parts": [f"[SYSTEM]: {content}"]})
                else:
                    messages.append({"role": role, "parts": [content]})
        
        # Add current prompt
        messages.append({"role": "user", "parts": [prompt]})
        
        with trace_span("llm.generate", {
            "llm.model": self.model_name,
            "llm.provider": "gemini",
            "llm.stream": str(stream),
            "llm.messages_count": len(messages),
            "llm.prompt_length": len(prompt)
        }):
            set_trace_attribute("llm.model", self.model_name)
            set_trace_attribute("llm.provider", "gemini")
            add_trace_event("llm.request.started", {"model": self.model_name, "provider": "gemini"})
            
            increment_counter("llm_requests_total", labels={"model": self.model_name, "provider": "gemini", "stream": str(stream)})
            
            try:
                model = self._get_model()
                
                # Convert messages to Gemini chat format
                # Gemini uses a chat history format with alternating user/assistant messages
                # Build history from context messages (all except the last one)
                history = []
                for i in range(0, len(messages) - 1):
                    msg = messages[i]
                    role = msg.get("role", "user")
                    parts = msg.get("parts", [])
                    if isinstance(parts, list) and len(parts) > 0:
                        content = parts[0]
                    else:
                        content = str(parts) if parts else ""
                    
                    # Gemini expects alternating user/model messages
                    if role == "user":
                        history.append({"role": "user", "parts": [content]})
                    elif role == "assistant":
                        # If last message was user, add model response
                        if history and history[-1]["role"] == "user":
                            history.append({"role": "model", "parts": [content]})
                        else:
                            # If no user message before, add empty user message
                            history.append({"role": "user", "parts": [""]})
                            history.append({"role": "model", "parts": [content]})
                
                # Start chat with history (empty if no history)
                if history:
                    chat = model.start_chat(history=history)
                else:
                    chat = model.start_chat(history=[])
                
                # Send the last message and get response
                last_msg = messages[-1]["parts"][0] if isinstance(messages[-1]["parts"], list) else str(messages[-1]["parts"])
                # Configure safety settings for generate() method too
                safety_settings_simple = None
                try:
                    import google.generativeai.types as genai_types
                    safety_settings_simple = [
                        {
                            "category": genai_types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                            "threshold": genai_types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                        },
                        {
                            "category": genai_types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                            "threshold": genai_types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                        },
                        {
                            "category": genai_types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                            "threshold": genai_types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                        },
                        {
                            "category": genai_types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                            "threshold": genai_types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                        },
                    ]
                except Exception:
                    pass
                
                send_kwargs = {}
                if safety_settings_simple:
                    send_kwargs["safety_settings"] = safety_settings_simple
                
                if stream:
                    # Streaming not fully implemented yet - return non-streaming for now
                    logger.warning("Streaming not fully supported for Gemini yet, using non-streaming")
                    response = await self._generate_async(chat, last_msg, **send_kwargs)
                else:
                    response = await self._generate_async(chat, last_msg, **send_kwargs)
                
                duration = time.time() - start_time
                observe_histogram("llm_request_duration_seconds", duration, labels={"model": self.model_name, "provider": "gemini", "stream": str(stream)})
                
                # Check for safety blocks (finish_reason = 1 = SAFETY)
                finish_reason = None
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'finish_reason'):
                        finish_reason = candidate.finish_reason
                
                # Convert Gemini response to Ollama format
                # Handle safety blocks (finish_reason = 1)
                if finish_reason == 1:  # SAFETY
                    logger.warning(f"Gemini response blocked by safety filters (finish_reason=1)")
                    response_text = "Mi dispiace, la mia risposta è stata bloccata dai filtri di sicurezza. Potresti riformulare la tua richiesta in modo diverso?"
                else:
                    try:
                        response_text = response.text if hasattr(response, 'text') else str(response)
                    except Exception as e:
                        # If response.text fails (e.g., finish_reason=1), provide fallback
                        logger.warning(f"Could not access response.text: {e}, finish_reason={finish_reason}")
                        response_text = "Mi dispiace, ho riscontrato un problema nella generazione della risposta. Potresti riprovare?"
                
                if response_text:
                    set_trace_attribute("llm.response_length", len(response_text))
                    add_trace_event("llm.response.completed", {
                        "model": self.model_name,
                        "provider": "gemini",
                        "response_length": len(response_text)
                    })
                
                # Return in Ollama-compatible format
                return {
                    "model": self.model_name,
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                    "message": {
                        "role": "assistant",
                        "content": response_text
                    },
                    "done": True
                }
            except Exception as e:
                duration = time.time() - start_time
                observe_histogram("llm_request_duration_seconds", duration, labels={"model": self.model_name, "provider": "gemini", "error": "true"})
                increment_counter("llm_requests_errors_total", labels={"model": self.model_name, "provider": "gemini", "error_type": type(e).__name__})
                add_trace_event("llm.response.error", {"model": self.model_name, "provider": "gemini", "error": str(e)})
                logger.error(f"Error calling Gemini API: {e}", exc_info=True)
                raise
    
    async def _generate_async(self, chat, message: str, generation_config: Optional[Dict[str, Any]] = None, safety_settings: Optional[List[Dict[str, Any]]] = None):
        """Helper to generate response asynchronously"""
        import asyncio
        loop = asyncio.get_event_loop()
        # Use run_in_executor to avoid blocking
        def _send():
            kwargs = {}
            if generation_config:
                kwargs["generation_config"] = generation_config
            if safety_settings:
                kwargs["safety_settings"] = safety_settings
            if kwargs:
                return chat.send_message(message, **kwargs)
            else:
                return chat.send_message(message)
        return await loop.run_in_executor(None, _send)
    
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
        disable_safety_filters: bool = False,  # New parameter: disable safety filters for tool result synthesis
    ) -> str:
        """
        Generate response with session context and retrieved memory (compatible with OllamaClient.generate_with_context)
        
        Args:
            prompt: Current user prompt
            session_context: Previous messages in the session
            system_prompt: System prompt
            retrieved_memory: Retrieved memory content to include
            tools_description: Description of available tools
            tools: List of tool definitions
            format: Response format (e.g., "json")
            return_raw: If True, return raw response dict instead of string
            
        Returns:
            Response text or raw dict if return_raw=True
        """
        from app.core.tracing import trace_span, set_trace_attribute, add_trace_event
        from app.core.metrics import increment_counter, observe_histogram
        
        start_time = time.time()
        
        # Build system prompt with memory if available
        base_system_prompt = """Sei Knowledge Navigator, un assistente AI personale che aiuta l'utente a gestire informazioni, conoscenze e attività quotidiane.

Hai accesso a memoria multi-livello (short/medium/long-term), integrazioni (Gmail, Calendar, web), e tool per eseguire azioni.

IMPORTANTE - Regole per l'uso dei tool:
1. EMAIL: Se l'utente chiede di leggere, vedere, controllare email, o domande come "ci sono email non lette?", "email nuove", "leggi le email" → USA SEMPRE get_emails (NON customsearch_search)
2. CALENDARIO: Se l'utente chiede eventi, appuntamenti, meeting, impegni → USA get_calendar_events (NON customsearch_search)
3. WEB SEARCH: Usa customsearch_search per informazioni generali che NON sono email/calendario (es: "cerca informazioni su X", "notizie su Y", "meteo a Bussigny", "informazioni sulla band Swisspulse")
4. MAI usare customsearch_search per domande su email o calendario dell'utente
5. CRITICO: Quando l'utente chiede di cercare informazioni sul web, DEVI SEMPRE chiamare customsearch_search - non dire che la chiave API non è configurata senza prima provare a chiamare il tool!

Esempi:
- "Ci sono email non lette?" → usa get_emails con query='is:unread'
- "Cosa ho in calendario domani?" → usa get_calendar_events
- "Cerca informazioni su Python" → usa customsearch_search
- "Informazioni sulla band Swisspulse" → usa customsearch_search
- "Meteo a Bussigny" → usa customsearch_search
- "Email di oggi" → usa get_emails (NON customsearch_search)

Rispondi in modo naturale e diretto basandoti sui dati ottenuti dai tool."""
        
        enhanced_system = system_prompt or base_system_prompt
        
        # Add time/location context if provided
        time_context = getattr(self, '_time_context', None)
        if time_context:
            enhanced_system = time_context + "\n\n" + enhanced_system
        
        if retrieved_memory:
            # Format memory context
            memory_context = "\n\n=== IMPORTANT: Context Information from Files and Memory ===\n"
            memory_context += "The following information has been retrieved from uploaded files and previous conversations.\n"
            memory_context += "You MUST use this information to answer questions accurately.\n\n"
            
            for i, mem in enumerate(retrieved_memory, 1):
                max_chars = 5000
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
        
        # Prepare messages for Gemini
        # Gemini supports system instructions via generation_config
        # We'll include system in the first user message
        messages = []
        system_content = enhanced_system if enhanced_system else ""
        
        # Add session context
        for msg in session_context:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            messages.append({"role": role, "parts": [content]})
        
        # Add current prompt
        messages.append({"role": "user", "parts": [prompt]})
        
        # Convert tools to Gemini function calling format
        gemini_tools = None
        if tools:
            # Filter out web_search and web_fetch (same as OllamaClient)
            filtered_tools = []
            for tool in tools:
                tool_name = tool.get("name", "")
                if tool_name in ["web_search", "web_fetch"]:
                    logger.warning(f"Filtering out {tool_name} before passing to Gemini")
                    continue
                filtered_tools.append(tool)
            
            # Convert to Gemini function declarations format
            gemini_tools = []
            for tool in filtered_tools:
                tool_name = tool.get("name", "")
                tool_desc = tool.get("description", "")
                tool_params = tool.get("parameters", {})
                
                try:
                    # Convert parameters to Gemini schema format
                    gemini_schema = self._convert_parameters_to_gemini_schema(tool_params)
                    
                    gemini_tools.append({
                        "function_declarations": [{
                            "name": tool_name,
                            "description": tool_desc,
                            "parameters": gemini_schema
                        }]
                    })
                except Exception as e:
                    logger.error(f"❌ Error converting tool {tool_name} to Gemini schema: {e}", exc_info=True)
                    logger.error(f"   Tool params: {tool_params}")
                    # Skip this tool but continue with others
                    continue
            
            if gemini_tools:
                logger.info(f"Passing {len(gemini_tools)} tools to Gemini (filtered from {len(tools)} original tools)")
                # Log tool names for debugging
                tool_names = [t.get("function_declarations", [{}])[0].get("name", "unknown") for t in gemini_tools]
                mcp_tools = [n for n in tool_names if n.startswith("mcp_")]
                logger.info(f"   Tool breakdown: {len(mcp_tools)} MCP tools")
                if mcp_tools:
                    logger.info(f"   MCP tools: {', '.join(mcp_tools[:10])}{'...' if len(mcp_tools) > 10 else ''}")
                    # Log Drive tools specifically
                    drive_tools = [n for n in tool_names if 'drive' in n.lower()]
                    if drive_tools:
                        logger.info(f"   📁 Drive tools passed to Gemini: {', '.join(drive_tools[:10])}{'...' if len(drive_tools) > 10 else ''}")
                # Log customsearch_search specifically
                if "customsearch_search" in tool_names:
                    logger.info(f"   ✅ customsearch_search is available to Gemini")
                    # Find and log the tool details
                    for tool in gemini_tools:
                        func_decl = tool.get("function_declarations", [{}])[0]
                        if func_decl.get("name") == "customsearch_search":
                            logger.info(f"   📋 customsearch_search details: name={func_decl.get('name')}, description length={len(func_decl.get('description', ''))}")
                            logger.info(f"   📋 customsearch_search description preview: {func_decl.get('description', '')[:100]}...")
                            break
                else:
                    logger.warning(f"   ⚠️  customsearch_search NOT in tools passed to Gemini!")
                    logger.warning(f"   Available tools: {', '.join(tool_names[:20])}{'...' if len(tool_names) > 20 else ''}")
        
        # Set response format if specified
        generation_config = {}
        if format == "json":
            generation_config["response_mime_type"] = "application/json"
        
        # Configure safety settings
        # When synthesizing tool results, we can disable safety filters to avoid blocking legitimate content
        # For normal interactions, we use BLOCK_ONLY_HIGH to block only the most harmful content
        # NOTE: safety_settings must be passed to the model, NOT to GenerationConfig
        logger.info(f"🔍 Safety settings configuration: disable_safety_filters={disable_safety_filters}")
        safety_settings = None
        try:
            import google.generativeai.types as genai_types
            logger.info(f"🔍 Successfully imported genai_types")
            if disable_safety_filters:
                logger.info(f"🔍 Configuring BLOCK_NONE safety settings...")
                # Disable all safety filters for tool result synthesis
                # This is safe because tool results come from trusted sources (our own tools)
                safety_settings = [
                    {
                        "category": genai_types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                        "threshold": genai_types.HarmBlockThreshold.BLOCK_NONE,
                    },
                    {
                        "category": genai_types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                        "threshold": genai_types.HarmBlockThreshold.BLOCK_NONE,
                    },
                    {
                        "category": genai_types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                        "threshold": genai_types.HarmBlockThreshold.BLOCK_NONE,
                    },
                    {
                        "category": genai_types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                        "threshold": genai_types.HarmBlockThreshold.BLOCK_NONE,
                    },
                ]
                logger.info(f"🔓 Disabled safety filters for tool result synthesis (BLOCK_NONE). Settings: {safety_settings}")
            else:
                logger.info(f"🔍 Configuring BLOCK_ONLY_HIGH safety settings...")
                # Block only the most harmful content (BLOCK_ONLY_HIGH) for normal interactions
                safety_settings = [
                    {
                        "category": genai_types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                        "threshold": genai_types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                    },
                    {
                        "category": genai_types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                        "threshold": genai_types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                    },
                    {
                        "category": genai_types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                        "threshold": genai_types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                    },
                    {
                        "category": genai_types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                        "threshold": genai_types.HarmBlockThreshold.BLOCK_ONLY_HIGH,
                    },
                ]
                logger.debug("✅ Configured Gemini safety settings to BLOCK_ONLY_HIGH")
        except Exception as e:
            logger.error(f"❌ Could not configure safety settings: {e}", exc_info=True)
            logger.warning(f"   Using default safety settings (may cause blocks)")
        
        with trace_span("llm.generate_with_context", {
            "llm.model": self.model_name,
            "llm.provider": "gemini",
            "llm.has_tools": str(tools is not None),
            "llm.has_memory": str(retrieved_memory is not None)
        }):
            try:
                # Build chat history from messages
                history = []
                for i in range(0, len(messages) - 1, 2):
                    if i + 1 < len(messages):
                        user_msg = messages[i]
                        assistant_msg = messages[i + 1] if messages[i + 1].get("role") == "assistant" else None
                        if user_msg.get("role") == "user":
                            user_content = user_msg["parts"][0] if isinstance(user_msg["parts"], list) else str(user_msg["parts"])
                            if assistant_msg:
                                assistant_content = assistant_msg["parts"][0] if isinstance(assistant_msg["parts"], list) else str(assistant_msg["parts"])
                                history.append({"role": "user", "parts": [user_content]})
                                history.append({"role": "model", "parts": [assistant_content]})
                            else:
                                # If no assistant response, add empty one
                                history.append({"role": "user", "parts": [user_content]})
                                history.append({"role": "model", "parts": [""]})
                
                # Configure model with system instruction and tools
                model_config = {}
                if system_content:
                    model_config["system_instruction"] = system_content
                
                if gemini_tools:
                    model_config["tools"] = gemini_tools
                    logger.info(f"🔧 Configured {len(gemini_tools)} tools for Gemini model")
                
                try:
                    if model_config:
                        # Add safety_settings to model_config if available
                        if safety_settings:
                            model_config["safety_settings"] = safety_settings
                            if disable_safety_filters:
                                logger.info(f"🔓 Safety filters DISABLED (BLOCK_NONE) for this request")
                            else:
                                logger.debug(f"✅ Safety filters enabled (BLOCK_ONLY_HIGH) for this request")
                        model = genai.GenerativeModel(self.model_name, **model_config)
                        logger.info(f"✅ Created Gemini model with {len(gemini_tools) if gemini_tools else 0} tools, safety_settings={'configured' if safety_settings else 'default'}")
                    else:
                        model = self._get_model()
                        # If no model_config, we'll pass safety_settings to send_message
                    
                    # Start chat with history
                    chat = model.start_chat(history=history)
                except Exception as e:
                    logger.error(f"❌ Error creating Gemini model or starting chat: {e}", exc_info=True)
                    logger.error(f"   Model name: {self.model_name}")
                    logger.error(f"   Model config keys: {list(model_config.keys()) if model_config else 'None'}")
                    if gemini_tools:
                        logger.error(f"   Number of tools: {len(gemini_tools)}")
                        # Log first tool for debugging
                        if len(gemini_tools) > 0:
                            logger.error(f"   First tool: {gemini_tools[0]}")
                    raise
                
                # Send last message
                last_msg = messages[-1]["parts"][0] if isinstance(messages[-1]["parts"], list) else str(messages[-1]["parts"])
                
                # Pass generation_config and safety_settings to _generate_async
                # safety_settings should be passed to send_message if not already in model_config
                safety_settings_to_pass = None
                if safety_settings and not (model_config and "safety_settings" in model_config):
                    safety_settings_to_pass = safety_settings
                    if disable_safety_filters:
                        logger.info(f"🔓 Passing safety_settings (BLOCK_NONE) to send_message")
                    else:
                        logger.debug(f"✅ Passing safety_settings (BLOCK_ONLY_HIGH) to send_message")
                
                response = await self._generate_async(chat, last_msg, generation_config=generation_config, safety_settings=safety_settings_to_pass)
                
                duration = time.time() - start_time
                observe_histogram("llm_request_duration_seconds", duration, labels={"model": self.model_name, "provider": "gemini"})
                
                # Parse response
                content = ""
                tool_calls = []
                
                # First, check for function calls in Gemini response
                # IMPORTANT: Check function calls BEFORE checking finish_reason
                # Gemini might have generated function calls even if finish_reason=1 (safety block on text only)
                # If there are function calls, response.text will fail, so we need to check parts first
                has_function_calls = False
                finish_reason = None
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'finish_reason'):
                        finish_reason = candidate.finish_reason
                    if hasattr(candidate, 'content') and candidate.content:
                        parts = getattr(candidate.content, 'parts', None)
                        if parts is not None:
                            for part in parts:
                                if hasattr(part, 'function_call') and part.function_call:
                                    has_function_calls = True
                
                # Handle safety blocks ONLY if there are no function calls
                # If there are function calls, process them normally (safety block might be only on text response)
                if finish_reason == 1 and not has_function_calls:  # SAFETY and no function calls
                    logger.warning(f"Gemini response blocked by safety filters (finish_reason=1) in generate_with_tools, no function calls available")
                    # Return empty string instead of generic error message
                    # This allows the caller to extract results from tool execution
                    return {
                        "model": self.model_name,
                        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                        "message": {
                            "role": "assistant",
                            "content": ""  # Empty content to trigger fallback in caller
                        },
                        "tool_calls": [],
                        "done": True
                    }
                
                # Continue processing function calls if they exist (even if finish_reason=1)
                if has_function_calls:
                    if finish_reason == 1:
                        logger.info(f"Gemini generated function calls despite safety block (finish_reason=1), processing them")
                    
                    # Process function calls from parts
                    if hasattr(response, 'candidates') and response.candidates:
                        candidate = response.candidates[0]
                        if hasattr(candidate, 'content') and candidate.content:
                            parts = getattr(candidate.content, 'parts', None)
                            if parts is not None:
                                for part in parts:
                                    if hasattr(part, 'function_call') and part.function_call:
                                        func_call = part.function_call
                                        # Safely extract args - could be None, dict, or protobuf object
                                        args_dict = {}
                                        if hasattr(func_call, 'args') and func_call.args:
                                            try:
                                                # Try to convert to dict if it's a protobuf object
                                                if hasattr(func_call.args, '__dict__'):
                                                    args_dict = dict(func_call.args)
                                                elif isinstance(func_call.args, dict):
                                                    args_dict = func_call.args
                                                else:
                                                    # Try to iterate if it's a mapping
                                                    try:
                                                        args_dict = dict(func_call.args)
                                                    except (TypeError, ValueError):
                                                        # Fallback: try to get as dict-like object
                                                        args_dict = getattr(func_call.args, '__dict__', {})
                                            except Exception as e:
                                                logger.warning(f"Error extracting function call args: {e}")
                                                args_dict = {}
                                        
                                        tool_name_from_gemini = getattr(func_call, 'name', '')
                                        logger.info(f"🔧 Gemini called tool: '{tool_name_from_gemini}'")
                                        tool_calls.append({
                                            "name": tool_name_from_gemini,
                                            "parameters": args_dict
                                        })
                                    elif hasattr(part, 'text'):
                                        # Extract text from parts if available
                                        content = part.text
                
                # Handle safety blocks when tools=None (no function calls expected)
                if finish_reason == 1 and not has_function_calls:
                    logger.warning(f"Gemini response blocked by safety filters (finish_reason=1) in generate_with_context")
                    # Return empty string to allow caller to extract results from tools if available
                    if return_raw:
                        return {
                            "model": self.model_name,
                            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                            "message": {
                                "role": "assistant",
                                "content": ""  # Empty content to trigger fallback in caller
                            },
                            "tool_calls": [],
                            "done": True
                        }
                    else:
                        return ""  # Return empty string to trigger fallback
                
                # Only try to access response.text if there are no function calls
                # (function calls cause response.text to fail)
                if not has_function_calls and hasattr(response, 'text'):
                    try:
                        content = response.text
                    except Exception as e:
                        # If response.text fails (e.g., because of function calls), that's OK
                        # We've already extracted function calls above
                        logger.debug(f"Could not access response.text (likely function calls present): {e}")
                        if not content and not tool_calls:
                            # Only log warning if we have neither text nor function calls
                            logger.warning(f"Response has no text and no function calls: {e}")
                
                # Convert tool calls to Ollama format
                converted_tool_calls = []
                for tc in tool_calls:
                    converted_tool_calls.append({
                        "name": tc.get("name", ""),
                        "parameters": tc.get("parameters", {})
                    })
                
                if return_raw:
                    return {
                        "content": content,
                        "raw_result": {
                            "model": self.model_name,
                            "text": content,
                            "tool_calls": converted_tool_calls
                        },
                        "_parsed_tool_calls": converted_tool_calls,
                        "_raw_tool_calls": tool_calls
                    }
                else:
                    return content
                    
            except Exception as e:
                duration = time.time() - start_time
                observe_histogram("llm_request_duration_seconds", duration, labels={"model": self.model_name, "provider": "gemini", "error": "true"})
                increment_counter("llm_requests_errors_total", labels={"model": self.model_name, "provider": "gemini", "error_type": type(e).__name__})
                
                # Check for rate limit errors (429)
                error_str = str(e).lower()
                if "429" in error_str or "quota" in error_str or "rate limit" in error_str:
                    logger.warning(f"⚠️  Gemini API rate limit exceeded (429). Consider switching to Ollama or waiting for quota reset.")
                    logger.warning(f"   Error: {e}")
                    logger.warning(f"   Free tier limit: 10 requests/minute. Email analysis may exceed this limit.")
                    # Don't raise - let the caller handle it, but log clearly
                
                logger.error(f"Error calling Gemini API: {e}", exc_info=True)
                raise
    
    
    def _convert_parameters_to_gemini_schema(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Convert JSON Schema parameters to Gemini function calling schema"""
        # Gemini uses a simplified schema format
        # Convert from JSON Schema to Gemini format
        properties = params.get("properties", {})
        required = params.get("required", [])
        
        gemini_properties = {}
        gemini_required = []
        
        for prop_name, prop_schema in properties.items():
            prop_type = prop_schema.get("type", "string")
            prop_desc = prop_schema.get("description", "")
            
            # Map JSON Schema types to Gemini types
            gemini_type = "STRING"
            if prop_type == "integer" or prop_type == "number":
                gemini_type = "NUMBER"
            elif prop_type == "boolean":
                gemini_type = "BOOLEAN"
            elif prop_type == "array":
                gemini_type = "ARRAY"
            elif prop_type == "object":
                gemini_type = "OBJECT"
            
            gemini_prop = {
                "type": gemini_type,
                "description": prop_desc
            }
            
            # For arrays, preserve the items schema (required by Gemini)
            if prop_type == "array":
                if "items" in prop_schema:
                    items_schema = prop_schema["items"]
                    items_type = items_schema.get("type", "string")
                    
                    # Map items type to Gemini type
                    if items_type == "array":
                        # Nested array - preserve items recursively
                        # For nested arrays, we need to create an ARRAY type with its own items
                        nested_items_schema = {}
                        if "items" in items_schema:
                            nested_items_type = items_schema["items"].get("type", "string")
                            nested_gemini_type = "STRING"
                            if nested_items_type == "integer" or nested_items_type == "number":
                                nested_gemini_type = "NUMBER"
                            elif nested_items_type == "boolean":
                                nested_gemini_type = "BOOLEAN"
                            elif nested_items_type == "object":
                                nested_gemini_type = "OBJECT"
                            nested_items_schema = {"type": nested_gemini_type}
                        else:
                            # Nested array without items - default to STRING
                            nested_items_schema = {"type": "STRING"}
                        # Create ARRAY with nested items
                        gemini_prop["items"] = {
                            "type": "ARRAY",
                            "items": nested_items_schema
                        }
                    else:
                        # Simple array (not nested)
                        gemini_items_type = "STRING"
                        if items_type == "integer" or items_type == "number":
                            gemini_items_type = "NUMBER"
                        elif items_type == "boolean":
                            gemini_items_type = "BOOLEAN"
                        elif items_type == "object":
                            gemini_items_type = "OBJECT"
                        gemini_prop["items"] = {"type": gemini_items_type}
                else:
                    # Array without items specified - default to STRING array (required by Gemini)
                    gemini_prop["items"] = {"type": "STRING"}
            
            gemini_properties[prop_name] = gemini_prop
            
            if prop_name in required:
                gemini_required.append(prop_name)
        
        return {
            "type": "OBJECT",
            "properties": gemini_properties,
            "required": gemini_required
        }
    
    async def list_models(self) -> List[str]:
        """List available Gemini models"""
        try:
            # Gemini has a fixed set of models
            # Return common models
            return [
                "gemini-1.5-pro",
                "gemini-1.5-flash",
                "gemini-1.5-pro-latest",
                "gemini-1.5-flash-latest",
                "gemini-pro",
                "gemini-pro-vision"
            ]
        except Exception as e:
            logger.error(f"Error listing Gemini models: {e}", exc_info=True)
            return []
    
    async def close(self):
        """Close the client (no-op for Gemini as it's stateless)"""
        self.client = None

