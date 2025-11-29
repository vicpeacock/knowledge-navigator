"""
Vertex AI Client - Alternative to Gemini REST API

This client uses Google Vertex AI instead of the direct Gemini REST API.
Vertex AI may have different safety policies and could resolve blocking issues.
"""
import logging
from typing import List, Dict, Optional, Any
from app.core.config import settings
import json
import time

logger = logging.getLogger(__name__)

try:
    from google import genai
    from google.genai.types import HttpOptions, SafetySetting, HarmCategory, HarmBlockThreshold, Tool, FunctionDeclaration
    from google.auth import default
    import google.auth.transport.requests
    VERTEX_AI_AVAILABLE = True
except ImportError as e:
    VERTEX_AI_AVAILABLE = False
    logger.warning(f"Vertex AI SDK not installed: {e}. Install with: pip install google-genai")

class VertexAIClient:
    """
    Vertex AI client compatible with GeminiClient interface.
    
    Uses Google Vertex AI instead of direct Gemini REST API.
    This may resolve safety filter blocking issues.
    """
    
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize Vertex AI client.
        
        Args:
            base_url: Ignored for Vertex AI (uses Google Cloud auth)
            model: Gemini model name (default: settings.gemini_model)
        """
        if not VERTEX_AI_AVAILABLE:
            raise ImportError(
                "google-genai is not installed. "
                "Install with: pip install google-genai"
            )
        
        if not settings.google_cloud_project_id:
            raise ValueError(
                "GOOGLE_CLOUD_PROJECT_ID is required for Vertex AI but not set. "
                "Set it in your .env file or environment variables."
            )
        
        self.model_name = model or settings.gemini_model
        self.project_id = settings.google_cloud_project_id
        self.location = settings.google_cloud_location or "us-central1"
        self.client = None
        self.credentials = None
        
        # Initialize authentication
        try:
            # Priority 1: Use GOOGLE_APPLICATION_CREDENTIALS if set (Service Account JSON file)
            import os
            if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                from google.oauth2 import service_account
                credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                self.credentials = service_account.Credentials.from_service_account_file(
                    credentials_path,
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
                logger.info(f"✅ Vertex AI authentication using Service Account JSON file: {credentials_path}")
            else:
                # Use Application Default Credentials
                self.credentials, _ = default()
                logger.info("✅ Vertex AI authentication using Application Default Credentials")
        except Exception as e:
            logger.error(f"❌ Vertex AI authentication failed: {e}")
            logger.error("💡 Tip: Configure Application Default Credentials with: gcloud auth application-default login")
            raise ValueError(f"Failed to authenticate with Google Cloud: {e}")
        
        # Initialize client
        self._init_client()

    def _init_client(self):
        try:
            # Vertex AI requires vertexai=True, project, and location parameters
            self.client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=self.location,
                credentials=self.credentials,
                http_options=HttpOptions(api_version="v1"),
            )
            logger.info(f"✅ Vertex AI client initialized (model: {self.model_name}, project: {self.project_id}, location: {self.location})")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Vertex AI client: {e}")
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
        """Close the client (no-op for Gemini as it is stateless)"""
        self.client = None

    def _create_safety_settings(self, block_none: bool = False) -> List[SafetySetting]:
        """
        Create safety settings for Vertex AI.
        
            block_none: If True, set all categories to BLOCK_NONE
            
        Returns:
            List of SafetySetting objects
        """
        threshold = HarmBlockThreshold.BLOCK_NONE if block_none else HarmBlockThreshold.BLOCK_ONLY_HIGH
        
        return [
            SafetySetting(
                category=HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=threshold,
            ),
            SafetySetting(
                category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=threshold,
            ),
            SafetySetting(
                category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=threshold,
            ),
            SafetySetting(
                category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=threshold,
            ),
        ]
    
    async def generate(
        self,
        prompt: str,
        context: Optional[List[Dict[str, str]]] = None,
        system: Optional[str] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """Generate a response from Vertex AI (compatible with GeminiClient.generate)
        """
        from app.core.tracing import trace_span, set_trace_attribute, add_trace_event
        from app.core.metrics import increment_counter, observe_histogram
        
        start_time = time.time()
        
        # Build contents for Vertex AI
        # Vertex AI expects simple string or list of strings, not dict with role/parts
        if context:
            # Build conversation history as list of strings
            contents = []
            for msg in context:
                content = msg.get("content", "")
                if content:  # Skip empty messages
                    contents.append(content)
            # Add current prompt
            contents.append(prompt)
        else:
            # Simple prompt without context
            contents = prompt
        
        # Create safety settings
        safety_settings = self._create_safety_settings(block_none=False)
        
        # Prepare config
        config = {}
        if system:
            config["system_instruction"] = system
        config["safety_settings"] = safety_settings
        
        vertex_tools_list = None

        try:
            with trace_span("vertex_ai.generate"):
                set_trace_attribute("vertex_ai.model", self.model_name)
                set_trace_attribute("vertex_ai.project", self.project_id)
                
                # Generate content
                # Tools must be in config according to Vertex AI SDK
                # Tools must be in config, not as direct parameter
                if vertex_tools_list:
                    config["tools"] = vertex_tools_list
                    logger.info(f"🔧 Adding {len(vertex_tools_list)} Tool objects to config")
                
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=config,
                )
                
                response_text = response.text if hasattr(response, 'text') and response.text else None
                
                if response_text is None:
                    # Try to extract text from response object
                    if hasattr(response, 'candidates') and response.candidates:
                        candidate = response.candidates[0]
                        if hasattr(candidate, 'content') and candidate.content:
                            if hasattr(candidate.content, 'parts'):
                                parts = candidate.content.parts
                                if parts:
                                    response_text = parts[0].text if hasattr(parts[0], 'text') else str(parts[0])
                    
                    if response_text is None:
                        response_text = str(response) if response else ""
                
                # Return in Ollama-compatible format
                return {
                    "model": self.model_name,
                    "response": response_text,
                    "done": True,
                    "context": context + [{"role": "user", "content": prompt}] if context else [{"role": "user", "content": prompt}],
                }
        
        except Exception as e:
            logger.error(f"❌ Vertex AI generate error: {e}", exc_info=True)
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
        disable_safety_filters: bool = False,
    ) -> str:
        """Generate response with full context (compatible with GeminiClient.generate_with_context)
        """
        from app.core.tracing import trace_span, set_trace_attribute
        
        start_time = time.time()
        
        with trace_span("vertex_ai.generate_with_context"):
            set_trace_attribute("vertex_ai.model", self.model_name)
            set_trace_attribute("vertex_ai.has_tools", bool(tools))
            
            # Build contents from session context
            from google.genai import types
            # Vertex AI SDK expects Content objects from google.genai.types
            from google.genai import types
            
            contents = []
            system_messages = []  # Collect system messages separately
            
            for msg in session_context:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                parts = msg.get("parts", [])
                
                # CRITICAL: Vertex AI does NOT allow system role in contents array
                # System messages must be in system_instruction only
                if role == "system":
                    # Collect system messages to add to system_instruction instead
                    if content:
                        system_messages.append(content)
                    elif parts:
                        for part in parts:
                            if isinstance(part, str):
                                system_messages.append(part)
                            elif isinstance(part, dict) and "text" in part:
                                system_messages.append(part["text"])
                    continue  # Skip adding to contents array
                
                # Handle function_response format (from langgraph_app synthesis_context)
                if role == "function" and parts:
                    # Vertex AI expects function_response in Content format
                    for part in parts:
                        if isinstance(part, dict) and "function_response" in part:
                            func_resp = part["function_response"]
                            func_name = func_resp.get("name", "")
                            func_response = func_resp.get("response", {})
                            # Create Content object with function_response
                            contents.append(types.Content(
                                role="function",
                                parts=[types.Part(function_response=types.FunctionResponse(
                                    name=func_name,
                                    response=func_response
                                ))]
                            ))
                        elif isinstance(part, str):
                            contents.append(types.Content(role="function", parts=[types.Part(text=part)]))
                elif role == "model" and parts:
                    # Handle model messages with function_call
                    model_parts = []
                    for part in parts:
                        if isinstance(part, dict) and "function_call" in part:
                            func_call = part["function_call"]
                            model_parts.append(types.Part(function_call=types.FunctionCall(
                                name=func_call.get("name", ""),
                                args=func_call.get("args", {})
                            )))
                        elif isinstance(part, str):
                            model_parts.append(types.Part(text=part))
                    if model_parts:
                        contents.append(types.Content(role="model", parts=model_parts))
                elif content:  # Regular user message
                    contents.append(types.Content(role=role, parts=[types.Part(text=content)]))
            
            # Add collected system messages to system_instruction instead of contents
            if system_messages:
                logger.info(f"📋 Found {len(system_messages)} system messages in session_context, adding to system_instruction instead of contents")
                system_content = "\n\n".join(system_messages)
                if system_prompt:
                    system_prompt = system_prompt + "\n\n" + system_content
                else:
                    system_prompt = system_content
            
            # Add current prompt
            contents.append(types.Content(role="user", parts=[types.Part(text=prompt)]))
            
            # Prepare config
            config = {}
            
            if system_prompt:
                config["system_instruction"] = system_prompt
            
            # Add tool usage instructions if tools are available
            # Use actual tool descriptions from MCP instead of hardcoded generic instructions
            if tools and len(tools) > 0:
                tool_names = [tool.get("name", "unknown") for tool in tools if isinstance(tool, dict)]
                if tool_names:
                    # Build instructions from actual tool descriptions
                    tool_descriptions = []
                    for tool in tools:
                        if isinstance(tool, dict):
                            tool_name = tool.get("name", "unknown")
                            tool_description = tool.get("description", "")
                            if tool_description:
                                # Use the actual description from MCP server
                                tool_descriptions.append(f"- {tool_name}: {tool_description}")
                            else:
                                # Fallback if no description available
                                tool_descriptions.append(f"- {tool_name}")
                    
                    # Build instruction text
                    if tool_descriptions:
                        # Show first 15 tools with descriptions, then summarize if more
                        shown_tools = tool_descriptions[:15]
                        remaining_count = len(tool_descriptions) - len(shown_tools)
                        
                        tool_instruction = f"""
