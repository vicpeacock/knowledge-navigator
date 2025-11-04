"""
Tool Manager - Manages available tools and executes them when requested by LLM
"""
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.services.email_service import EmailService
from app.services.calendar_service import CalendarService
from app.services.date_parser import DateParser
from app.models.database import Integration
from app.core.config import settings
from app.core.mcp_client import MCPClient
import re
import json


class ToolManager:
    """Manages tools available to the LLM"""
    
    def __init__(self, db: Optional[AsyncSession] = None):
        self.db = db
        self.email_service = EmailService()
        self.calendar_service = CalendarService()
        self.date_parser = DateParser()
        self._mcp_clients_cache: Dict[str, MCPClient] = {}
    
    def get_base_tools(self) -> List[Dict[str, Any]]:
        """Get list of base built-in tools with their schemas"""
        return [
            {
                "name": "get_calendar_events",
                "description": "Recupera eventi dal calendario Google. Usa questo tool quando l'utente chiede informazioni sul calendario, eventi, appuntamenti, meeting.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Query in linguaggio naturale per filtrare eventi (es: 'eventi domani', 'meeting questa settimana'). Se vuoto, recupera eventi dei prossimi 7 giorni."
                        },
                        "start_time": {
                            "type": "string",
                            "description": "Data/ora di inizio in formato ISO (opzionale)"
                        },
                        "end_time": {
                            "type": "string",
                            "description": "Data/ora di fine in formato ISO (opzionale)"
                        }
                    }
                }
            },
            {
                "name": "get_emails",
                "description": "Recupera email da Gmail. Usa questo tool quando l'utente chiede informazioni sulle email, email non lette, messaggi, posta, o l'ultima email ricevuta.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Query Gmail (es: 'is:unread' per email non lette, 'from:example@gmail.com' per email da un mittente specifico). Se vuoto, recupera le ultime email."
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Numero massimo di email da recuperare (default: 1 per 'ultima email', 10 altrimenti, max: 50)",
                            "default": 10
                        },
                        "include_body": {
                            "type": "boolean",
                            "description": "Includere il corpo completo delle email. DEVI impostarlo a true se l'utente chiede un riassunto o il contenuto (default: true)",
                            "default": True
                        }
                    }
                }
            },
            {
                "name": "summarize_emails",
                "description": "Riassume automaticamente le email non lette usando AI. Usa questo tool quando l'utente chiede un riassunto delle email o delle ultime email.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "max_emails": {
                            "type": "integer",
                            "description": "Numero massimo di email da riassumere (default: 5)",
                            "default": 5
                        }
                    }
                }
            },
        ]
    
    async def get_mcp_tools(self) -> List[Dict[str, Any]]:
        """Get MCP tools from enabled integrations"""
        if not self.db:
            return []
        
        try:
            # Get all enabled MCP integrations
            result = await self.db.execute(
                select(Integration)
                .where(Integration.service_type == "mcp_server")
                .where(Integration.enabled == True)
            )
            integrations = result.scalars().all()
            
            mcp_tools = []
            
            for integration in integrations:
                selected_tools = integration.session_metadata.get("selected_tools", []) if integration.session_metadata else []
                if not selected_tools:
                    continue
                
                # Get or create MCP client for this integration
                integration_key = str(integration.id)
                if integration_key not in self._mcp_clients_cache:
                    server_url = integration.session_metadata.get("server_url", "") if integration.session_metadata else ""
                    if server_url:
                        self._mcp_clients_cache[integration_key] = MCPClient(base_url=server_url)
                    else:
                        self._mcp_clients_cache[integration_key] = MCPClient()
                
                client = self._mcp_clients_cache[integration_key]
                
                # Fetch all tools from the server
                try:
                    all_tools = await client.list_tools()
                    
                    # Filter to only selected tools and convert to our format
                    for tool_info in all_tools:
                        if isinstance(tool_info, dict):
                            tool_name = tool_info.get("name", "")
                            if tool_name in selected_tools:
                                # Convert MCP tool format to our format
                                mcp_tool = {
                                    "name": f"mcp_{tool_name}",  # Prefix to avoid conflicts
                                    "description": tool_info.get("description", f"MCP tool: {tool_name}"),
                                    "parameters": tool_info.get("inputSchema", {}),
                                    "mcp_integration_id": str(integration.id),
                                    "mcp_tool_name": tool_name,
                                    "mcp_server_url": integration.session_metadata.get("server_url", "") if integration.session_metadata else "",
                                }
                                mcp_tools.append(mcp_tool)
                except Exception as e:
                    # Log error but continue with other integrations
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Error fetching tools from MCP integration {integration.id}: {e}")
            
            return mcp_tools
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error loading MCP tools: {e}", exc_info=True)
            return []
    
    async def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of all available tools (base + MCP)"""
        base_tools = self.get_base_tools()
        mcp_tools = await self.get_mcp_tools()
        return base_tools + mcp_tools
    
    async def get_tools_system_prompt(self) -> str:
        """Generate minimal system prompt - tools are passed natively to Ollama"""
        # When tools are passed natively via the API, Ollama handles them automatically
        # We only need a brief reminder to use tools when needed
        return "\n\nHai accesso a vari strumenti (tools) che puoi usare quando necessario. Usali quando servono informazioni esterne o azioni specifiche."
    
    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """Execute a tool by name"""
        import logging
        logger = logging.getLogger(__name__)
        
        if db is None:
            db = self.db
        
        if db is None:
            return {"error": "Database session not available"}
        
        logger.info(f"Executing tool: {tool_name} with parameters: {parameters}")
        
        try:
            # Check if it's an MCP tool (prefixed with "mcp_")
            if tool_name.startswith("mcp_"):
                result = await self._execute_mcp_tool(tool_name, parameters, db)
                logger.info(f"MCP Tool {tool_name} completed")
                return result
            elif tool_name == "get_calendar_events":
                result = await self._execute_get_calendar_events(parameters, db)
                logger.info(f"Tool {tool_name} completed, result type: {type(result)}")
                return result
            elif tool_name == "get_emails":
                result = await self._execute_get_emails(parameters, db)
                logger.info(f"Tool {tool_name} completed, emails count: {result.get('count', 0) if isinstance(result, dict) else 'unknown'}")
                return result
            elif tool_name == "summarize_emails":
                result = await self._execute_summarize_emails(parameters, db)
                logger.info(f"Tool {tool_name} completed, summary length: {len(result.get('summary', '')) if isinstance(result, dict) else 'unknown'}")
                return result
            else:
                logger.error(f"Unknown tool: {tool_name}")
                return {"error": f"Tool '{tool_name}' not found"}
        except Exception as e:
            logger.error(f"Exception in tool execution {tool_name}: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def _execute_get_calendar_events(
        self,
        parameters: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Execute get_calendar_events tool"""
        from app.models.database import Integration
        from app.api.integrations.calendars import _decrypt_credentials
        from sqlalchemy import select
        from datetime import datetime, timezone, timedelta
        
        try:
            # Get calendar integration
            result = await db.execute(
                select(Integration)
                .where(Integration.provider == "google")
                .where(Integration.service_type == "calendar")
                .where(Integration.enabled == True)
                .limit(1)
            )
            integration = result.scalar_one_or_none()
            
            if not integration:
                return {"error": "Nessuna integrazione Google Calendar configurata"}
            
            # Decrypt credentials
            credentials = _decrypt_credentials(
                integration.credentials_encrypted,
                settings.credentials_encryption_key
            )
            
            # Setup service
            await self.calendar_service.setup_google(credentials, str(integration.id))
            
            # Parse dates
            query = parameters.get("query", "")
            start_time = None
            end_time = None
            
            if parameters.get("start_time"):
                start_time = datetime.fromisoformat(parameters["start_time"])
            elif query:
                start_time, end_time = self.date_parser.parse_query(query)
            
            if not start_time:
                start_time = datetime.now(timezone.utc)
            if not end_time:
                end_time = start_time + timedelta(days=7)
            
            # Get events
            events = await self.calendar_service.get_google_events(
                start_time=start_time,
                end_time=end_time,
                max_results=20,
                integration_id=str(integration.id),
            )
            
            return {
                "success": True,
                "events": events,
                "count": len(events),
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def _execute_get_emails(
        self,
        parameters: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Execute get_emails tool"""
        from app.models.database import Integration
        from app.api.integrations.emails import _decrypt_credentials
        from sqlalchemy import select
        
        try:
            # Get email integration
            result = await db.execute(
                select(Integration)
                .where(Integration.provider == "google")
                .where(Integration.service_type == "email")
                .where(Integration.enabled == True)
                .limit(1)
            )
            integration = result.scalar_one_or_none()
            
            if not integration:
                return {"error": "Nessuna integrazione Gmail configurata"}
            
            # Decrypt credentials
            credentials = _decrypt_credentials(
                integration.credentials_encrypted,
                settings.credentials_encryption_key
            )
            
            # Setup service
            await self.email_service.setup_gmail(credentials, str(integration.id))
            
            # Get emails
            gmail_query = parameters.get("query", None)
            max_results = parameters.get("max_results", 10)
            include_body = parameters.get("include_body", False)
            
            emails = await self.email_service.get_gmail_messages(
                max_results=max_results,
                query=gmail_query,
                integration_id=str(integration.id),
                include_body=include_body,
            )
            
            return {
                "success": True,
                "emails": emails,
                "count": len(emails),
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def _execute_mcp_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Execute an MCP tool"""
        import logging
        logger = logging.getLogger(__name__)
        
        # Extract actual tool name (remove "mcp_" prefix)
        actual_tool_name = tool_name.replace("mcp_", "", 1)
        logger.info(f"🔧 Executing MCP tool: '{tool_name}' -> actual name: '{actual_tool_name}'")
        logger.info(f"   Parameters: {parameters}")
        
        # Find the MCP integration that provides this tool
        result = await db.execute(
            select(Integration)
            .where(Integration.service_type == "mcp_server")
            .where(Integration.enabled == True)
        )
        integrations = result.scalars().all()
        
        logger.info(f"   Found {len(integrations)} enabled MCP integration(s)")
        
        for integration in integrations:
            selected_tools = integration.session_metadata.get("selected_tools", []) if integration.session_metadata else []
            server_url = integration.session_metadata.get("server_url", "") if integration.session_metadata else ""
            
            logger.info(f"   Integration {integration.id}:")
            logger.info(f"     Server URL: {server_url}")
            logger.info(f"     Selected tools: {selected_tools}")
            logger.info(f"     Looking for tool: '{actual_tool_name}'")
            
            if actual_tool_name in selected_tools:
                logger.info(f"   ✅ Tool '{actual_tool_name}' found in integration {integration.id}")
                
                # Get or create MCP client
                integration_key = str(integration.id)
                if integration_key not in self._mcp_clients_cache:
                    if server_url:
                        logger.info(f"   Creating new MCP client with URL: {server_url}")
                        self._mcp_clients_cache[integration_key] = MCPClient(base_url=server_url)
                    else:
                        logger.warning(f"   No server_url in integration, using default from settings")
                        self._mcp_clients_cache[integration_key] = MCPClient()
                
                client = self._mcp_clients_cache[integration_key]
                logger.info(f"   Using MCP client with base_url: {client.base_url}")
                
                try:
                    # Call the MCP tool
                    logger.info(f"   Calling tool '{actual_tool_name}' on MCP server")
                    result = await client.call_tool(actual_tool_name, parameters, stream=False)
                    logger.info(f"   ✅ Tool call successful")
                    return {
                        "success": True,
                        "result": result,
                        "tool": actual_tool_name,
                    }
                except Exception as e:
                    logger.error(f"   ❌ Error calling MCP tool {actual_tool_name}: {e}", exc_info=True)
                    return {"error": f"Error calling MCP tool: {str(e)}"}
            else:
                logger.info(f"   ⚠️ Tool '{actual_tool_name}' NOT in selected_tools for this integration")
        
        logger.error(f"❌ MCP tool '{actual_tool_name}' not found in any enabled integration")
        return {"error": f"MCP tool '{actual_tool_name}' not found in any enabled integration"}
    
    async def _execute_summarize_emails(
        self,
        parameters: Dict[str, Any],
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Execute summarize_emails tool"""
        from app.models.database import Integration
        from app.api.integrations.emails import _decrypt_credentials
        from app.core.ollama_client import OllamaClient
        from sqlalchemy import select
        
        try:
            # Get email integration
            result = await db.execute(
                select(Integration)
                .where(Integration.provider == "google")
                .where(Integration.service_type == "email")
                .where(Integration.enabled == True)
                .limit(1)
            )
            integration = result.scalar_one_or_none()
            
            if not integration:
                return {"error": "Nessuna integrazione Gmail configurata"}
            
            # Decrypt credentials
            credentials = _decrypt_credentials(
                integration.credentials_encrypted,
                settings.credentials_encryption_key
            )
            
            # Setup service
            await self.email_service.setup_gmail(credentials, str(integration.id))
            
            # Get unread emails
            max_emails = parameters.get("max_emails", 5)
            emails = await self.email_service.get_gmail_messages(
                max_results=max_emails,
                query="is:unread",
                integration_id=str(integration.id),
                include_body=True,
            )
            
            if not emails:
                return {"success": True, "summary": "Nessuna email non letta trovata.", "count": 0}
            
            # Create summary using Ollama
            email_summaries = []
            for email in emails:
                email_text = f"From: {email['from']}\nSubject: {email['subject']}\n"
                if email.get('body'):
                    body = email['body'][:1000] if len(email.get('body', '')) > 1000 else email.get('body', '')
                    email_text += f"Body: {body}\n"
                else:
                    email_text += f"Snippet: {email.get('snippet', '')}\n"
                email_summaries.append(email_text)
            
            all_emails_text = "\n\n---\n\n".join(email_summaries)
            summary_prompt = f"""Riassumi le seguenti email non lette in modo conciso e utile. 
Indica per ciascuna: mittente, oggetto, e punti chiave del contenuto.

Email:
{all_emails_text}

Riassunto:"""
            
            ollama = OllamaClient()
            summary = await ollama.generate_with_context(
                prompt=summary_prompt,
                session_context=[],
                retrieved_memory=None,
            )
            
            return {
                "success": True,
                "summary": summary,
                "emails_count": len(emails),
            }
        except Exception as e:
            return {"error": str(e)}
    
    def parse_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """
        Parse tool calls from LLM response text
        Looks for JSON tool calls in the format: {"tool_call": {"name": "...", "parameters": {...}}}
        Also handles cases where model returns just parameters like {"url": "..."} for browser tools
        """
        tool_calls = []
        import logging
        logger = logging.getLogger(__name__)
        
        # Try to find complete JSON object with tool_call at the beginning of text
        text_stripped = text.strip()
        
        # Pattern 1: Complete JSON object starting at beginning (most reliable)
        try:
            # Try parsing entire beginning as JSON
            json_start = re.match(r'^(\{[^}]*"tool_call"[^}]*\{[^}]*(?:\{[^}]*\}[^}]*)*\}[^}]*\})', text_stripped, re.DOTALL)
            if json_start:
                parsed = json.loads(json_start.group(1))
                if "tool_call" in parsed and isinstance(parsed["tool_call"], dict):
                    tool_calls.append(parsed["tool_call"])
                    logger.info(f"✅ Parsed tool_call from JSON: {parsed['tool_call'].get('name')}")
                    return tool_calls  # Return early if found
        except Exception as e:
            logger.debug(f"Pattern 1 failed: {e}")
        
        # Pattern 2: Find JSON anywhere in text (more flexible)
        # Look for {"tool_call": {...}}
        json_anywhere_pattern = r'\{\s*"tool_call"\s*:\s*\{[^}]*(?:\{[^}]*\}[^}]*)*\}\s*\}'
        matches = re.finditer(json_anywhere_pattern, text, re.DOTALL)
        for match in matches:
            try:
                parsed = json.loads(match.group(0))
                if "tool_call" in parsed and "name" in parsed["tool_call"]:
                    # Only add if not already found
                    if not any(tc.get("name") == parsed["tool_call"]["name"] for tc in tool_calls):
                        tool_calls.append(parsed["tool_call"])
            except Exception:
                # Try manual extraction
                try:
                    name_match = re.search(r'"name"\s*:\s*"([^"]+)"', match.group(0))
                    params_match = re.search(r'"parameters"\s*:\s*(\{[^}]*(?:\{[^}]*\}[^}]*)*\})', match.group(0), re.DOTALL)
                    if name_match and params_match:
                        params = json.loads(params_match.group(1))
                        if not any(tc.get("name") == name_match.group(1) for tc in tool_calls):
                            tool_calls.append({
                                "name": name_match.group(1),
                                "parameters": params
                            })
                except Exception:
                    pass
        
        # Pattern 3: Handle case where model returns just parameters like {"url": "..."}
        # This is a fallback for when the model doesn't follow the full format
        # We'll try to infer which tool to use based on the parameters
        if not tool_calls:
            try:
                # Try to parse JSON at the start of the text
                json_match = re.match(r'^\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text_stripped)
                if json_match:
                    parsed_params = json.loads(json_match.group(0))
                    # Check if it looks like browser tool parameters (has "url" key)
                    if "url" in parsed_params and isinstance(parsed_params["url"], str):
                        logger.info(f"⚠️ Model returned only parameters {{url: ...}}, inferring browser_navigate tool")
                        # Infer browser navigate tool
                        tool_calls.append({
                            "name": "mcp_browser_navigate",  # Default, will be checked/updated in sessions.py
                            "parameters": parsed_params
                        })
                        logger.info(f"✅ Inferred tool_call: mcp_browser_navigate with parameters: {parsed_params}")
            except Exception as e:
                logger.debug(f"Pattern 3 (parameter inference) failed: {e}")
        
        return tool_calls

