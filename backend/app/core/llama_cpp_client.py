"""
LlamaCppClient - Adapter for llama.cpp server (OpenAI-compatible API)
"""
import httpx
from typing import List, Dict, Optional, Any
from app.core.config import settings
import json
import logging

logger = logging.getLogger(__name__)


class LlamaCppClient:
    """
    Client for llama.cpp server using OpenAI-compatible API.
    Compatible with OllamaClient interface for easy integration.
    """
    
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize llama.cpp client.
        
        Args:
            base_url: llama.cpp server URL (default: settings.ollama_background_base_url)
            model: Model name (default: settings.ollama_background_model)
        """
        self.base_url = base_url or settings.ollama_background_base_url
        self.model = model or settings.ollama_background_model
        # llama.cpp is faster, use shorter timeout
        self.client = httpx.AsyncClient(timeout=180.0)
        
        # Ensure base_url has /v1 prefix for OpenAI API
        if not self.base_url.endswith('/v1'):
            if self.base_url.endswith('/'):
                self.base_url = self.base_url + 'v1'
            else:
                self.base_url = self.base_url + '/v1'
    
    async def generate_with_context(
        self,
        prompt: str,
        session_context: List[Dict[str, str]] = None,
        system_prompt: Optional[str] = None,
        retrieved_memory: Optional[List[str]] = None,
        tools_description: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        format: Optional[str] = None,
        return_raw: bool = False,
    ) -> str:
        """
        Generate response using llama.cpp OpenAI-compatible API.
        
        Args:
            prompt: Current user prompt
            session_context: Previous messages in the session
            system_prompt: System prompt
            retrieved_memory: Retrieved memory content to include
            tools_description: Description of available tools
            tools: List of tools (not supported by llama.cpp, ignored)
            format: Response format (not supported by llama.cpp, ignored)
            return_raw: Whether to return raw response
            
        Returns:
            Generated response text
        """
        try:
            # Build messages list
            messages = []
            
            # Add system prompt if provided
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            
            # Add retrieved memory as system message if provided
            if retrieved_memory:
                memory_text = "\n\n".join([f"- {mem}" for mem in retrieved_memory])
                memory_system_msg = f"=== Context from Memory ===\n{memory_text}\n=== End Context ==="
                messages.append({"role": "system", "content": memory_system_msg})
            
            # Add tools description as system message if provided
            if tools_description:
                messages.append({"role": "system", "content": tools_description})
            
            # Add session context
            if session_context:
                messages.extend(session_context)
            
            # Add current prompt
            messages.append({"role": "user", "content": prompt})
            
            # Prepare request payload
            payload = {
                "model": self.model or "gpt-3.5-turbo",  # llama.cpp uses this as default
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2000,
            }
            
            # Add format if specified (for JSON mode)
            if format == "json":
                payload["response_format"] = {"type": "json_object"}
            
            logger.debug(f"Calling llama.cpp API: {self.base_url}/chat/completions")
            logger.debug(f"Model: {self.model}, Messages: {len(messages)}")
            
            # Call OpenAI-compatible API
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            
            # Extract response text
            if "choices" in result and len(result["choices"]) > 0:
                response_text = result["choices"][0]["message"]["content"]
                
                if return_raw:
                    return json.dumps(result)
                return response_text
            else:
                logger.error(f"Unexpected response format: {result}")
                return ""
                
        except Exception as e:
            logger.error(f"Error calling llama.cpp API: {e}", exc_info=True)
            raise
    
    async def generate(
        self,
        prompt: str,
        context: Optional[List[Dict[str, str]]] = None,
        system: Optional[str] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate a response (compatible with OllamaClient interface).
        
        Args:
            prompt: User prompt
            context: List of previous messages
            system: System prompt
            stream: Whether to stream (not supported, ignored)
            
        Returns:
            Response dict compatible with Ollama format
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        if context:
            messages.extend(context)
        messages.append({"role": "user", "content": prompt})
        
        response_text = await self.generate_with_context(
            prompt=prompt,
            session_context=messages[:-1] if messages else [],  # Exclude last (user) message
            system_prompt=system,
        )
        
        # Return in Ollama-compatible format
        return {
            "message": {
                "content": response_text,
                "role": "assistant"
            },
            "model": self.model,
            "response": response_text,  # Keep for backward compatibility
        }
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