IMPORTANTE - Uso dei Tool:
Hai accesso ai seguenti tool ({len(tool_names)} totali):

{chr(10).join(shown_tools)}
"""
                        if remaining_count > 0:
                            tool_instruction += f"\n... e altri {remaining_count} tool disponibili.\n"
                        
                        tool_instruction += """
IMPORTANTE: Quando l'utente chiede informazioni o azioni, usa SEMPRE i tool appropriati basandoti sulle loro descrizioni sopra.
NON rispondere con informazioni generiche o ipotetiche. Usa SEMPRE i tool per ottenere informazioni reali e aggiornate.
Ogni tool ha una descrizione specifica che indica quando e come usarlo - segui quelle descrizioni.
"""
                    else:
                        # Fallback if no descriptions available
                        tool_instruction = f"""
IMPORTANTE - Uso dei Tool:
Hai accesso ai seguenti tool: {', '.join(tool_names[:10])}{'...' if len(tool_names) > 10 else ''}

Quando l'utente chiede informazioni o azioni che richiedono questi tool, DEVI chiamarli.
NON rispondere con informazioni generiche o ipotetiche. Usa SEMPRE i tool appropriati per ottenere informazioni reali e aggiornate.
"""
                    
                    current_system = config.get("system_instruction", "")
                    if current_system:
                        config["system_instruction"] = current_system + tool_instruction
                    else:
                        config["system_instruction"] = tool_instruction
                    
                    # Also use tools_description if provided (may contain additional context)
                    if tools_description:
                        current_system = config.get("system_instruction", "")
                        if current_system:
                            config["system_instruction"] = current_system + "\n\n" + tools_description
                        else:
                            config["system_instruction"] = tools_description

            
            # Add retrieved memory (files, previous conversations) to system instruction
            if retrieved_memory:
                # Check if any memory contains file content
                has_file_content = any("[Content from uploaded file" in mem or "uploaded file" in mem.lower() for mem in retrieved_memory)
                
                # Format memory context clearly, similar to OllamaClient
                memory_context = "\n\n=== IMPORTANT: Context Information from Files and Memory ===\n"
                memory_context += "The following information has been retrieved from uploaded files and previous conversations.\n"
                memory_context += "You MUST use this information to answer questions accurately.\n\n"
                
                for i, mem in enumerate(retrieved_memory, 1):
                    # Truncate very long content to avoid token limits
                    # For file content, show enough to understand but not overwhelm the model
                    max_chars = 5000  # Same as OllamaClient
                    if len(mem) > max_chars:
                        memory_context += f"{i}. {mem[:max_chars]}... [content truncated - file is {len(mem)} chars total]\n\n"
                    else:
                        memory_context += f"{i}. {mem}\n\n"
                
                memory_context += "\n=== End of Context Information ===\n"
                
                # Add explicit instructions if file content is present
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
                
                # Combine memory_context with existing system_instruction
                current_system = config.get("system_instruction", "")
                if current_system:
                    config["system_instruction"] = current_system + memory_context
                else:
                    config["system_instruction"] = memory_context
            
            # Add time/location context if provided (like GeminiClient)
            time_context = getattr(self, '_time_context', None)
            if time_context:
                # Combine time_context with system_instruction
                current_system = config.get("system_instruction", "")
                if current_system:
                    config["system_instruction"] = time_context + "\n\n" + current_system
                else:
                    config["system_instruction"] = time_context
            
            safety_settings = self._create_safety_settings(block_none=disable_safety_filters)
            config["safety_settings"] = safety_settings
            
            vertex_tools_list = None  # Initialize before processing tools
            if tools:
                logger.info(f"🔧 Processing {len(tools)} tools for Vertex AI")
                vertex_tools = []
                for tool in tools:
                    tool_name = tool.get("name", "unknown")
                    if "function_declarations" in tool:
                        logger.info(f"   Tool {tool_name}: Already in function_declarations format")
                        vertex_tools.extend(tool["function_declarations"])
                    elif "name" in tool and "parameters" in tool:
                        logger.info(f"   Tool {tool_name}: Converting to function_declarations format")
                        try:
                            # Convert parameters to Vertex AI schema format (same as Gemini)
                            vertex_schema = self._convert_parameters_to_gemini_schema(tool["parameters"])
                            vertex_tools.append({
                                "name": tool["name"],
                                "description": tool.get("description", ""),
                                "parameters": vertex_schema,
                            })
                        except Exception as e:
                            logger.error(f"   ❌ Error converting tool {tool_name} parameters: {e}", exc_info=True)
                            logger.error(f"   Tool params: {tool.get('parameters', {})}")
                            # Fallback to original parameters
                            vertex_tools.append({
                                "name": tool["name"],
                                "description": tool.get("description", ""),
                                "parameters": tool["parameters"],
                            })
                    else:
                        logger.warning(f"   Tool {tool_name}: Unknown format, skipping")
                        logger.warning(f"   Tool keys: {list(tool.keys())}")
                
                # Convert to Vertex AI Tool objects (according to official docs)
                if vertex_tools:
                    # Vertex AI requires Tool objects with FunctionDeclaration objects
                    function_declarations = []
                    for tool_dict in vertex_tools:
                        tool_name = tool_dict.get("name", "unknown")
                        try:
                            # FunctionDeclaration accepts dict for parameters and converts to Schema automatically
                            func_decl = FunctionDeclaration(
                                name=tool_name,
                                description=tool_dict.get("description", ""),
                                parameters=tool_dict.get("parameters", {})
                            )
                            function_declarations.append(func_decl)
                            logger.debug(f"   ✅ Created FunctionDeclaration for {tool_name}")
                        except Exception as e:
                            logger.error(f"   ❌ Error creating FunctionDeclaration for {tool_name}: {e}", exc_info=True)
                            logger.error(f"   Tool dict: {tool_dict}")
                            # Skip this tool instead of adding dict (dict format won't work)
                            continue
                    
                    if function_declarations:
                        # Create Tool object with function_declarations (official format)
                        # According to docs, tools should be passed as parameter, not in config
                        vertex_tools_list = [Tool(function_declarations=function_declarations)]
                        logger.info(f"✅ Configured {len(function_declarations)} tools for Vertex AI: {[fd.name if hasattr(fd, 'name') else fd.get('name', 'unknown') for fd in function_declarations]}")
                else:
                    logger.warning("⚠️  No valid tools found after conversion")
            
            try:
                # Tools must be in config, not as direct parameter
                if vertex_tools_list:
                    config["tools"] = vertex_tools_list
                    logger.info(f"🔧 Adding {len(vertex_tools_list)} Tool objects to config")
                
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=config,
                )
                
                # Parse response - check for function calls first (like GeminiClient)
                content = ""
                tool_calls = []
                has_function_calls = False
                finish_reason = None
                
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'finish_reason'):
                        finish_reason = candidate.finish_reason
                        # Handle enum-like finish_reason
                        if hasattr(finish_reason, 'name'):
                            finish_reason_name = finish_reason.name
                        elif hasattr(finish_reason, 'value'):
                            finish_reason_name = str(finish_reason.value)
                        else:
                            finish_reason_name = str(finish_reason)
                    else:
                        finish_reason_name = None
                    
                    # Check for function calls in parts
                    if hasattr(candidate, 'content') and candidate.content:
                        if hasattr(candidate.content, 'parts'):
                            parts = candidate.content.parts
                            if parts:
                                for part in parts:
                                    # Check for function calls
                                    if hasattr(part, 'function_call') and part.function_call:
                                        has_function_calls = True
                                        func_call = part.function_call
                                        func_name = getattr(func_call, 'name', '')
                                        func_args_str = getattr(func_call, 'args', '')
                                        
                                        # Parse function arguments
                                        func_args = {}
                                        if func_args_str:
                                            if isinstance(func_args_str, str):
                                                try:
                                                    func_args = json.loads(func_args_str)
                                                except json.JSONDecodeError:
                                                    logger.warning(f"Could not parse function args as JSON: {func_args_str}")
                                                    func_args = {}
                                            elif isinstance(func_args_str, dict):
                                                func_args = func_args_str
                                        
                                        if func_name:
                                            tool_calls.append({
                                                "name": func_name,
                                                "parameters": func_args
                                            })
                                            logger.info(f"🔧 Found function call: {func_name} with args: {func_args}")
                                    
                                    # Extract text content
                                    if hasattr(part, 'text') and part.text:
                                        content += part.text
                
                # Handle MALFORMED_FUNCTION_CALL error
                if finish_reason_name == 'MALFORMED_FUNCTION_CALL':
                    logger.error(f"❌ Vertex AI returned MALFORMED_FUNCTION_CALL")
                    logger.error(f"   Response: {response}")
                    
                    # Try to extract the malformed function call from finish_message
                    if hasattr(response, 'candidates') and response.candidates:
                        candidate = response.candidates[0]
                        if hasattr(candidate, 'content') and candidate.content:
                            if hasattr(candidate.content, 'parts'):
                                parts = candidate.content.parts
                                if parts:
                                    for part in parts:
                                        if hasattr(part, 'text') and part.text:
                                            malformed_code = part.text
                                            logger.error(f"   Malformed code: {malformed_code[:500]}")
                    
                    # Raise error to be handled by caller
                    raise ValueError(
                        "Vertex AI generated malformed function call. "
                        "This usually means the tool format is incorrect or Vertex AI couldn't parse the function call. "
                        f"Finish reason: {finish_reason_name}"
                    )
                
                # If we have function calls, return them in a format compatible with the system
                if tool_calls:
                    logger.info(f"✅ Vertex AI generated {len(tool_calls)} function calls")
                    # Return as dict with tool calls (similar to GeminiClient format)
                    return {
                        "content": content,
                        "_parsed_tool_calls": tool_calls,
                        "raw_result": response
                    }
                
                # If no function calls, return text content
                if not content:
                    # Fallback: try response.text
                    content = response.text if hasattr(response, 'text') and response.text else ""
                    if not content:
                        content = str(response) if response else ""
                
                logger.info(f"✅ Vertex AI response generated (length: {len(content)} chars)")
                return content
            
            except Exception as e:
                logger.error(f"❌ Vertex AI generate_with_context error: {e}", exc_info=True)
                if hasattr(e, 'finish_reason') and e.finish_reason == 1:
                    logger.error("⚠️  Vertex AI blocked the request due to safety filters")
                    raise ValueError("La risposta è stata bloccata dai filtri di sicurezza di Vertex AI.")
                raise
