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
import httpx
import asyncio


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
            {
                "name": "web_search",
                "description": "Esegue una ricerca sul web usando l'API di ricerca web di Ollama. Usa questo tool quando l'utente chiede informazioni aggiornate dal web, notizie, o informazioni che potrebbero non essere nel tuo training data. Richiede OLLAMA_API_KEY configurata.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "La query di ricerca da eseguire sul web"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "web_fetch",
                "description": "Recupera il contenuto di una pagina web specifica usando l'API di Ollama. Usa questo tool quando l'utente chiede di accedere a un URL specifico o di leggere il contenuto di una pagina web. Richiede OLLAMA_API_KEY configurata.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "L'URL della pagina web da recuperare"
                        }
                    },
                    "required": ["url"]
                }
            },
            {
                "name": "get_whatsapp_messages",
                "description": "Recupera messaggi WhatsApp. Usa questo tool quando l'utente chiede informazioni sui messaggi WhatsApp o vuole leggere messaggi recenti. Richiede che WhatsApp sia configurato e autenticato.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "contact_name": {
                            "type": "string",
                            "description": "Nome del contatto (opzionale). Se non specificato, recupera messaggi dalla chat attiva."
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Numero massimo di messaggi da recuperare (default: 10)",
                            "default": 10
                        }
                    }
                }
            },
            {
                "name": "send_whatsapp_message",
                "description": "Invia un messaggio WhatsApp a un contatto. Usa questo tool quando l'utente chiede di inviare un messaggio WhatsApp. Richiede che WhatsApp sia configurato e autenticato.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "phone_number": {
                            "type": "string",
                            "description": "Numero di telefono del destinatario (formato: +39XXXXXXXXXX o 39XXXXXXXXXX, senza spazi). REQUIRED."
                        },
                        "message": {
                            "type": "string",
                            "description": "Il messaggio da inviare. REQUIRED."
                        }
                    },
                    "required": ["phone_number", "message"]
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
        session_id: Optional[UUID] = None,
        auto_index: bool = True,
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
                result = await self._execute_mcp_tool(tool_name, parameters, db, session_id, auto_index)
                logger.info(f"MCP Tool {tool_name} completed")
                return result
            elif tool_name == "get_calendar_events":
                result = await self._execute_get_calendar_events(parameters, db)
                logger.info(f"Tool {tool_name} completed, result type: {type(result)}")
                return result
            elif tool_name == "get_emails":
                result = await self._execute_get_emails(parameters, db, session_id=session_id)
                logger.info(f"Tool {tool_name} completed, emails count: {result.get('count', 0) if isinstance(result, dict) else 'unknown'}")
                return result
            elif tool_name == "summarize_emails":
                result = await self._execute_summarize_emails(parameters, db)
                logger.info(f"Tool {tool_name} completed, summary length: {len(result.get('summary', '')) if isinstance(result, dict) else 'unknown'}")
                return result
            elif tool_name == "web_search":
                result = await self._execute_web_search(parameters, db, session_id, auto_index)
                logger.info(f"Tool {tool_name} completed")
                return result
            elif tool_name == "web_fetch":
                result = await self._execute_web_fetch(parameters, db, session_id, auto_index)
                logger.info(f"Tool {tool_name} completed")
                return result
            elif tool_name == "get_whatsapp_messages":
                result = await self._execute_get_whatsapp_messages(parameters)
                logger.info(f"Tool {tool_name} completed")
                return result
            elif tool_name == "send_whatsapp_message":
                result = await self._execute_send_whatsapp_message(parameters)
                logger.info(f"Tool {tool_name} completed")
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
        session_id: Optional[UUID] = None,
        auto_index: bool = True,
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
            
            # Auto-index emails if enabled and session_id provided
            index_stats = None
            if auto_index and session_id and emails:
                try:
                    from app.services.email_indexer import EmailIndexer
                    from app.core.dependencies import get_memory_manager
                    
                    # Initialize memory manager if not already done
                    from app.core.dependencies import init_clients
                    init_clients()
                    memory_manager = get_memory_manager()
                    email_indexer = EmailIndexer(memory_manager)
                    index_stats = await email_indexer.index_emails(
                        db=db,
                        emails=emails,
                        session_id=session_id,
                        auto_index=True,
                    )
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.info(f"Auto-indexed {index_stats.get('indexed', 0)} emails from get_emails tool")
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to auto-index emails: {e}", exc_info=True)
                    # Don't fail the tool call if indexing fails
            
            result = {
                "success": True,
                "emails": emails,
                "count": len(emails),
            }
            if index_stats:
                result["indexing_stats"] = index_stats
            
            return result
        except Exception as e:
            return {"error": str(e)}
    
    async def _execute_mcp_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        db: AsyncSession,
        session_id: Optional[UUID] = None,
        auto_index: bool = True,
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
                    
                    # For browser tools, try to close the browser session after use to prevent orphaned containers
                    # This is a best-effort cleanup - if it fails, it's not critical
                    if actual_tool_name in ["browser_navigate", "browser_snapshot", "browser_click", "browser_evaluate", "browser_fill_form"]:
                        try:
                            # Try to close the browser session (if supported by the MCP server)
                            # Note: This might not work if the MCP server doesn't support it or if the session is already closed
                            await asyncio.sleep(0.1)  # Small delay to ensure the previous operation is complete
                            await client.call_tool("browser_close", {})
                            logger.debug(f"   🧹 Browser session closed after {actual_tool_name}")
                        except Exception as close_error:
                            # Ignore errors - browser_close might not be available or session might already be closed
                            logger.debug(f"   Note: Could not close browser session (this is normal): {close_error}")
                    
                    tool_result = {
                        "success": True,
                        "result": result,
                        "tool": actual_tool_name,
                    }
                    
                    # Auto-index browser content if enabled
                    if auto_index and session_id and actual_tool_name in ["browser_navigate", "browser_snapshot"]:
                        try:
                            from app.services.web_indexer import WebIndexer
                            from app.core.dependencies import get_memory_manager
                            
                            memory_manager = get_memory_manager()
                            web_indexer = WebIndexer(memory_manager)
                            
                            url = parameters.get("url", "")
                            if actual_tool_name == "browser_snapshot" and isinstance(result, dict):
                                snapshot_content = result.get("result", result).get("content", "")
                                if snapshot_content:
                                    await web_indexer.index_browser_snapshot(
                                        db=db,
                                        url=url or "unknown",
                                        snapshot=str(snapshot_content),
                                        session_id=session_id,
                                    )
                                    logger.info(f"Auto-indexed browser snapshot for URL: {url}")
                            elif actual_tool_name == "browser_navigate":
                                # For navigate, we might want to index after snapshot is taken
                                # But navigate itself doesn't return content, so we skip for now
                                pass
                        except Exception as e:
                            logger.warning(f"Failed to auto-index browser content: {e}", exc_info=True)
                    
                    return tool_result
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
    
    async def _execute_web_search(
        self,
        parameters: Dict[str, Any],
        db: Optional[AsyncSession] = None,
        session_id: Optional[UUID] = None,
        auto_index: bool = True,
    ) -> Dict[str, Any]:
        """Execute web_search tool using Ollama's official library"""
        import logging
        logger = logging.getLogger(__name__)
        
        query = parameters.get("query")
        if not query:
            return {"error": "Query parameter is required for web_search"}
        
        # Check if API key is configured
        if not settings.ollama_api_key:
            logger.error("OLLAMA_API_KEY not configured. Web search requires an API key from https://ollama.com")
            return {
                "error": "OLLAMA_API_KEY not configured. Please set it in your .env file or environment variables. Get an API key from https://ollama.com"
            }
        
        try:
            # Use official Ollama library
            import os
            
            # IMPORTANT: Set API key BEFORE importing ollama functions
            # The library reads OLLAMA_API_KEY from environment at import time
            original_key = os.environ.get("OLLAMA_API_KEY")
            os.environ["OLLAMA_API_KEY"] = settings.ollama_api_key
            
            try:
                # Verify API key is set
                if not os.environ.get("OLLAMA_API_KEY"):
                    logger.error("OLLAMA_API_KEY not set in environment after assignment")
                    return {"error": "Failed to set OLLAMA_API_KEY for Ollama library"}
                
                # Import AFTER setting the environment variable
                # Use Client to ensure API key is properly configured
                from ollama import Client
                client = Client()
                
                # Call web_search from Ollama library via client
                results = client.web_search(query)
                
                # Format results for LLM
                # Results come as WebSearchResponse object with .results attribute
                if results and hasattr(results, 'results'):
                    results_list = results.results
                elif isinstance(results, list):
                    results_list = results
                elif isinstance(results, dict) and 'results' in results:
                    results_list = results['results']
                else:
                    results_list = []
                
                results_text = "\n\n=== Risultati Ricerca Web ===\n"
                for i, r in enumerate(results_list[:5], 1):  # Limit to 5 results
                    # Handle both WebSearchResult objects and dicts
                    if hasattr(r, 'title'):
                        # It's a WebSearchResult object
                        title = r.title
                        url = r.url
                        content = r.content
                    elif isinstance(r, dict):
                        # It's a dict
                        title = r.get('title', 'N/A')
                        url = r.get('url', 'N/A')
                        content = r.get('content', 'N/A')
                    else:
                        title = 'N/A'
                        url = 'N/A'
                        content = 'N/A'
                    
                    # Truncate content to avoid overwhelming the LLM
                    content_preview = str(content)[:1000] if content else 'N/A'
                    if content and len(str(content)) > 1000:
                        content_preview += "..."
                    
                    results_text += f"\n{i}. {title}\n"
                    results_text += f"   URL: {url}\n"
                    results_text += f"   Contenuto: {content_preview}\n"
                results_text += "\n=== Fine Risultati ===\n"
                
                # Convert results_list to a serializable format for storage
                # WebSearchResult objects need to be converted to dicts
                serializable_results = []
                for r in results_list:
                    if hasattr(r, 'title'):
                        # It's a WebSearchResult object - convert to dict
                        serializable_results.append({
                            'title': r.title,
                            'url': r.url,
                            'content': r.content,
                        })
                    else:
                        # Already a dict
                        serializable_results.append(r)
                
                result_dict = {
                    "success": True,
                    "result": {
                        "results": serializable_results,
                        "formatted_text": results_text,
                    }
                }
                
                # Auto-index search results if enabled
                if auto_index and session_id and db and serializable_results:
                    try:
                        from app.services.web_indexer import WebIndexer
                        from app.core.dependencies import get_memory_manager, init_clients
                        
                        # Initialize memory manager if not already done
                        init_clients()
                        memory_manager = get_memory_manager()
                        web_indexer = WebIndexer(memory_manager)
                        index_stats = await web_indexer.index_web_search_results(
                            db=db,
                            search_query=query,
                            results=serializable_results,
                            session_id=session_id,
                        )
                        result_dict["indexing_stats"] = index_stats
                        logger.info(f"Auto-indexed {index_stats.get('indexed', 0)} web search results")
                    except Exception as e:
                        logger.warning(f"Failed to auto-index web search results: {e}", exc_info=True)
                
                return result_dict
            finally:
                # Restore original API key if it existed
                if original_key:
                    os.environ["OLLAMA_API_KEY"] = original_key
                elif "OLLAMA_API_KEY" in os.environ:
                    del os.environ["OLLAMA_API_KEY"]
                    
        except ImportError as e:
            logger.error(f"Ollama library not installed or version too old: {e}")
            return {
                "error": f"Ollama library not installed or version too old. Please install with: pip install 'ollama>=0.6.0'"
            }
        except Exception as e:
            logger.error(f"Error calling Ollama web_search: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def _execute_web_fetch(
        self,
        parameters: Dict[str, Any],
        db: Optional[AsyncSession] = None,
        session_id: Optional[UUID] = None,
        auto_index: bool = True,
    ) -> Dict[str, Any]:
        """Execute web_fetch tool using Ollama's official library"""
        import logging
        logger = logging.getLogger(__name__)
        
        url = parameters.get("url")
        if not url:
            return {"error": "URL parameter is required for web_fetch"}
        
        # Ensure URL has protocol
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        
        # Check if API key is configured
        if not settings.ollama_api_key:
            logger.error("OLLAMA_API_KEY not configured. Web fetch requires an API key from https://ollama.com")
            return {
                "error": "OLLAMA_API_KEY not configured. Please set it in your .env file or environment variables. Get an API key from https://ollama.com"
            }
        
        try:
            # Use official Ollama library
            import os
            
            # IMPORTANT: Set API key BEFORE importing ollama functions
            # The library reads OLLAMA_API_KEY from environment at import time
            original_key = os.environ.get("OLLAMA_API_KEY")
            os.environ["OLLAMA_API_KEY"] = settings.ollama_api_key
            
            try:
                # Verify API key is set
                if not os.environ.get("OLLAMA_API_KEY"):
                    logger.error("OLLAMA_API_KEY not set in environment after assignment")
                    return {"error": "Failed to set OLLAMA_API_KEY for Ollama library"}
                
                # Import AFTER setting the environment variable
                # Use Client to ensure API key is properly configured
                from ollama import Client
                client = Client()
                
                # Call web_fetch from Ollama library via client
                result = client.web_fetch(url)
                
                # Extract fields from result
                title = result.title if hasattr(result, 'title') else result.get('title', 'N/A') if isinstance(result, dict) else 'N/A'
                content = result.content if hasattr(result, 'content') else result.get('content', 'N/A') if isinstance(result, dict) else 'N/A'
                links = result.links if hasattr(result, 'links') else result.get('links', []) if isinstance(result, dict) else []
                
                # Format result for LLM
                formatted_text = f"""=== Contenuto Pagina Web ===
Titolo: {title}
URL: {url}

Contenuto:
{content}

Link trovati: {', '.join(str(l) for l in links)[:200]}...
=== Fine Contenuto ===
"""
                
                result_dict = {
                    "success": True,
                    "result": {
                        "title": title,
                        "content": content,
                        "links": links,
                        "formatted_text": formatted_text,
                    }
                }
                
                # Auto-index web fetch result if enabled
                if auto_index and session_id and db:
                    try:
                        from app.services.web_indexer import WebIndexer
                        from app.core.dependencies import get_memory_manager, init_clients
                        
                        # Initialize memory manager if not already done
                        init_clients()
                        memory_manager = get_memory_manager()
                        web_indexer = WebIndexer(memory_manager)
                        indexed = await web_indexer.index_web_fetch_result(
                            db=db,
                            url=url,
                            result=result_dict["result"],
                            session_id=session_id,
                        )
                        if indexed:
                            result_dict["indexing_stats"] = {"indexed": True}
                            logger.info(f"Auto-indexed web fetch result for URL: {url}")
                    except Exception as e:
                        logger.warning(f"Failed to auto-index web fetch result: {e}", exc_info=True)
                
                return result_dict
            finally:
                # Restore original API key if it existed
                if original_key:
                    os.environ["OLLAMA_API_KEY"] = original_key
                elif "OLLAMA_API_KEY" in os.environ:
                    del os.environ["OLLAMA_API_KEY"]
                    
        except ImportError as e:
            logger.error(f"Ollama library not installed or version too old: {e}")
            return {
                "error": f"Ollama library not installed or version too old. Please install with: pip install 'ollama>=0.6.0'"
            }
        except Exception as e:
            logger.error(f"Error calling Ollama web_fetch: {e}", exc_info=True)
            return {"error": str(e)}
    
    async def _execute_get_whatsapp_messages(
        self,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute get_whatsapp_messages tool"""
        from app.api.integrations.whatsapp import get_whatsapp_service
        import logging
        
        logger = logging.getLogger(__name__)
        
        try:
            # Use the same global instance as the API endpoint
            whatsapp_service = get_whatsapp_service()
            
            # Check authentication status
            # If driver exists, check authentication status
            if whatsapp_service.driver:
                try:
                    auth_status = whatsapp_service._check_authentication_status()
                    if auth_status.get("authenticated", False):
                        whatsapp_service.is_authenticated = True
                    else:
                        return {
                            "error": "WhatsApp non autenticato. Per favore configura WhatsApp prima dalla pagina Integrations."
                        }
                except Exception as e:
                    logger.warning(f"Error checking WhatsApp auth status: {e}")
                    # If check fails but driver exists, try anyway
                    if not whatsapp_service.is_authenticated:
                        return {
                            "error": "WhatsApp non autenticato. Per favore configura WhatsApp prima dalla pagina Integrations."
                        }
            else:
                # No driver - need to setup first
                return {
                    "error": "WhatsApp non inizializzato. Per favore connetti WhatsApp dalla pagina Integrations prima di usare questa funzione."
                }
            
            contact_name = parameters.get("contact_name")
            max_results = parameters.get("max_results", 10)
            
            messages = await whatsapp_service.get_recent_messages(
                contact_name=contact_name,
                max_results=max_results,
            )
            
            return {
                "success": True,
                "messages": messages,
                "count": len(messages),
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def _execute_send_whatsapp_message(
        self,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute send_whatsapp_message tool"""
        from app.api.integrations.whatsapp import get_whatsapp_service
        import logging
        
        logger = logging.getLogger(__name__)
        
        try:
            # Use the same global instance as the API endpoint
            whatsapp_service = get_whatsapp_service()
            
            # Check authentication status
            # If driver doesn't exist, try to reconnect using persistent profile
            if not whatsapp_service.driver:
                logger.info("WhatsApp driver not initialized, attempting to reconnect with persistent profile...")
                try:
                    # Try to setup WhatsApp again using the same profile (non-blocking)
                    # This should reuse the existing authenticated session
                    await whatsapp_service.setup_whatsapp_web(
                        headless=False,  # Keep visible so user can see
                        wait_for_auth=False,  # Don't wait, just open
                        timeout=10,
                    )
                    logger.info("Successfully reconnected to WhatsApp Web")
                    # Wait a bit for page to load
                    import time
                    time.sleep(3)
                except Exception as e:
                    logger.error(f"Failed to reconnect WhatsApp driver: {e}")
                    return {
                        "error": f"WhatsApp non inizializzato. Per favore connetti WhatsApp dalla pagina Integrations prima di usare questa funzione. Errore: {str(e)}"
                    }
            
            # Now check authentication status
            if whatsapp_service.driver:
                try:
                    auth_status = whatsapp_service._check_authentication_status()
                    if auth_status.get("authenticated", False):
                        whatsapp_service.is_authenticated = True
                    else:
                        return {
                            "error": f"WhatsApp non autenticato. Status: {auth_status.get('status')}. {auth_status.get('message', 'Per favore configura WhatsApp prima dalla pagina Integrations.')}"
                        }
                except Exception as e:
                    logger.warning(f"Error checking WhatsApp auth status: {e}")
                    # If check fails but driver exists, try anyway
                    if not whatsapp_service.is_authenticated:
                        return {
                            "error": f"WhatsApp non autenticato. Errore nel controllo: {str(e)}"
                        }
            else:
                # Still no driver after reconnect attempt
                return {
                    "error": "WhatsApp non inizializzato. Per favore connetti WhatsApp dalla pagina Integrations prima di usare questa funzione."
                }
            
            phone_number = parameters.get("phone_number")
            message = parameters.get("message")
            
            if not phone_number:
                return {"error": "Numero di telefono richiesto"}
            if not message:
                return {"error": "Messaggio richiesto"}
            
            await whatsapp_service.send_message_pywhatkit(
                phone_number=phone_number,
                message=message,
            )
            
            return {
                "success": True,
                "message": f"Messaggio programmato per essere inviato a {phone_number}",
                "note": "Il messaggio verrà inviato tra circa 1 minuto (tempo necessario per aprire WhatsApp Web)"
            }
        except Exception as e:
            return {"error": str(e)}

