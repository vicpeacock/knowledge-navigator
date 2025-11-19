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
                if stream:
                    # Streaming not fully implemented yet - return non-streaming for now
                    logger.warning("Streaming not fully supported for Gemini yet, using non-streaming")
                    response = await self._generate_async(chat, last_msg)
                else:
                    response = await self._generate_async(chat, last_msg)
                
                duration = time.time() - start_time
                observe_histogram("llm_request_duration_seconds", duration, labels={"model": self.model_name, "provider": "gemini", "stream": str(stream)})
                
                # Convert Gemini response to Ollama format
                response_text = response.text if hasattr(response, 'text') else str(response)
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
    
    async def _generate_async(self, chat, message: str):
        """Helper to generate response asynchronously"""
        import asyncio
        loop = asyncio.get_event_loop()
        # Use run_in_executor to avoid blocking
        def _send():
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
                
                # Convert parameters to Gemini schema format
                gemini_schema = self._convert_parameters_to_gemini_schema(tool_params)
                
                gemini_tools.append({
                    "function_declarations": [{
                        "name": tool_name,
                        "description": tool_desc,
                        "parameters": gemini_schema
                    }]
                })
            
            if gemini_tools:
                logger.info(f"Passing {len(gemini_tools)} tools to Gemini (filtered from {len(tools)} original tools)")
        
        # Set response format if specified
        generation_config = {}
        if format == "json":
            generation_config["response_mime_type"] = "application/json"
        
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
                
                if model_config:
                    model = genai.GenerativeModel(self.model_name, **model_config)
                else:
                    model = self._get_model()
                
                # Start chat with history
                chat = model.start_chat(history=history)
                
                # Send last message
                last_msg = messages[-1]["parts"][0] if isinstance(messages[-1]["parts"], list) else str(messages[-1]["parts"])
                
                # Configure generation with format if specified
                if generation_config:
                    # Create new model with generation config
                    if model_config:
                        model = genai.GenerativeModel(self.model_name, generation_config=generation_config, **{k: v for k, v in model_config.items() if k != "generation_config"})
                    else:
                        model = genai.GenerativeModel(self.model_name, generation_config=generation_config)
                    chat = model.start_chat(history=history)
                
                response = await self._generate_async(chat, last_msg)
                
                duration = time.time() - start_time
                observe_histogram("llm_request_duration_seconds", duration, labels={"model": self.model_name, "provider": "gemini"})
                
                # Parse response
                content = ""
                tool_calls = []
                
                if hasattr(response, 'text'):
                    content = response.text
                
                # Check for function calls in Gemini response
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content') and candidate.content:
                        parts = candidate.content.parts
                        for part in parts:
                            if hasattr(part, 'function_call'):
                                func_call = part.function_call
                                tool_calls.append({
                                    "name": func_call.name,
                                    "parameters": dict(func_call.args) if hasattr(func_call, 'args') else {}
                                })
                
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
            
            gemini_properties[prop_name] = {
                "type": gemini_type,
                "description": prop_desc
            }
            
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

