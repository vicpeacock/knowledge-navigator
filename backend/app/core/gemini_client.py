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
        self.alternative_model = settings.gemini_alternative_model  # Alternative model to try if main model fails
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
    
    async def _generate_async(self, chat, message: str, generation_config: Optional[Dict[str, Any]] = None, safety_settings: Optional[List[Any]] = None):
        """
        Helper to generate response asynchronously.
        
        Note: safety_settings should typically be set in model_config when creating GenerativeModel.
        They are only passed here if they were NOT set in model_config (rare case).
        """
        import asyncio
        import logging
        logger = logging.getLogger(__name__)
        loop = asyncio.get_event_loop()
        # Use run_in_executor to avoid blocking
        def _send():
            kwargs = {}
            if generation_config:
                kwargs["generation_config"] = generation_config
            if safety_settings:
                # Only pass safety_settings if they were not already set in model_config
                kwargs["safety_settings"] = safety_settings
                logger.info(f"🔍 _generate_async: Passing safety_settings to send_message (not in model_config)")
                # Log format verification - check if it's SafetySetting objects (preferred)
                if safety_settings and len(safety_settings) > 0:
                    first_setting = safety_settings[0]
                    # Check if it's a SafetySetting object (preferred format)
                    if 'google.generativeai.types.SafetySetting' in str(type(first_setting)) or hasattr(first_setting, 'category'):
                        logger.info(f"   🔍 _generate_async: Found SafetySetting objects (correct type) to pass to send_message")
                        if hasattr(first_setting, 'category'):
                            logger.info(f"   Category: {first_setting.category}, Threshold: {first_setting.threshold}")
                    elif isinstance(first_setting, dict):
                        category = first_setting.get("category")
                        threshold = first_setting.get("threshold")
                        logger.debug(f"   Safety settings format: dict (category={category}, threshold={threshold})")
                    else:
                        logger.debug(f"   Safety settings format: {type(first_setting)}")
            if kwargs:
                logger.debug(f"🔍 _generate_async: Calling send_message with {len(kwargs)} kwargs: {list(kwargs.keys())}")
                return chat.send_message(message, **kwargs)
            else:
                logger.debug(f"🔍 _generate_async: Calling send_message without kwargs (safety_settings should be in model)")
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
        # System prompt for Gemini - keep it minimal and neutral
        # Only mention tools if they are actually available
        if tools and len(tools) > 0:
            # Tools available - mention them
            base_system_prompt = """You are a helpful assistant that uses tools to provide accurate information.

Available tools:
- get_emails: Read emails
- get_calendar_events: Check calendar
- customsearch_search: Search the web

When the user asks a question, use the appropriate tool to find the answer. Respond with clear, factual information."""
        else:
            # No tools - use minimal prompt without mentioning tools
            base_system_prompt = """You are a helpful assistant. Respond clearly and factually to user questions."""
        
        enhanced_system = system_prompt or base_system_prompt
        
        # Add time/location context if provided
        time_context = getattr(self, '_time_context', None)
        if time_context:
            enhanced_system = time_context + "\n\n" + enhanced_system
        
        if retrieved_memory:
            # Format memory context - neutral, factual language (no imperatives)
            memory_context = "\n\n=== Context Information from Files and Memory ===\n"
            memory_context += "The following information has been retrieved from uploaded files and previous conversations.\n\n"
            
            for i, mem in enumerate(retrieved_memory, 1):
                max_chars = 5000
                if len(mem) > max_chars:
                    memory_context += f"{i}. {mem[:max_chars]}... [content truncated - file is {len(mem)} chars total]\n\n"
                else:
                    memory_context += f"{i}. {mem}\n\n"
            
            memory_context += "\n=== End of Context Information ===\n"
            # No imperative instructions - let the model use memory naturally
            enhanced_system += memory_context
        
        # Add tools description if provided
        if tools_description:
            enhanced_system += tools_description
        
        # Prepare messages for Gemini
        # Gemini supports system instructions via system_instruction parameter in GenerativeModel
        # We'll pass system_content as system_instruction, NOT in the message
        messages = []
        system_content = enhanced_system if enhanced_system else ""
        
        # Log system instruction for debugging
        if system_content:
            logger.info(f"🔍 System instruction configured (length: {len(system_content)} chars)")
            logger.debug(f"   System instruction preview: {system_content[:200]}...")
        
        # Add session context (without system prompt - it will be passed as system_instruction)
        # CRITICAL: Filter out error/fallback messages that trigger Gemini's safety filters
        # These messages contain patterns that Gemini interprets as attempts to bypass safety filters
        error_patterns = [
            "Ho ricevuto il tuo messaggio. Come posso aiutarti?",
            "non sono riuscito a generare una risposta",
            "filtri di sicurezza di Gemini",
            "safety filter block",
            "blocked by safety filters",
            "Mi dispiace, non sono riuscito",
            "Potresti riprovare?",
        ]
        
        for msg in session_context:
            role = msg.get("role", "user")
            # Skip system messages from context - they're handled by system_instruction
            if role != "system":
                # Extract content to check for error patterns
                content = ""
                if "parts" in msg and isinstance(msg["parts"], list):
                    # Extract text from parts (skip function_response parts)
                    for part in msg["parts"]:
                        if isinstance(part, str):
                            content = part
                            break
                        elif isinstance(part, dict) and "text" in part:
                            content = part["text"]
                            break
                else:
                    content = msg.get("content", "")
                
                # Skip messages that match error/fallback patterns
                content_lower = content.lower()
                is_error_message = any(pattern.lower() in content_lower for pattern in error_patterns)
                
                if is_error_message:
                    logger.debug(f"🔍 Filtering out error/fallback message from history: {content[:100]}...")
                    continue  # Skip this message
                
                # Check if message already has "parts" with function_response format
                if "parts" in msg and isinstance(msg["parts"], list):
                    # Preserve the parts as-is (may contain function_response)
                    messages.append({"role": role, "parts": msg["parts"]})
                else:
                    # Legacy format: convert content to parts
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
        # IMPORTANT: BLOCK_NONE requires allowlist approval from Google
        logger.info(f"🔍 Safety settings configuration: disable_safety_filters={disable_safety_filters}")
        safety_settings = None
        try:
            import google.generativeai as genai
            import google.generativeai.types as genai_types
            logger.info(f"🔍 Successfully imported genai and genai_types")
            
            # CRITICAL: Use SafetySetting objects instead of dicts for proper safety settings application
            # The google.generativeai SDK accepts both formats, but SafetySetting objects are preferred
            HarmCategory = genai_types.HarmCategory
            HarmBlockThreshold = genai_types.HarmBlockThreshold
            
            # Try to use SafetySetting class if available (preferred method)
            SafetySetting = None
            use_objects = False
            try:
                if hasattr(genai_types, 'SafetySetting'):
                    SafetySetting = genai_types.SafetySetting
                    use_objects = True
                    logger.info(f"✅ Using SafetySetting objects (preferred method)")
                else:
                    logger.warning(f"⚠️  SafetySetting class not found in genai_types, will try to import directly")
                    # Try importing directly from google.generativeai
                    from google.generativeai.types import SafetySetting as DirectSafetySetting
                    SafetySetting = DirectSafetySetting
                    use_objects = True
                    logger.info(f"✅ Using SafetySetting objects (imported directly)")
            except (ImportError, AttributeError) as e:
                logger.warning(f"⚠️  SafetySetting not available: {e}, will use dict format as fallback")
                use_objects = False
            
            if disable_safety_filters:
                logger.info(f"🔍 Configuring BLOCK_NONE safety settings for tool result synthesis...")
                logger.warning(f"   ⚠️  NOTE: BLOCK_NONE requires allowlist approval from Google. If not approved, this may not work.")
                # Use BLOCK_NONE for tool result synthesis (disable all safety filters)
                # This is safe because tool results come from trusted sources (our own tools)
                try:
                    if use_objects and SafetySetting:
                        safety_settings = [
                            SafetySetting(
                                category=HarmCategory.HARM_CATEGORY_HARASSMENT,
                                threshold=HarmBlockThreshold.BLOCK_NONE,
                            ),
                            SafetySetting(
                                category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                                threshold=HarmBlockThreshold.BLOCK_NONE,
                            ),
                            SafetySetting(
                                category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                                threshold=HarmBlockThreshold.BLOCK_NONE,
                            ),
                            SafetySetting(
                                category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                                threshold=HarmBlockThreshold.BLOCK_NONE,
                            ),
                        ]
                        logger.info(f"🔓 Safety settings configured: {len(safety_settings)} categories with BLOCK_NONE (using SafetySetting objects)")
                    else:
                        # Fallback to dict format if SafetySetting not available
                        safety_settings = [
                            {
                                "category": HarmCategory.HARM_CATEGORY_HARASSMENT,
                                "threshold": HarmBlockThreshold.BLOCK_NONE,
                            },
                            {
                                "category": HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                                "threshold": HarmBlockThreshold.BLOCK_NONE,
                            },
                            {
                                "category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                                "threshold": HarmBlockThreshold.BLOCK_NONE,
                            },
                            {
                                "category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                                "threshold": HarmBlockThreshold.BLOCK_NONE,
                            },
                        ]
                        logger.warning(f"⚠️  Using dict format for BLOCK_NONE (SafetySetting objects not available)")
                except Exception as e:
                    logger.error(f"   ❌ Failed to create safety settings: {e}", exc_info=True)
                    safety_settings = None
                    logger.warning(f"   Will use default safety settings (may cause blocks)")
            else:
                # Use BLOCK_ONLY_HIGH when tools are available (most permissive without allowlist)
                # BLOCK_ONLY_HIGH blocks only HIGH probability harmful content, allowing tool calls
                # When no tools, also use BLOCK_ONLY_HIGH for consistency
                threshold_to_use = HarmBlockThreshold.BLOCK_ONLY_HIGH
                threshold_name = "BLOCK_ONLY_HIGH"
                logger.info(f"🔍 Configuring {threshold_name} safety settings...")
                if gemini_tools:
                    logger.info(f"   Using BLOCK_ONLY_HIGH to allow tool calling (most permissive without allowlist)")
                try:
                    if use_objects and SafetySetting:
                        safety_settings = [
                            SafetySetting(
                                category=HarmCategory.HARM_CATEGORY_HARASSMENT,
                                threshold=threshold_to_use,
                            ),
                            SafetySetting(
                                category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                                threshold=threshold_to_use,
                            ),
                            SafetySetting(
                                category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                                threshold=threshold_to_use,
                            ),
                            SafetySetting(
                                category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                                threshold=threshold_to_use,
                            ),
                        ]
                        logger.info(f"✅ Configured Gemini safety settings to {threshold_name} (using SafetySetting objects)")
                    else:
                        # Fallback to dict format if SafetySetting not available
                        safety_settings = [
                            {
                                "category": HarmCategory.HARM_CATEGORY_HARASSMENT,
                                "threshold": threshold_to_use,
                            },
                            {
                                "category": HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                                "threshold": threshold_to_use,
                            },
                            {
                                "category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                                "threshold": threshold_to_use,
                            },
                            {
                                "category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                                "threshold": threshold_to_use,
                            },
                        ]
                        logger.warning(f"⚠️  Using dict format for {threshold_name} (SafetySetting objects not available)")
                except Exception as e:
                    logger.error(f"❌ Failed to create safety settings: {e}", exc_info=True)
                    safety_settings = None
                    logger.warning(f"   Will use default safety settings (may cause blocks)")
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
                # CRITICAL: Gemini requires perfect alternation: user -> model -> function -> user -> model
                # Support for function_response: function role can appear after model with function_call
                # The last message in history MUST be "model" or "function" before sending new user message
                history = []
                i = 0
                while i < len(messages) - 1:
                    msg = messages[i]
                    role = msg.get("role", "user")
                    parts = msg.get("parts", [])
                    
                    if role == "user":
                        # Extract user content
                        if isinstance(parts, list) and len(parts) > 0:
                            user_content = parts[0] if isinstance(parts[0], str) else str(parts[0])
                        else:
                            user_content = str(parts) if parts else ""
                        
                        history.append({"role": "user", "parts": [user_content]})
                        i += 1
                        
                        # Look for model response (may contain function_call)
                        if i < len(messages):
                            model_msg = messages[i]
                            if model_msg.get("role") in ["model", "assistant"]:
                                model_parts = model_msg.get("parts", [])
                                # Check if parts contain function_call
                                processed_parts = []
                                for part in model_parts:
                                    if isinstance(part, dict) and "function_call" in part:
                                        # Keep function_call as-is
                                        processed_parts.append(part)
                                    elif isinstance(part, str):
                                        processed_parts.append(part)
                                    else:
                                        processed_parts.append(str(part))
                                
                                if not processed_parts:
                                    processed_parts = [""]
                                
                                history.append({"role": "model", "parts": processed_parts})
                                i += 1
                                
                                # Look for function_response after model
                                while i < len(messages):
                                    func_msg = messages[i]
                                    if func_msg.get("role") == "function":
                                        func_parts = func_msg.get("parts", [])
                                        # Process function_response
                                        processed_func_parts = []
                                        for part in func_parts:
                                            if isinstance(part, dict) and "function_response" in part:
                                                # Keep function_response as-is
                                                processed_func_parts.append(part)
                                            elif isinstance(part, dict):
                                                # Try to convert to function_response format
                                                if "name" in part and "response" in part:
                                                    processed_func_parts.append({
                                                        "function_response": {
                                                            "name": part["name"],
                                                            "response": part["response"]
                                                        }
                                                    })
                                                else:
                                                    processed_func_parts.append(part)
                                            else:
                                                processed_func_parts.append(str(part))
                                        
                                        if processed_func_parts:
                                            history.append({"role": "function", "parts": processed_func_parts})
                                        i += 1
                                    else:
                                        break
                            else:
                                # No model response, add empty one to maintain alternation
                                history.append({"role": "model", "parts": [""]})
                    elif role == "function":
                        # Handle standalone function messages
                        func_parts = parts
                        processed_func_parts = []
                        for part in func_parts:
                            if isinstance(part, dict) and "function_response" in part:
                                processed_func_parts.append(part)
                            elif isinstance(part, dict) and "name" in part and "response" in part:
                                processed_func_parts.append({
                                    "function_response": {
                                        "name": part["name"],
                                        "response": part["response"]
                                    }
                                })
                            else:
                                processed_func_parts.append(str(part))
                        
                        if processed_func_parts:
                            history.append({"role": "function", "parts": processed_func_parts})
                        i += 1
                    else:
                        # Skip unknown roles or handle them
                        i += 1
                
                # CRITICAL: Verify history ends with "model" role
                if history and history[-1]["role"] != "model":
                    logger.warning(f"⚠️  History does not end with 'model' role! Last role: {history[-1]['role']}")
                    logger.warning(f"   Adding empty model message to fix alternation...")
                    history.append({"role": "model", "parts": [""]})
                
                logger.debug(f"📝 Built history with {len(history)} messages, last role: {history[-1]['role'] if history else 'empty'}")
                
                # Configure model with tools only (NOT system_instruction)
                # CRITICAL: Don't use system_instruction in model_config - put it in the message instead
                # This matches the working behavior of generate() method which puts system in [SYSTEM]: prefix
                model_config = {}
                
                if gemini_tools:
                    model_config["tools"] = gemini_tools
                    logger.info(f"🔧 Configured {len(gemini_tools)} tools for Gemini model")
                
                try:
                    if model_config:
                        model = genai.GenerativeModel(self.model_name, **model_config)
                        logger.info(f"✅ Created Gemini model with {len(gemini_tools) if gemini_tools else 0} tools")
                    else:
                        model = self._get_model()
                    
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
                
                # Send last message (system_content will be prepended above if present)
                last_msg = messages[-1]["parts"][0] if isinstance(messages[-1]["parts"], list) else str(messages[-1]["parts"])
                
                # DEBUG: Log the EXACT input being sent to Gemini (FULL CONTENT)
                logger.error("=" * 80)
                logger.error("🔍🔍🔍 EXACT INPUT TO GEMINI - FULL CONTENT 🔍🔍🔍")
                logger.error("=" * 80)
                logger.error(f"📋 Model: {self.model_name}")
                logger.error(f"")
                logger.error(f"📝 SYSTEM INSTRUCTION (length: {len(system_content) if system_content else 0} chars):")
                logger.error("-" * 80)
                if system_content:
                    logger.error(system_content)
                else:
                    logger.error("(empty)")
                logger.error("-" * 80)
                logger.error(f"")
                logger.error(f"💬 HISTORY (length: {len(history)} messages):")
                logger.error("-" * 80)
                if history:
                    for i, h in enumerate(history):
                        role = h.get('role', 'unknown')
                        parts = h.get('parts', [])
                        parts_str = str(parts) if parts else "(empty)"
                        logger.error(f"  [{i+1}] Role: {role}")
                        logger.error(f"      Parts: {parts_str[:500]}{'...' if len(parts_str) > 500 else ''}")
                else:
                    logger.error("  (empty)")
                logger.error("-" * 80)
                logger.error(f"")
                logger.error(f"📨 LAST MESSAGE (user input, length: {len(last_msg) if last_msg else 0} chars):")
                logger.error("-" * 80)
                if last_msg:
                    logger.error(last_msg)
                else:
                    logger.error("(empty)")
                logger.error("-" * 80)
                logger.error(f"")
                logger.error(f"🔧 TOOLS (count: {len(gemini_tools) if gemini_tools else 0}):")
                logger.error("-" * 80)
                if gemini_tools:
                    for i, tool in enumerate(gemini_tools):
                        func_decl = tool.get("function_declarations", [{}])[0] if tool.get("function_declarations") else {}
                        name = func_decl.get("name", "unknown")
                        desc = func_decl.get("description", "")
                        params = func_decl.get("parameters", {})
                        logger.error(f"  [{i+1}] {name}")
                        logger.error(f"      Description: {desc[:200]}{'...' if len(desc) > 200 else ''}")
                        logger.error(f"      Parameters: {str(params)[:300]}{'...' if len(str(params)) > 300 else ''}")
                else:
                    logger.error("  (no tools)")
                logger.error("-" * 80)
                logger.error(f"")
                logger.error(f"🛡️  SAFETY SETTINGS (count: {len(safety_settings) if safety_settings else 0} categories):")
                logger.error("-" * 80)
                if safety_settings:
                    for i, setting in enumerate(safety_settings):
                        if isinstance(setting, dict):
                            cat = setting.get('category', 'unknown')
                            thresh = setting.get('threshold', 'unknown')
                            logger.error(f"  [{i+1}] Category: {cat}, Threshold: {thresh}")
                        else:
                            cat = getattr(setting, 'category', 'unknown')
                            thresh = getattr(setting, 'threshold', 'unknown')
                            logger.error(f"  [{i+1}] Category: {cat}, Threshold: {thresh}")
                else:
                    logger.error("  (default safety settings)")
                logger.error("-" * 80)
                logger.error(f"")
                logger.error(f"⚙️  GENERATION CONFIG:")
                logger.error("-" * 80)
                logger.error(f"  {generation_config}")
                logger.error("-" * 80)
                logger.error("=" * 80)
                logger.error("🔍🔍🔍 END OF EXACT INPUT TO GEMINI 🔍🔍🔍")
                logger.error("=" * 80)
                
                # CRITICAL: If we have system_content, prepend it to the first user message (like generate() does)
                # NOTE: last_msg was already defined above (line 784), don't redefine it here
                # This is the key difference - generate() works because it doesn't use system_instruction in model_config
                if system_content:
                    logger.info(f"✅ Adding system_instruction to first message (length: {len(system_content)} chars) - like generate() method")
                    # Prepend system instruction to the first user message in history, or to last_msg if no history
                    if history and len(history) > 0 and history[0].get("role") == "user":
                        # Prepend to first user message in history
                        first_user_parts = history[0].get("parts", [])
                        if first_user_parts and isinstance(first_user_parts, list) and len(first_user_parts) > 0:
                            first_user_parts[0] = f"[SYSTEM]: {system_content}\n\n{first_user_parts[0]}"
                        else:
                            history[0]["parts"] = [f"[SYSTEM]: {system_content}"]
                    else:
                        # Prepend to last_msg (no history or history doesn't start with user)
                        last_msg = f"[SYSTEM]: {system_content}\n\n{last_msg}"
                        logger.info(f"   Prepended system instruction to last_msg")
                
                # CRITICAL: Always pass safety_settings to send_message(), NOT in model_config
                # This matches the working behavior of generate() method
                # Passing safety_settings in model_config seems to cause stricter filtering
                safety_settings_to_pass = safety_settings
                if safety_settings:
                    threshold_name = "BLOCK_NONE" if disable_safety_filters else "BLOCK_ONLY_HIGH"
                    logger.info(f"🔓 Passing safety_settings ({threshold_name}) to send_message() (not in model_config)")
                    # Log the safety_settings format
                    if safety_settings_to_pass and len(safety_settings_to_pass) > 0:
                        first_setting = safety_settings_to_pass[0]
                        if hasattr(first_setting, 'category'):
                            logger.info(f"   Safety settings format: SafetySetting objects (category={first_setting.category}, threshold={first_setting.threshold})")
                        elif isinstance(first_setting, dict):
                            logger.info(f"   Safety settings format: dict (category={first_setting.get('category')}, threshold={first_setting.get('threshold')})")
                else:
                    safety_settings_to_pass = None
                
                # Do not pass safety_settings if they're already in model_config
                logger.info(f"🔍 DEBUG: About to call _generate_async with:")
                logger.info(f"   Message length: {len(last_msg) if last_msg else 0}")
                logger.info(f"   Generation config: {generation_config}")
                logger.info(f"   Safety settings to pass: {safety_settings_to_pass is not None}")
                
                response = await self._generate_async(chat, last_msg, generation_config=generation_config, safety_settings=safety_settings_to_pass)
                
                # ==========================================================
                # 🚨 CRITICAL DEBUG BLOCK FOR SAFETY FILTERS (INPUT)
                # ==========================================================
                # According to Gemini 3, if safety_ratings in response are empty,
                # the problem is in the INPUT, and details are in prompt_feedback.safety_ratings
                if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                    pf = response.prompt_feedback
                    pf_safety_ratings = getattr(pf, 'safety_ratings', [])
                    
                    # 1. Log the main block reason
                    block_reason_name = 'BLOCK_REASON_UNSPECIFIED'
                    if hasattr(pf, 'block_reason'):
                        block_reason = pf.block_reason
                        if hasattr(block_reason, 'name'):
                            block_reason_name = block_reason.name
                        else:
                            block_reason_name = str(block_reason)
                    
                    if block_reason_name != 'BLOCK_REASON_UNSPECIFIED':
                        logger.error(f"🚨 INPUT BLOCKED! Block Reason: {block_reason_name}")
                    
                    # 2. Log safety ratings on INPUT (if present)
                    if pf_safety_ratings:
                        logger.error(f"🚨 Dettagli Safety Ratings su INPUT (causa del blocco): {len(pf_safety_ratings)} rating trovati.")
                        for i, rating in enumerate(pf_safety_ratings):
                            category_name = 'UNKNOWN'
                            probability_name = 'UNKNOWN'
                            
                            if hasattr(rating, 'category'):
                                category = rating.category
                                if hasattr(category, 'name'):
                                    category_name = category.name
                                else:
                                    category_name = str(category)
                            
                            if hasattr(rating, 'probability'):
                                probability = rating.probability
                                if hasattr(probability, 'name'):
                                    probability_name = probability.name
                                else:
                                    probability_name = str(probability)
                            
                            # Log only ratings that caused the block (excluding NEGLIGIBLE)
                            if probability_name not in ['NEGLIGIBLE', 'LOW']:
                                logger.error(f"   [{i}] Categoria: {category_name}, Probabilità: {probability_name} (⚠️ Soglia superata - CAUSA DEL BLOCCO)")
                            else:
                                logger.debug(f"   [{i}] Categoria: {category_name}, Probabilità: {probability_name} (Non bloccante)")
                    else:
                        # This is the case you're experiencing: prompt_feedback exists, but ratings are empty
                        if block_reason_name != 'BLOCK_REASON_UNSPECIFIED':
                            logger.error("⚠️ Blocco su INPUT confermato, ma safety_ratings vuoti. Problema a livello di policy/infrastruttura.")
                            logger.error("   Questo indica che il blocco avviene a livello infrastrutturale, non a livello di contenuto.")
                            logger.error("   Richiesta allowlist necessaria per BLOCK_NONE.")
                
                logger.info(f"🔍 DEBUG: Response received from Gemini:")
                logger.info(f"   Response type: {type(response)}")
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    logger.info(f"   Finish reason: {getattr(candidate, 'finish_reason', 'N/A')}")
                    
                    # Check for function calls FIRST before trying to access response.text
                    has_function_calls = False
                    if hasattr(candidate, 'content') and candidate.content:
                        parts = getattr(candidate.content, 'parts', None)
                        if parts is not None:
                            for part in parts:
                                if hasattr(part, 'function_call') and part.function_call:
                                    has_function_calls = True
                                    break
                    
                    logger.info(f"   Has function calls: {has_function_calls}")
                    
                    # Only try to access response.text if there are NO function calls
                    if not has_function_calls:
                        try:
                            # Use getattr with default to avoid accessing response.text property
                            # which raises ValueError if function calls are present
                            text_attr = getattr(response, 'text', None)
                            if text_attr is not None:
                                text_preview = str(text_attr)[:200] if text_attr else "Empty"
                                logger.info(f"   Text preview: {text_preview}")
                            else:
                                logger.info(f"   No text attribute available")
                        except (ValueError, AttributeError) as e:
                            logger.info(f"   Text access failed: {e}")
                    else:
                        logger.info(f"   Skipping text access (function calls present)")
                
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
                
                # ==========================================================
                # 🚨 DEBUG FOR OUTPUT (if output is blocked and input is OK)
                # ==========================================================
                output_safety_ratings = []
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'safety_ratings'):
                        output_safety_ratings = candidate.safety_ratings
                
                # Handle safety blocks ONLY if there are no function calls
                # If there are function calls, process them normally (safety block might be only on text response)
                if finish_reason == 1 and not has_function_calls:  # SAFETY and no function calls
                    logger.warning(f"🔴 Gemini response blocked by safety filters (finish_reason=1) in generate_with_context, no function calls available")
                    
                    # Log output safety ratings if present
                    if output_safety_ratings:
                        logger.error(f"🚨 OUTPUT BLOCKED! {len(output_safety_ratings)} safety ratings trovati sull'output.")
                        for i, rating in enumerate(output_safety_ratings):
                            category_name = 'UNKNOWN'
                            probability_name = 'UNKNOWN'
                            
                            if hasattr(rating, 'category'):
                                category = rating.category
                                if hasattr(category, 'name'):
                                    category_name = category.name
                                else:
                                    category_name = str(category)
                            
                            if hasattr(rating, 'probability'):
                                probability = rating.probability
                                if hasattr(probability, 'name'):
                                    probability_name = probability.name
                                else:
                                    probability_name = str(probability)
                            
                            logger.error(f"   [{i}] Categoria: {category_name}, Probabilità: {probability_name} (Causa del finish_reason=1)")
                    elif not output_safety_ratings:
                        # Check if we have prompt_feedback ratings
                        pf_ratings = []
                        if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                            pf_ratings = getattr(response.prompt_feedback, 'safety_ratings', [])
                        
                        if not pf_ratings:
                            # If both input and output ratings are empty, it's a deep problem
                            logger.error("❌ Blocco SAFETY (finish_reason=1) senza dettagli di rating. Richiesta allowlist necessaria.")
                            logger.error("   Questo indica un blocco a livello infrastrutturale/policy, non a livello di contenuto.")
                    
                    # Try alternative model if available and current model is flash
                    if self.alternative_model and self.model_name == settings.gemini_model and "flash" in self.model_name.lower():
                        logger.info(f"🔄 Trying alternative model: {self.alternative_model}")
                        original_model = self.model_name
                        self.model_name = self.alternative_model
                        try:
                            # Retry with alternative model
                            response = await self._generate_async(chat, last_msg, generation_config=generation_config, safety_settings=safety_settings_to_pass)
                            # Check if alternative model worked
                            if hasattr(response, 'candidates') and response.candidates:
                                candidate = response.candidates[0]
                                alt_finish_reason = getattr(candidate, 'finish_reason', None)
                                if alt_finish_reason != 1:  # Not blocked
                                    logger.info(f"✅ Alternative model {self.alternative_model} succeeded!")
                                    # Continue with alternative model response
                                else:
                                    logger.warning(f"⚠️  Alternative model {self.alternative_model} also blocked")
                                    self.model_name = original_model  # Revert
                            else:
                                self.model_name = original_model  # Revert
                        except Exception as e:
                            logger.error(f"❌ Error with alternative model: {e}")
                            self.model_name = original_model  # Revert
                            # Continue with original error handling below
                    
                    # DEBUG: Inspect prompt_feedback (if block is on input)
                    # CRITICAL: According to Gemini, if safety_ratings in response are empty,
                    # the problem is in the INPUT, and details are in prompt_feedback.safety_ratings
                    if hasattr(response, 'prompt_feedback'):
                        prompt_feedback = response.prompt_feedback
                        logger.error(f"🔍 PROMPT_FEEDBACK (input block) - THIS IS WHERE THE PROBLEM IS:")
                        logger.error(f"   Type: {type(prompt_feedback)}")
                        logger.error(f"   All attributes: {[x for x in dir(prompt_feedback) if not x.startswith('_')]}")
                        
                        if prompt_feedback:
                            if hasattr(prompt_feedback, 'block_reason'):
                                block_reason = prompt_feedback.block_reason
                                logger.error(f"   Block reason: {block_reason} (type: {type(block_reason)})")
                                try:
                                    if hasattr(block_reason, 'name'):
                                        logger.error(f"   Block reason name: {block_reason.name}")
                                    if hasattr(block_reason, 'value'):
                                        logger.error(f"   Block reason value: {block_reason.value}")
                                except:
                                    pass
                            
                            # CRITICAL: Check prompt_feedback.safety_ratings
                            if hasattr(prompt_feedback, 'safety_ratings'):
                                safety_ratings = prompt_feedback.safety_ratings
                                logger.error(f"   🔑 PROMPT_FEEDBACK.safety_ratings (type: {type(safety_ratings)}, length: {len(safety_ratings) if safety_ratings else 0}):")
                                if safety_ratings and len(safety_ratings) > 0:
                                    logger.error(f"     ✅ FOUND {len(safety_ratings)} safety ratings in prompt_feedback!")
                                    for i, rating in enumerate(safety_ratings):
                                        logger.error(f"     Rating {i}: {type(rating)}")
                                        logger.error(f"       Full repr: {repr(rating)}")
                                        try:
                                            category = None
                                            if hasattr(rating, 'category'):
                                                category = rating.category
                                                if hasattr(category, 'name'):
                                                    category = category.name
                                                elif hasattr(category, 'value'):
                                                    category = category.value
                                            
                                            probability = None
                                            if hasattr(rating, 'probability'):
                                                probability = rating.probability
                                                if hasattr(probability, 'name'):
                                                    probability = probability.name
                                                elif hasattr(probability, 'value'):
                                                    probability = probability.value
                                            
                                            blocked = getattr(rating, 'blocked', False)
                                            logger.error(f"       ✅ Category: {category}, Probability: {probability}, Blocked: {blocked}")
                                        except Exception as e:
                                            logger.error(f"       ❌ Error: {e}")
                                            logger.error(f"       Rating dir: {[x for x in dir(rating) if not x.startswith('_')]}")
                                else:
                                    logger.error(f"     ⚠️  No safety ratings in prompt_feedback (empty or None)")
                                    logger.error(f"     This suggests the block is at infrastructure level, not content level")
                            else:
                                logger.error(f"   ⚠️  No safety_ratings attribute in prompt_feedback")
                        else:
                            logger.error(f"   ⚠️  prompt_feedback is None or empty")
                    
                    # DEBUG: Inspect safety_ratings on output (if block is on output)
                    if hasattr(response, 'candidates') and response.candidates:
                        candidate = response.candidates[0]
                        if hasattr(candidate, 'safety_ratings'):
                            safety_ratings = candidate.safety_ratings
                            logger.error(f"🔍 SAFETY_RATINGS on OUTPUT (type: {type(safety_ratings)}, length: {len(safety_ratings) if safety_ratings else 0}):")
                            if safety_ratings and len(safety_ratings) > 0:
                                for i, rating in enumerate(safety_ratings):
                                    logger.error(f"     Rating {i}: {type(rating)}")
                                    logger.error(f"       Repr: {repr(rating)[:300]}")
                                    try:
                                        category = getattr(rating, 'category', None)
                                        if category is None:
                                            category = str(rating.category) if hasattr(rating, 'category') else 'UNKNOWN'
                                        probability = getattr(rating, 'probability', None)
                                        if probability is None:
                                            probability = str(rating.probability) if hasattr(rating, 'probability') else 'UNKNOWN'
                                        blocked = getattr(rating, 'blocked', False)
                                        logger.error(f"       Category: {category}, Probability: {probability}, Blocked: {blocked}")
                                    except Exception as e:
                                        logger.error(f"       Error: {e}")
                            else:
                                logger.error(f"     (No safety ratings - empty or None)")
                    
                    # IMPORTANT: If tools were available but Gemini was blocked before calling them,
                    # this might be a false positive. Log this case for debugging.
                    if gemini_tools and len(gemini_tools) > 0:
                        logger.warning(f"⚠️  Gemini was blocked BEFORE calling tools even though {len(gemini_tools)} tools were available!")
                        logger.warning(f"   This suggests the prompt or context triggered safety filters before tool selection.")
                        tool_names = [t.get('function_declarations', [{}])[0].get('name', 'unknown') for t in gemini_tools[:10]]
                        logger.warning(f"   Available tools: {tool_names}")
                        # Log the prompt that triggered the block (first 200 chars)
                        logger.warning(f"   Prompt preview: {last_msg[:200] if 'last_msg' in locals() else 'N/A'}")
                        logger.warning(f"   System instruction length: {len(system_content) if system_content else 0}")
                    
                    # Raise ValueError when Gemini blocks - let the caller handle it properly
                    # This is better than returning empty content which triggers hardcoded fallbacks
                    prompt_feedback_summary = "No details"
                    if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                        pf = response.prompt_feedback
                        block_reason = getattr(pf, 'block_reason', None)
                        if block_reason:
                            block_reason_name = getattr(block_reason, 'name', str(block_reason))
                            prompt_feedback_summary = f"Block reason: {block_reason_name}"
                    
                    output_safety_ratings_summary = "No ratings"
                    if output_safety_ratings:
                        categories = []
                        for rating in output_safety_ratings:
                            cat = getattr(rating, 'category', None)
                            prob = getattr(rating, 'probability', None)
                            if cat and prob:
                                cat_name = getattr(cat, 'name', str(cat))
                                prob_name = getattr(prob, 'name', str(prob))
                                categories.append(f"{cat_name}={prob_name}")
                        if categories:
                            output_safety_ratings_summary = ", ".join(categories)
                    
                    raise ValueError(
                        f"Gemini response blocked by safety filters (finish_reason=1). "
                        f"Prompt feedback: {prompt_feedback_summary}. "
                        f"Output safety ratings: {output_safety_ratings_summary}"
                    )
                
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
                    logger.warning(f"🔴 Gemini response blocked by safety filters (finish_reason=1) in generate_with_context")
                    
                    # DEBUG: Inspect prompt_feedback (if block is on input)
                    # CRITICAL: According to Gemini, if safety_ratings in response are empty,
                    # the problem is in the INPUT, and details are in prompt_feedback.safety_ratings
                    if hasattr(response, 'prompt_feedback'):
                        prompt_feedback = response.prompt_feedback
                        logger.error(f"🔍 PROMPT_FEEDBACK (input block) - THIS IS WHERE THE PROBLEM IS:")
                        logger.error(f"   Type: {type(prompt_feedback)}")
                        logger.error(f"   All attributes: {[x for x in dir(prompt_feedback) if not x.startswith('_')]}")
                        
                        if prompt_feedback:
                            if hasattr(prompt_feedback, 'block_reason'):
                                block_reason = prompt_feedback.block_reason
                                logger.error(f"   Block reason: {block_reason} (type: {type(block_reason)})")
                                try:
                                    if hasattr(block_reason, 'name'):
                                        logger.error(f"   Block reason name: {block_reason.name}")
                                    if hasattr(block_reason, 'value'):
                                        logger.error(f"   Block reason value: {block_reason.value}")
                                except:
                                    pass
                            
                            # CRITICAL: Check prompt_feedback.safety_ratings
                            if hasattr(prompt_feedback, 'safety_ratings'):
                                safety_ratings = prompt_feedback.safety_ratings
                                logger.error(f"   🔑 PROMPT_FEEDBACK.safety_ratings (type: {type(safety_ratings)}, length: {len(safety_ratings) if safety_ratings else 0}):")
                                if safety_ratings and len(safety_ratings) > 0:
                                    logger.error(f"     ✅ FOUND {len(safety_ratings)} safety ratings in prompt_feedback!")
                                    for i, rating in enumerate(safety_ratings):
                                        logger.error(f"     Rating {i}: {type(rating)}")
                                        logger.error(f"       Full repr: {repr(rating)}")
                                        try:
                                            category = None
                                            if hasattr(rating, 'category'):
                                                category = rating.category
                                                if hasattr(category, 'name'):
                                                    category = category.name
                                                elif hasattr(category, 'value'):
                                                    category = category.value
                                            
                                            probability = None
                                            if hasattr(rating, 'probability'):
                                                probability = rating.probability
                                                if hasattr(probability, 'name'):
                                                    probability = probability.name
                                                elif hasattr(probability, 'value'):
                                                    probability = probability.value
                                            
                                            blocked = getattr(rating, 'blocked', False)
                                            logger.error(f"       ✅ Category: {category}, Probability: {probability}, Blocked: {blocked}")
                                        except Exception as e:
                                            logger.error(f"       ❌ Error: {e}")
                                            logger.error(f"       Rating dir: {[x for x in dir(rating) if not x.startswith('_')]}")
                                else:
                                    logger.error(f"     ⚠️  No safety ratings in prompt_feedback (empty or None)")
                                    logger.error(f"     This suggests the block is at infrastructure level, not content level")
                            else:
                                logger.error(f"   ⚠️  No safety_ratings attribute in prompt_feedback")
                        else:
                            logger.error(f"   ⚠️  prompt_feedback is None or empty")
                    
                    # DEBUG: Inspect safety_ratings on output (if block is on output)
                    if hasattr(response, 'candidates') and response.candidates:
                        candidate = response.candidates[0]
                        if hasattr(candidate, 'safety_ratings'):
                            safety_ratings = candidate.safety_ratings
                            logger.error(f"🔍 SAFETY_RATINGS on OUTPUT (type: {type(safety_ratings)}, length: {len(safety_ratings) if safety_ratings else 0}):")
                            if safety_ratings and len(safety_ratings) > 0:
                                for i, rating in enumerate(safety_ratings):
                                    logger.error(f"     Rating {i}: {type(rating)}")
                                    logger.error(f"       Repr: {repr(rating)[:300]}")
                                    try:
                                        category = getattr(rating, 'category', None)
                                        if category is None:
                                            category = str(rating.category) if hasattr(rating, 'category') else 'UNKNOWN'
                                        probability = getattr(rating, 'probability', None)
                                        if probability is None:
                                            probability = str(rating.probability) if hasattr(rating, 'probability') else 'UNKNOWN'
                                        blocked = getattr(rating, 'blocked', False)
                                        logger.error(f"       Category: {category}, Probability: {probability}, Blocked: {blocked}")
                                    except Exception as e:
                                        logger.error(f"       Error: {e}")
                            else:
                                logger.error(f"     (No safety ratings - empty or None)")
                    
                    # When Gemini blocks, raise an exception so the caller can handle it properly
                    # This is better than returning empty content, which might be silently ignored
                    raise ValueError(
                        f"Gemini response blocked by safety filters (finish_reason=1). "
                        f"Model: {self.model_name}. "
                        f"Try rephrasing your request or using a different model."
                    )
                
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

