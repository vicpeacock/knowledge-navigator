"""
Tool Manager - Manages available tools and executes them when requested by LLM
"""
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.services.email_service import EmailService, IntegrationAuthError
from app.services.calendar_service import CalendarService
from app.services.date_parser import DateParser
from app.models.database import Integration, Session as SessionModel
from app.core.config import settings
from app.core.mcp_client import MCPClient
import re
import json
import httpx
import asyncio

if TYPE_CHECKING:
    # Avoid circular imports at runtime; only for type hints
    from app.models.database import User


class ToolManager:
    """Manages tools available to the LLM"""
    
    def __init__(self, db: Optional[AsyncSession] = None, tenant_id: Optional[UUID] = None):
        self.db = db
        self.tenant_id = tenant_id
        self.email_service = EmailService()
        self.calendar_service = CalendarService()
        self.date_parser = DateParser()
        self._mcp_clients_cache: Dict[str, MCPClient] = {}
    
    def get_base_tools(self) -> List[Dict[str, Any]]:
        """Get list of base built-in tools with their schemas"""
        return [
            {
                "name": "get_calendar_events",
                "description": "Recupera eventi dal calendario Google.",
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
                "description": "Recupera email da Gmail. Usa query Gmail standard (es: 'is:unread' per email non lette, 'from:example@gmail.com' per email da un mittente).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Query Gmail. Lasciare vuoto per recuperare tutte le email. Usa 'is:unread' per email non lette."
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Numero massimo di email da recuperare. Default: 10, max: 50",
                            "default": 10
                        },
                        "include_body": {
                            "type": "boolean",
                            "description": "Includere il corpo completo delle email. Default: true",
                            "default": True
                        }
                    }
                }
            },
            {
                "name": "summarize_emails",
                "description": "Riassume automaticamente le email non lette usando AI.",
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
                "name": "archive_email",
                "description": "Archivia un'email rimuovendola dalla Posta in arrivo.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "email_id": {
                            "type": "string",
                            "description": "ID dell'email Gmail da archiviare (es: '19a98336265a2d64')"
                        }
                    },
                    "required": ["email_id"]
                }
            },
            {
                "name": "send_email",
                "description": "Invia un'email tramite Gmail.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to": {
                            "type": "string",
                            "description": "Indirizzo email del destinatario (es: 'example@gmail.com')"
                        },
                        "subject": {
                            "type": "string",
                            "description": "Oggetto dell'email"
                        },
                        "body": {
                            "type": "string",
                            "description": "Corpo dell'email in testo semplice"
                        },
                        "body_html": {
                            "type": "string",
                            "description": "Corpo dell'email in HTML (opzionale, se non fornito usa body)"
                        }
                    },
                    "required": ["to", "subject", "body"]
                }
            },
            {
                "name": "reply_to_email",
                "description": "Risponde a un'email esistente tramite Gmail.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "email_id": {
                            "type": "string",
                            "description": "ID dell'email Gmail a cui rispondere (es: '19a98336265a2d64')"
                        },
                        "body": {
                            "type": "string",
                            "description": "Corpo della risposta in testo semplice"
                        },
                        "body_html": {
                            "type": "string",
                            "description": "Corpo della risposta in HTML (opzionale, se non fornito usa body)"
                        }
                    },
                    "required": ["email_id", "body"]
                }
            },
            {
                "name": "web_search",
                "description": "Esegue una ricerca sul web usando l'API di ricerca web di Ollama. Richiede OLLAMA_API_KEY configurata.",
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
                "description": "Recupera il contenuto di una pagina web specifica usando l'API di Ollama. Richiede OLLAMA_API_KEY configurata.",
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
            # WhatsApp integration temporarily disabled - will be re-enabled with Business API
            # {
            #     "name": "get_whatsapp_messages",
            #     "description": "🔴 OBBLIGATORIO per qualsiasi richiesta su WhatsApp! Usa questo tool quando l'utente: chiede messaggi WhatsApp, vuole vedere messaggi ricevuti, chiede 'cosa ho ricevuto oggi', 'messaggi di oggi', 'messaggi di ieri', o qualsiasi domanda relativa a WhatsApp. NON rispondere mai senza aver chiamato questo tool prima. OBBLIGATORIO: Se l'utente chiede 'messaggi di oggi', 'messaggi ricevuti oggi', 'cosa ho ricevuto oggi', 'che messaggi ho ricevuto oggi', o qualsiasi richiesta che menziona 'oggi', DEVI SEMPRE usare date_filter='today'. Se l'utente chiede 'ieri', usa date_filter='yesterday'. I messaggi includono testo, data/ora, e mittente. IMPORTANTE: Prima di dire che WhatsApp non è configurato o che non ci sono messaggi, DEVI chiamare questo tool per verificare.",
            #     "parameters": {
            #         "type": "object",
            #         "properties": {
            #             "contact_name": {
            #                 "type": "string",
            #                 "description": "Nome del contatto (opzionale). Se non specificato, recupera messaggi dalla chat attiva."
            #             },
            #             "max_results": {
            #                 "type": "integer",
            #                 "description": "Numero massimo di messaggi da recuperare (default: 20 per avere più messaggi da filtrare per data)",
            #                 "default": 20
            #             },
            #             "date_filter": {
            #                 "type": "string",
            #                 "description": "Filtro per data (opzionale ma IMPORTANTE). Valori: 'today' per messaggi di oggi, 'yesterday' per ieri, 'this_week' per questa settimana. DEVI usare 'today' quando l'utente chiede messaggi di oggi. Se non specificato, restituisce i messaggi più recenti."
            #             }
            #         },
            #         "required": []
            #     }
            # },
            # {
            #     "name": "send_whatsapp_message",
            #     "description": "Invia un messaggio WhatsApp a un contatto. Usa questo tool quando l'utente chiede di inviare un messaggio WhatsApp. Richiede che WhatsApp sia configurato e autenticato.",
            #     "parameters": {
            #         "type": "object",
            #         "properties": {
            #             "phone_number": {
            #                 "type": "string",
            #                 "description": "Numero di telefono del destinatario (formato: +39XXXXXXXXXX o 39XXXXXXXXXX, senza spazi). REQUIRED."
            #             },
            #             "message": {
            #                 "type": "string",
            #                 "description": "Il messaggio da inviare. REQUIRED."
            #             }
            #         },
            #         "required": ["phone_number", "message"]
            #     }
            # },
        ]
    
    async def get_mcp_tools(self, current_user: Optional["User"] = None, include_all: bool = False) -> List[Dict[str, Any]]:  # type: ignore[name-defined]
        """Get MCP tools from enabled integrations (tenant-level/global).

        MCP integrations are global per tenant (user_id = NULL), but tool selection
        is per-user. This method reads per-user tool preferences from user_metadata.
        
        Args:
            current_user: Optional user object to get per-user tool preferences
            include_all: If True, return all available tools without filtering by user preferences
        """
        if not self.db or not self.tenant_id:
            return []
        
        try:
            # Get all enabled MCP integrations for this tenant
            # MCP integrations are global (user_id = NULL) so all users can see them
            query = (
                select(Integration)
                .where(Integration.service_type == "mcp_server")
                .where(Integration.enabled == True)
                .where(Integration.tenant_id == self.tenant_id)
                .where(Integration.user_id.is_(None))  # Only global MCP integrations
            )
            result = await self.db.execute(query)
            integrations = result.scalars().all()
            
            mcp_tools = []
            
            for integration in integrations:
                # Get per-user tool preferences (only if not including all)
                selected_tools = []
                if not include_all and current_user:
                    user_metadata = current_user.user_metadata or {}
                    mcp_preferences = user_metadata.get("mcp_tools_preferences", {})
                    selected_tools = mcp_preferences.get(str(integration.id), [])
                
                # If current_user is None, include all tools (no user preferences to respect)
                # If include_all is True, include all tools
                # If current_user is provided but no preferences set, include all tools (default behavior)
                # Only skip if current_user is provided AND has preferences AND selected_tools is empty
                if not include_all and current_user is not None and not selected_tools:
                    # Check if user has any preferences set at all for this integration
                    user_metadata = current_user.user_metadata or {}
                    mcp_preferences = user_metadata.get("mcp_tools_preferences", {})
                    # If user has preferences dict but this integration is not in it, include all tools
                    # If user has preferences dict and this integration is in it but empty, skip (user explicitly deselected all)
                    if str(integration.id) in mcp_preferences:
                        # User has preferences for this integration but selected_tools is empty - skip
                        continue
                    # User doesn't have preferences for this integration - include all tools (default)
                
                # Get or create MCP client for this integration
                integration_key = str(integration.id)
                if integration_key not in self._mcp_clients_cache:
                    session_metadata = integration.session_metadata or {}
                    server_url = session_metadata.get("server_url", "")
                    if server_url:
                        self._mcp_clients_cache[integration_key] = MCPClient(base_url=server_url)
                    else:
                        self._mcp_clients_cache[integration_key] = MCPClient()
                
                client = self._mcp_clients_cache[integration_key]
                
                # Fetch all tools from the server
                try:
                    all_tools = await client.list_tools()
                    
                    # Get integration name for display
                    session_metadata = integration.session_metadata or {}
                    integration_name = session_metadata.get("name") or session_metadata.get("server_url") or "Unknown MCP Server"
                    
                    # Helper function to detect server name from tool name
                    def detect_server_from_tool_name(tool_name: str) -> str:
                        """Detect which MCP server a tool belongs to based on its name"""
                        tool_lower = tool_name.lower()
                        
                        # Pattern matching for known MCP servers (order matters - more specific first)
                        if "wikipedia" in tool_lower or "wiki" in tool_lower:
                            return "Wikipedia"
                        elif "playwright" in tool_lower or "browser" in tool_lower or "navigate" in tool_lower or "screenshot" in tool_lower:
                            return "Playwright"
                        elif ("paper" in tool_lower or "arxiv" in tool_lower or "research" in tool_lower or "pubmed" in tool_lower or
                              "biorxiv" in tool_lower or "crossref" in tool_lower or "iacr" in tool_lower or 
                              "medrxiv" in tool_lower or "semantic" in tool_lower or "download_biorxiv" in tool_lower or
                              "download_crossref" in tool_lower or "download_iacr" in tool_lower or "download_medrxiv" in tool_lower or
                              "download_semantic" in tool_lower or "search_biorxiv" in tool_lower or "search_crossref" in tool_lower or
                              "search_iacr" in tool_lower or "search_medrxiv" in tool_lower or "search_semantic" in tool_lower):
                            return "Paper Search"
                        elif "google" in tool_lower or "maps" in tool_lower or "geocod" in tool_lower or "places" in tool_lower:
                            return "Google Maps"
                        else:
                            # Default: use integration name or "Unknown"
                            return integration_name
                    
                    # Filter to only selected tools (if not including all) and convert to our format
                    for tool_info in all_tools:
                        if isinstance(tool_info, dict):
                            tool_name = tool_info.get("name", "")
                            # If include_all is True, include all tools
                            # If current_user is None, include all tools (no preferences to respect)
                            # If selected_tools is empty but current_user is None, include all tools
                            # Otherwise, filter by selected_tools
                            should_include = (
                                include_all or 
                                current_user is None or 
                                (not selected_tools and str(integration.id) not in (current_user.user_metadata or {}).get("mcp_tools_preferences", {})) or
                                tool_name in selected_tools
                            )
                            if should_include:
                                # Detect server name from tool name
                                detected_server = detect_server_from_tool_name(tool_name)
                                
                                # Convert MCP tool format to our format
                                original_description = tool_info.get("description", f"MCP tool: {tool_name}")
                                
                                # Enhance descriptions for Google Maps tools to be more explicit
                                enhanced_description = original_description
                                if detected_server == "Google Maps":
                                    if "directions" in tool_name.lower():
                                        enhanced_description = f"Get directions and route information between two locations using Google Maps. Use this tool when the user asks for directions, routes, how to get somewhere, travel planning, or navigation. {original_description}"
                                    elif "distance" in tool_name.lower() or "matrix" in tool_name.lower():
                                        enhanced_description = f"Calculate distances and travel times between multiple locations using Google Maps. Use this tool when the user asks about distances, travel times, or comparing routes. {original_description}"
                                    elif "geocode" in tool_name.lower():
                                        enhanced_description = f"Convert addresses to coordinates (latitude/longitude) using Google Maps. Use this tool when the user provides an address and you need its location coordinates. {original_description}"
                                    elif "reverse" in tool_name.lower() and "geocode" in tool_name.lower():
                                        enhanced_description = f"Get address from coordinates (latitude/longitude) using Google Maps. Use this tool when you have coordinates and need the address. {original_description}"
                                    elif "place" in tool_name.lower() and "search" in tool_name.lower():
                                        enhanced_description = f"Search for places (restaurants, shops, points of interest) using Google Maps. Use this tool when the user asks to find places, search for locations, or discover nearby points of interest. {original_description}"
                                    elif "place" in tool_name.lower() and "details" in tool_name.lower():
                                        enhanced_description = f"Get detailed information about a specific place using Google Maps. Use this tool when the user asks for details about a place, business, or location. {original_description}"
                                    elif "elevation" in tool_name.lower():
                                        enhanced_description = f"Get elevation data for geographic points using Google Maps. Use this tool when the user asks about elevation, altitude, or height above sea level. {original_description}"
                                
                                mcp_tool = {
                                    "name": f"mcp_{tool_name}",  # Prefix to avoid conflicts
                                    "description": enhanced_description,
                                    "parameters": tool_info.get("inputSchema", {}),
                                    "mcp_integration_id": str(integration.id),
                                    "mcp_tool_name": tool_name,
                                    "mcp_server_url": session_metadata.get("server_url", ""),
                                    "mcp_integration_name": integration_name,
                                    "mcp_server_name": detected_server,  # Server name detected from tool name
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
    
    async def get_available_tools(self, current_user: Optional["User"] = None) -> List[Dict[str, Any]]:  # type: ignore[name-defined]
        """Get list of all available tools (base + MCP), filtered by user preferences if provided."""
        import logging
        logger = logging.getLogger(__name__)
        
        base_tools = self.get_base_tools()
        
        # Try to get MCP tools, but don't fail if they're unavailable
        mcp_tools = []
        try:
            mcp_tools = await self.get_mcp_tools(current_user=current_user)
            logger.info(f"🔧 get_available_tools: Retrieved {len(mcp_tools)} MCP tools (current_user={'present' if current_user else 'None'})")
            if mcp_tools:
                maps_tools = [t for t in mcp_tools if 'maps' in t.get('name', '').lower()]
                logger.info(f"   🗺️  Google Maps tools: {len(maps_tools)}")
        except Exception as e:
            logger.warning(f"MCP tools unavailable, continuing with base tools only: {e}")
            # Continue with base tools only
        
        tools = base_tools + mcp_tools
        logger.info(f"🔧 get_available_tools: Total tools before filtering: {len(tools)} (base: {len(base_tools)}, MCP: {len(mcp_tools)})")

        # Apply per-user tool preferences if available
        if current_user is not None:
            try:
                metadata = getattr(current_user, "user_metadata", {}) or {}
                enabled_tools = metadata.get("enabled_tools")
                
                # Log current state for debugging
                logger.info(f"🔍 User tool preferences check for user {current_user.email}: enabled_tools={enabled_tools} (type: {type(enabled_tools)})")
                
                if enabled_tools is None:
                    # No preferences set yet - include all tools (default behavior)
                    logger.info("   ℹ️  No preferences set, including all tools (default behavior)")
                    # NOTE: If user wants to disable web_search by default, they need to set preferences
                elif isinstance(enabled_tools, list):
                    if len(enabled_tools) == 0:
                        # Empty list means user explicitly disabled all tools
                        logger.warning("⚠️  User has empty enabled_tools list - all tools disabled")
                        tools = []
                    else:
                        # Keep only tools explicitly enabled by the user
                        enabled_set = set(enabled_tools)
                        original_count = len(tools)
                        # Log which tools will be filtered out BEFORE filtering
                        all_tool_names = [t.get("name") for t in tools]
                        filtered_out = [name for name in all_tool_names if name not in enabled_set]
                        tools = [t for t in tools if t.get("name") in enabled_set]
                        filtered_count = len(tools)
                        logger.info(f"🔒 Filtered tools by user preferences: {original_count} -> {filtered_count} (enabled: {len(enabled_set)})")
                        if filtered_out:
                            logger.info(f"   Filtered out: {', '.join(filtered_out[:10])}{'...' if len(filtered_out) > 10 else ''}")
                        # Verify web_search and web_fetch are filtered if not in enabled_set
                        if "web_search" in filtered_out:
                            logger.warning("   🚫 web_search correctly filtered out - should NOT be available to Ollama")
                        elif "web_search" in enabled_set:
                            logger.info("   ✅ web_search is enabled by user")
                        if "web_fetch" in filtered_out:
                            logger.warning("   🚫 web_fetch correctly filtered out - should NOT be available to Ollama")
                        elif "web_fetch" in enabled_set:
                            logger.info("   ✅ web_fetch is enabled by user")
                else:
                    # Invalid type - log warning but include all tools
                    logger.warning(f"⚠️  enabled_tools has invalid type: {type(enabled_tools)}, including all tools")
            except Exception as e:
                # If anything goes wrong, fall back to full set of tools
                logger.warning(f"⚠️  Error filtering tools by user preferences: {e}", exc_info=True)
                pass
        else:
            logger.info("🔍 No current_user provided - including all tools (no filtering)")
        
        # Final check: log which tools are being returned
        final_tool_names = [t.get("name") for t in tools]
        
        # CRITICAL: Double-check that web_search and web_fetch are NOT in the list if user has preferences
        # This is a safety net in case the filtering above didn't work correctly
        if current_user is not None:
            try:
                metadata = getattr(current_user, "user_metadata", {}) or {}
                enabled_tools = metadata.get("enabled_tools")
                if isinstance(enabled_tools, list) and enabled_tools:
                    # User has preferences - explicitly filter out web_search and web_fetch if not enabled
                    enabled_set = set(enabled_tools)
                    if "web_search" in final_tool_names and "web_search" not in enabled_set:
                        logger.error(f"🚨🚨🚨 CRITICAL: web_search found in final list but NOT in enabled_tools! Removing it.")
                        tools = [t for t in tools if t.get("name") != "web_search"]
                        final_tool_names = [t.get("name") for t in tools]
                    if "web_fetch" in final_tool_names and "web_fetch" not in enabled_set:
                        logger.error(f"🚨🚨🚨 CRITICAL: web_fetch found in final list but NOT in enabled_tools! Removing it.")
                        tools = [t for t in tools if t.get("name") != "web_fetch"]
                        final_tool_names = [t.get("name") for t in tools]
            except Exception as e:
                logger.warning(f"⚠️  Error in final web_search check: {e}", exc_info=True)
        
        if "web_search" in final_tool_names:
            logger.error(f"🚨🚨🚨 CRITICAL: web_search is in final tools list! Tools being passed: {final_tool_names[:10]}")
            logger.error(f"🚨 This should NOT happen if user has disabled web_search!")
        else:
            logger.info(f"✅ web_search NOT in final tools list. Tools being passed: {final_tool_names[:10]}")
        
        # Force INFO level logging to ensure it's written
        import sys
        print(f"[TOOL_MANAGER] Returning {len(tools)} tools. web_search in list: {'web_search' in final_tool_names}", file=sys.stderr)

        return tools
    
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
        current_user: Optional["User"] = None,  # type: ignore[name-defined]
    ) -> Dict[str, Any]:
        """Execute a tool by name"""
        import logging
        from app.core.tracing import trace_span, set_trace_attribute, add_trace_event
        from app.core.metrics import increment_counter, observe_histogram
        import time
        
        logger = logging.getLogger(__name__)
        
        if db is None:
            db = self.db
        
        if db is None:
            return {"error": "Database session not available"}
        
        # Check if tool is enabled for this user (before execution)
        # CRITICAL: This is the last line of defense - block tool execution if disabled
        if current_user is not None:
            try:
                metadata = getattr(current_user, "user_metadata", {}) or {}
                enabled_tools = metadata.get("enabled_tools")
                # Only check if user has explicitly set preferences (list, not None)
                if isinstance(enabled_tools, list) and enabled_tools:
                    if tool_name not in enabled_tools:
                        error_msg = f"Tool '{tool_name}' is disabled by user preferences"
                        logger.error(f"🚫🚫🚫 BLOCKED: {error_msg}")
                        logger.error(f"   Enabled tools: {enabled_tools[:10]}{'...' if len(enabled_tools) > 10 else ''}")
                        increment_counter("tool_executions_blocked", labels={"tool": tool_name, "reason": "disabled_by_user"})
                        return {"error": error_msg}
                # If enabled_tools is None, user hasn't set preferences yet - allow all tools (default)
            except Exception as e:
                logger.warning(f"⚠️  Error checking tool permissions: {e}", exc_info=True)
                # Continue execution if check fails (fail open for safety)
        
        logger.info(f"Executing tool: {tool_name} with parameters: {parameters}")
        
        # Start tracing
        start_time = time.time()
        with trace_span(f"tool.execute.{tool_name}", {
            "tool.name": tool_name,
            "tool.session_id": str(session_id) if session_id else None,
            "tool.auto_index": str(auto_index)
        }):
            set_trace_attribute("tool.name", tool_name)
            add_trace_event("tool.execution.started", {"tool": tool_name})
            
            # Increment tool execution counter
            increment_counter("tool_executions_total", labels={"tool": tool_name})
            
            try:
                # Check if it's an MCP tool (prefixed with "mcp_")
                if tool_name.startswith("mcp_"):
                    result = await self._execute_mcp_tool(tool_name, parameters, db, session_id, auto_index)
                    logger.info(f"MCP Tool {tool_name} completed")
                    add_trace_event("tool.execution.completed", {"tool": tool_name, "type": "mcp"})
                    duration = time.time() - start_time
                    observe_histogram("tool_execution_duration_seconds", duration, labels={"tool": tool_name, "type": "mcp"})
                    return result
                elif tool_name == "get_calendar_events":
                    result = await self._execute_get_calendar_events(parameters, db, session_id=session_id)
                    logger.info(f"Tool {tool_name} completed, result type: {type(result)}")
                    add_trace_event("tool.execution.completed", {"tool": tool_name, "type": "calendar"})
                    duration = time.time() - start_time
                    observe_histogram("tool_execution_duration_seconds", duration, labels={"tool": tool_name, "type": "calendar"})
                    return result
                elif tool_name == "get_emails":
                    result = await self._execute_get_emails(parameters, db, session_id=session_id)
                    logger.info(f"Tool {tool_name} completed, emails count: {result.get('count', 0) if isinstance(result, dict) else 'unknown'}")
                    add_trace_event("tool.execution.completed", {"tool": tool_name, "type": "email"})
                    duration = time.time() - start_time
                    observe_histogram("tool_execution_duration_seconds", duration, labels={"tool": tool_name, "type": "email"})
                    return result
                elif tool_name == "summarize_emails":
                    result = await self._execute_summarize_emails(parameters, db, session_id=session_id)
                    logger.info(f"Tool {tool_name} completed, summary length: {len(result.get('summary', '')) if isinstance(result, dict) else 'unknown'}")
                    add_trace_event("tool.execution.completed", {"tool": tool_name, "type": "email"})
                    duration = time.time() - start_time
                    observe_histogram("tool_execution_duration_seconds", duration, labels={"tool": tool_name, "type": "email"})
                    return result
                elif tool_name == "archive_email":
                    result = await self._execute_archive_email(parameters, db, session_id=session_id)
                    logger.info(f"Tool {tool_name} completed, email_id: {parameters.get('email_id', 'unknown')}")
                    add_trace_event("tool.execution.completed", {"tool": tool_name, "type": "email"})
                    duration = time.time() - start_time
                    observe_histogram("tool_execution_duration_seconds", duration, labels={"tool": tool_name, "type": "email"})
                    return result
                elif tool_name == "send_email":
                    result = await self._execute_send_email(parameters, db, session_id=session_id)
                    logger.info(f"Tool {tool_name} completed, to: {parameters.get('to', 'unknown')}")
                    add_trace_event("tool.execution.completed", {"tool": tool_name, "type": "email"})
                    duration = time.time() - start_time
                    observe_histogram("tool_execution_duration_seconds", duration, labels={"tool": tool_name, "type": "email"})
                    return result
                elif tool_name == "reply_to_email":
                    result = await self._execute_reply_to_email(parameters, db, session_id=session_id)
                    logger.info(f"Tool {tool_name} completed, email_id: {parameters.get('email_id', 'unknown')}")
                    add_trace_event("tool.execution.completed", {"tool": tool_name, "type": "email"})
                    duration = time.time() - start_time
                    observe_histogram("tool_execution_duration_seconds", duration, labels={"tool": tool_name, "type": "email"})
                    return result
                elif tool_name == "web_search":
                    result = await self._execute_web_search(parameters, db, session_id, auto_index)
                    logger.info(f"Tool {tool_name} completed")
                    add_trace_event("tool.execution.completed", {"tool": tool_name, "type": "web"})
                    duration = time.time() - start_time
                    observe_histogram("tool_execution_duration_seconds", duration, labels={"tool": tool_name, "type": "web"})
                    return result
                elif tool_name == "web_fetch":
                    result = await self._execute_web_fetch(parameters, db, session_id, auto_index)
                    logger.info(f"Tool {tool_name} completed")
                    add_trace_event("tool.execution.completed", {"tool": tool_name, "type": "web"})
                    duration = time.time() - start_time
                    observe_histogram("tool_execution_duration_seconds", duration, labels={"tool": tool_name, "type": "web"})
                    return result
                # WhatsApp tools temporarily disabled - will be re-enabled with Business API
                # elif tool_name == "get_whatsapp_messages":
                #     result = await self._execute_get_whatsapp_messages(parameters)
                #     logger.info(f"Tool {tool_name} completed")
                #     return result
                # elif tool_name == "send_whatsapp_message":
                #     result = await self._execute_send_whatsapp_message(parameters)
                #     logger.info(f"Tool {tool_name} completed")
                #     return result
                else:
                    logger.error(f"Unknown tool: {tool_name}")
                    add_trace_event("tool.execution.error", {"tool": tool_name, "error": "not_found"})
                    increment_counter("tool_executions_errors_total", labels={"tool": tool_name, "error": "not_found"})
                    return {"error": f"Tool '{tool_name}' not found"}
            except Exception as e:
                logger.error(f"Exception in tool execution {tool_name}: {e}", exc_info=True)
                add_trace_event("tool.execution.error", {"tool": tool_name, "error": str(e)})
                duration = time.time() - start_time
                observe_histogram("tool_execution_duration_seconds", duration, labels={"tool": tool_name, "error": "true"})
                increment_counter("tool_executions_errors_total", labels={"tool": tool_name, "error_type": type(e).__name__})
                return {"error": str(e)}
    
    async def _execute_get_calendar_events(
        self,
        parameters: Dict[str, Any],
        db: AsyncSession,
        session_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Execute get_calendar_events tool"""
        from app.models.database import Integration
        from app.api.integrations.calendars import _decrypt_credentials
        from sqlalchemy import select
        from datetime import datetime, timezone, timedelta
        
        try:
            # Get calendar integration for the session's user (or global)
            if not session_id:
                return {"error": "Session ID is required to resolve calendar integration"}

            # Get session to know tenant and user
            session_result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            session = session_result.scalar_one_or_none()
            if not session:
                return {"error": "Session not found"}

            tenant_id = session.tenant_id
            user_id = session.user_id

            query = (
                select(Integration)
                .where(Integration.provider == "google")
                .where(Integration.service_type == "calendar")
                .where(Integration.enabled == True)
                .where(Integration.tenant_id == tenant_id)
            )
            from sqlalchemy import or_
            if user_id is not None:
                query = query.where(or_(Integration.user_id == user_id, Integration.user_id.is_(None)))

            result = await db.execute(query.limit(1))
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
        except IntegrationAuthError as exc:
            return {
                "error": (
                    "Autorizzazione Gmail scaduta o revocata. "
                    "Ricollega l'integrazione email e riprova."
                ),
                "provider": exc.provider,
                "reason": exc.reason,
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
            # Get email integration for the session's user (or global)
            if not session_id:
                return {"error": "Session ID is required to resolve email integration"}

            # Get session to know tenant and user
            session_result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            session = session_result.scalar_one_or_none()
            if not session:
                return {"error": "Session not found"}

            tenant_id = session.tenant_id
            user_id = session.user_id

            query = (
                select(Integration)
                .where(Integration.provider == "google")
                .where(Integration.service_type == "email")
                .where(Integration.enabled == True)
                .where(Integration.tenant_id == tenant_id)
            )
            from sqlalchemy import or_
            if user_id is not None:
                query = query.where(or_(Integration.user_id == user_id, Integration.user_id.is_(None)))

            result = await db.execute(query.limit(1))
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
            include_body = parameters.get("include_body", True)  # Default to True for reading emails
            
            import logging
            logger = logging.getLogger(__name__)
            logger.info(
                f"📧 get_emails called: query={gmail_query}, max_results={max_results}, include_body={include_body}"
            )
            
            emails = await self.email_service.get_gmail_messages(
                max_results=max_results,
                query=gmail_query,
                integration_id=str(integration.id),
                include_body=include_body,
            )
            
            logger.info(f"📧 Retrieved {len(emails) if emails else 0} emails")
            
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
    
    def _normalize_google_maps_parameters(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Google Maps tool parameters to match expected format"""
        import logging
        logger = logging.getLogger(__name__)
        
        normalized = dict(parameters)
        
        # Normalize travelMode for directions and distance_matrix tools
        if "maps" in tool_name.lower() and "travelMode" in normalized:
            travel_mode = normalized["travelMode"]
            if isinstance(travel_mode, str):
                # Convert common variations to uppercase format expected by Google Maps API
                mode_mapping = {
                    "driving": "DRIVE",
                    "walking": "WALK",
                    "bicycling": "BICYCLE",
                    "transit": "TRANSIT",
                    "drive": "DRIVE",
                    "walk": "WALK",
                    "bicycle": "BICYCLE",
                }
                normalized["travelMode"] = mode_mapping.get(travel_mode.lower(), travel_mode.upper())
                if normalized["travelMode"] != travel_mode:
                    logger.info(f"   Normalized travelMode: '{travel_mode}' -> '{normalized['travelMode']}'")
        
        return normalized

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
        logger.info(f"   Parameters (original): {parameters}")
        
        # Normalize parameters for Google Maps tools
        if "maps" in tool_name.lower():
            parameters = self._normalize_google_maps_parameters(tool_name, parameters)
            logger.info(f"   Parameters (normalized): {parameters}")
        
        # Find the MCP integration that provides this tool
        result = await db.execute(
            select(Integration)
            .where(Integration.service_type == "mcp_server")
            .where(Integration.enabled == True)
        )
        integrations = result.scalars().all()
        
        logger.info(f"   Found {len(integrations)} enabled MCP integration(s)")
        
        for integration in integrations:
            session_metadata = integration.session_metadata or {}
            server_url = session_metadata.get("server_url", "")
            
            logger.info(f"   Integration {integration.id}:")
            logger.info(f"     Server URL: {server_url}")
            logger.info(f"     Looking for tool: '{actual_tool_name}'")
            
            # Get MCP client and list all available tools from this integration
            integration_key = str(integration.id)
            if integration_key not in self._mcp_clients_cache:
                if server_url:
                    logger.info(f"   Creating new MCP client with URL: {server_url}")
                    self._mcp_clients_cache[integration_key] = MCPClient(base_url=server_url)
                else:
                    logger.warning(f"   No server_url in integration, using default from settings")
                    self._mcp_clients_cache[integration_key] = MCPClient()
            
            client = self._mcp_clients_cache[integration_key]
            
            # List all tools from this integration to check if the tool exists
            try:
                all_tools = await client.list_tools()
                tool_names = [t.get("name", "") if isinstance(t, dict) else getattr(t, "name", "") for t in all_tools]
                logger.info(f"     Available tools from this integration: {len(tool_names)}")
                logger.info(f"     Tool names: {tool_names[:10]}{'...' if len(tool_names) > 10 else ''}")
                
                if actual_tool_name in tool_names:
                    logger.info(f"   ✅ Tool '{actual_tool_name}' found in integration {integration.id}")
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
                                await asyncio.sleep(0.2)  # Small delay to ensure the previous operation is complete
                                await client.call_tool("browser_close", {})
                                logger.info(f"   🧹 Browser session closed after {actual_tool_name}")
                            except Exception as close_error:
                                # Log warning if browser_close fails - this can lead to orphaned containers
                                logger.warning(f"   ⚠️  Could not close browser session after {actual_tool_name}: {close_error}. Container may remain running.")
                                # Try alternative cleanup: check if there's a browser_close_all or similar tool
                                try:
                                    # Some MCP servers might have a different cleanup method
                                    await client.call_tool("browser_close_all", {})
                                    logger.info(f"   🧹 Browser session closed via browser_close_all")
                                except Exception:
                                    pass  # Ignore if this also fails
                        
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
                    logger.info(f"   ⚠️ Tool '{actual_tool_name}' NOT found in integration {integration.id}")
            except Exception as e:
                logger.error(f"   ❌ Error listing tools from integration {integration.id}: {e}", exc_info=True)
                # Continue to next integration
                continue
        
        logger.error(f"❌ MCP tool '{actual_tool_name}' not found in any enabled integration")
        return {"error": f"MCP tool '{actual_tool_name}' not found in any enabled integration"}
    
    async def _execute_summarize_emails(
        self,
        parameters: Dict[str, Any],
        db: AsyncSession,
        session_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Execute summarize_emails tool"""
        from app.models.database import Integration
        from app.api.integrations.emails import _decrypt_credentials
        from app.core.ollama_client import OllamaClient
        from sqlalchemy import select
        
        try:
            # Get email integration for the session's user (or global)
            if not session_id:
                return {"error": "Session ID is required to resolve email integration"}

            # Get session to know tenant and user
            session_result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            session = session_result.scalar_one_or_none()
            if not session:
                return {"error": "Session not found"}

            tenant_id = session.tenant_id
            user_id = session.user_id

            query = (
                select(Integration)
                .where(Integration.provider == "google")
                .where(Integration.service_type == "email")
                .where(Integration.enabled == True)
                .where(Integration.tenant_id == tenant_id)
            )
            from sqlalchemy import or_
            if user_id is not None:
                query = query.where(or_(Integration.user_id == user_id, Integration.user_id.is_(None)))

            result = await db.execute(query.limit(1))
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
    
    async def _execute_archive_email(
        self,
        parameters: Dict[str, Any],
        db: AsyncSession,
        session_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Execute archive_email tool"""
        import logging
        logger = logging.getLogger(__name__)
        from app.models.database import Integration
        from app.api.integrations.emails import _decrypt_credentials
        from app.services.exceptions import IntegrationAuthError
        from sqlalchemy import select, or_
        
        try:
            email_id = parameters.get("email_id")
            if not email_id:
                return {"error": "email_id is required"}
            
            # Get email integration for the session's user (or global)
            if not session_id:
                return {"error": "Session ID is required to resolve email integration"}

            # Get session to know tenant and user
            session_result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            session = session_result.scalar_one_or_none()
            if not session:
                return {"error": "Session not found"}

            tenant_id = session.tenant_id
            user_id = session.user_id

            query = (
                select(Integration)
                .where(Integration.provider == "google")
                .where(Integration.service_type == "email")
                .where(Integration.enabled == True)
                .where(Integration.tenant_id == tenant_id)
            )
            if user_id is not None:
                query = query.where(or_(Integration.user_id == user_id, Integration.user_id.is_(None)))

            result = await db.execute(query.limit(1))
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
            
            # Archive email
            success = await self.email_service.archive_email(
                email_id=email_id,
                integration_id=str(integration.id),
            )
            
            if success:
                return {"success": True, "message": f"Email {email_id} archiviata con successo"}
            else:
                return {"error": "Errore durante l'archiviazione dell'email"}
        except IntegrationAuthError as auth_error:
            logger.error(f"Authorization error in archive_email: {auth_error}")
            # Return a user-friendly error message
            error_msg = str(auth_error)
            if "insufficient" in error_msg.lower() or "scope" in error_msg.lower() or "permission" in error_msg.lower():
                return {"error": "Permessi Gmail insufficienti. Per favore riconnetti l'integrazione Gmail per ottenere i permessi necessari per archiviare email."}
            return {"error": f"Errore di autorizzazione Gmail: {auth_error.reason}"}
        except Exception as e:
            logger.error(f"Error in archive_email: {e}", exc_info=True)
            # Extract a clean error message without stack traces
            error_msg = str(e)
            # Remove Python traceback info if present
            if "Traceback" in error_msg or "File \"" in error_msg:
                # Try to extract just the error message
                lines = error_msg.split('\n')
                for line in reversed(lines):
                    if line.strip() and not line.strip().startswith('File') and not line.strip().startswith('Traceback'):
                        error_msg = line.strip()
                        break
            return {"error": f"Errore durante l'archiviazione dell'email: {error_msg}"}
    
    async def _execute_send_email(
        self,
        parameters: Dict[str, Any],
        db: AsyncSession,
        session_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Execute send_email tool"""
        import logging
        logger = logging.getLogger(__name__)
        from app.models.database import Integration
        from app.api.integrations.emails import _decrypt_credentials
        from app.services.exceptions import IntegrationAuthError
        from sqlalchemy import select, or_
        
        try:
            to = parameters.get("to")
            subject = parameters.get("subject")
            body = parameters.get("body")
            body_html = parameters.get("body_html")
            
            if not to or not subject or not body:
                return {"error": "to, subject, and body are required"}
            
            # Get email integration for the session's user (or global)
            if not session_id:
                return {"error": "Session ID is required to resolve email integration"}

            # Get session to know tenant and user
            session_result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            session = session_result.scalar_one_or_none()
            if not session:
                return {"error": "Session not found"}

            tenant_id = session.tenant_id
            user_id = session.user_id

            query = (
                select(Integration)
                .where(Integration.provider == "google")
                .where(Integration.service_type == "email")
                .where(Integration.enabled == True)
                .where(Integration.tenant_id == tenant_id)
            )
            if user_id is not None:
                query = query.where(or_(Integration.user_id == user_id, Integration.user_id.is_(None)))

            result = await db.execute(query.limit(1))
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
            
            # Send email
            result = await self.email_service.send_email(
                to=to,
                subject=subject,
                body=body,
                body_html=body_html,
                integration_id=str(integration.id),
            )
            
            if result.get("success"):
                # Track sent email thread_id in session metadata for reply detection
                thread_id = result.get("thread_id")
                message_id = result.get("message_id")
                if session_id and thread_id:
                    try:
                        # SessionModel is already imported globally, no need to import again
                        session_result = await db.execute(
                            select(SessionModel).where(SessionModel.id == session_id)
                        )
                        session = session_result.scalar_one_or_none()
                        if session:
                            # Initialize sent_email_threads if not exists
                            if not session.session_metadata:
                                session.session_metadata = {}
                            if "sent_email_threads" not in session.session_metadata:
                                session.session_metadata["sent_email_threads"] = []
                            
                            # Add thread_id if not already present
                            if thread_id not in session.session_metadata["sent_email_threads"]:
                                session.session_metadata["sent_email_threads"].append(thread_id)
                                await db.commit()
                                logger.info(f"📧 Tracked sent email thread_id {thread_id} in session {session_id}")
                    except Exception as e:
                        logger.warning(f"Failed to track sent email thread_id: {e}")
                
                return {
                    "success": True,
                    "message": f"Email inviata con successo a {to}",
                    "message_id": message_id,
                    "thread_id": thread_id,
                }
            else:
                return {"error": "Errore durante l'invio dell'email"}
        except IntegrationAuthError as auth_error:
            logger.error(f"Authorization error in send_email: {auth_error}")
            # Return a user-friendly error message
            error_msg = str(auth_error)
            if "insufficient" in error_msg.lower() or "scope" in error_msg.lower() or "permission" in error_msg.lower():
                return {"error": "Permessi Gmail insufficienti. Per favore riconnetti l'integrazione Gmail per ottenere i permessi necessari per inviare email."}
            return {"error": f"Errore di autorizzazione Gmail: {auth_error.reason}"}
        except Exception as e:
            logger.error(f"Error in send_email: {e}", exc_info=True)
            # Extract a clean error message without stack traces
            error_msg = str(e)
            # Remove Python traceback info if present
            if "Traceback" in error_msg or "File \"" in error_msg:
                # Try to extract just the error message
                lines = error_msg.split('\n')
                for line in reversed(lines):
                    if line.strip() and not line.strip().startswith('File') and not line.strip().startswith('Traceback'):
                        error_msg = line.strip()
                        break
            return {"error": f"Errore durante l'invio dell'email: {error_msg}"}
    
    async def _execute_reply_to_email(
        self,
        parameters: Dict[str, Any],
        db: AsyncSession,
        session_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Execute reply_to_email tool"""
        import logging
        logger = logging.getLogger(__name__)
        from app.models.database import Integration
        from app.api.integrations.emails import _decrypt_credentials
        from sqlalchemy import select, or_
        
        try:
            email_id = parameters.get("email_id")
            body = parameters.get("body")
            body_html = parameters.get("body_html")
            
            if not email_id or not body:
                return {"error": "email_id and body are required"}
            
            # Get email integration for the session's user (or global)
            if not session_id:
                return {"error": "Session ID is required to resolve email integration"}

            # Get session to know tenant and user
            session_result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            session = session_result.scalar_one_or_none()
            if not session:
                return {"error": "Session not found"}

            tenant_id = session.tenant_id
            user_id = session.user_id

            query = (
                select(Integration)
                .where(Integration.provider == "google")
                .where(Integration.service_type == "email")
                .where(Integration.enabled == True)
                .where(Integration.tenant_id == tenant_id)
            )
            if user_id is not None:
                query = query.where(or_(Integration.user_id == user_id, Integration.user_id.is_(None)))

            result = await db.execute(query.limit(1))
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
            
            # Reply to email
            result = await self.email_service.reply_to_email(
                email_id=email_id,
                body=body,
                body_html=body_html,
                integration_id=str(integration.id),
            )
            
            if result.get("success"):
                # Track replied email thread_id in session metadata for reply detection
                thread_id = result.get("thread_id")
                message_id = result.get("message_id")
                if session_id and thread_id:
                    try:
                        # SessionModel is already imported globally, no need to import again
                        session_result = await db.execute(
                            select(SessionModel).where(SessionModel.id == session_id)
                        )
                        session = session_result.scalar_one_or_none()
                        if session:
                            # Initialize sent_email_threads if not exists
                            if not session.session_metadata:
                                session.session_metadata = {}
                            if "sent_email_threads" not in session.session_metadata:
                                session.session_metadata["sent_email_threads"] = []
                            
                            # Add thread_id if not already present
                            if thread_id not in session.session_metadata["sent_email_threads"]:
                                session.session_metadata["sent_email_threads"].append(thread_id)
                                await db.commit()
                                logger.info(f"📧 Tracked replied email thread_id {thread_id} in session {session_id}")
                    except Exception as e:
                        logger.warning(f"Failed to track replied email thread_id: {e}")
                
                return {
                    "success": True,
                    "message": f"Risposta inviata con successo",
                    "message_id": message_id,
                    "thread_id": thread_id,
                }
            else:
                return {"error": "Errore durante l'invio della risposta"}
        except IntegrationAuthError as auth_error:
            logger.error(f"Authorization error in reply_to_email: {auth_error}")
            # Return a user-friendly error message
            error_msg = str(auth_error)
            if "insufficient" in error_msg.lower() or "scope" in error_msg.lower() or "permission" in error_msg.lower():
                return {"error": "Permessi Gmail insufficienti. Per favore riconnetti l'integrazione Gmail per ottenere i permessi necessari per inviare email."}
            return {"error": f"Errore di autorizzazione Gmail: {auth_error.reason}"}
        except Exception as e:
            logger.error(f"Error in reply_to_email: {e}", exc_info=True)
            # Extract a clean error message without stack traces
            error_msg = str(e)
            # Remove Python traceback info if present
            if "Traceback" in error_msg or "File \"" in error_msg:
                # Try to extract just the error message
                lines = error_msg.split('\n')
                for line in reversed(lines):
                    if line.strip() and not line.strip().startswith('File') and not line.strip().startswith('Traceback'):
                        error_msg = line.strip()
                        break
            return {"error": f"Errore durante l'invio della risposta: {error_msg}"}
    
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
                        # SessionModel is already imported globally, no need to import again
                        
                        # Get tenant_id from session
                        session_result = await db.execute(
                            select(SessionModel.tenant_id).where(SessionModel.id == session_id)
                        )
                        tenant_id = session_result.scalar_one_or_none()
                        
                        # Initialize memory manager if not already done
                        init_clients()
                        memory_manager = get_memory_manager()
                        web_indexer = WebIndexer(memory_manager)
                        index_stats = await web_indexer.index_web_search_results(
                            db=db,
                            search_query=query,
                            results=serializable_results,
                            session_id=session_id,
                            tenant_id=tenant_id,
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
                        
                        # Get tenant_id from session
                        # SessionModel is already imported globally, no need to import again
                        session_result = await db.execute(
                            select(SessionModel.tenant_id).where(SessionModel.id == session_id)
                        )
                        tenant_id = session_result.scalar_one_or_none()
                        
                        # Initialize memory manager if not already done
                        init_clients()
                        memory_manager = get_memory_manager()
                        web_indexer = WebIndexer(memory_manager)
                        indexed = await web_indexer.index_web_fetch_result(
                            db=db,
                            url=url,
                            result=result_dict["result"],
                            session_id=session_id,
                            tenant_id=tenant_id,
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
    
    async def _ensure_whatsapp_connected(self) -> tuple:
        """
        Legacy placeholder retained for backward compatibility. The Selenium-based
        WhatsApp integration has been removed in favor of a future Business API flow.
        """
        raise RuntimeError(
            "WhatsApp Web integration has been removed. Please configure the Business API integration instead."
        )
    
    async def _execute_get_whatsapp_messages(
        self,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Legacy placeholder for removed WhatsApp Web integration."""
        return {
            "error": "Il tool get_whatsapp_messages non è più disponibile. L'integrazione WhatsApp verrà reintrodotta con le Business API."
        }
    
    async def _execute_send_whatsapp_message(
        self,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Legacy placeholder for removed WhatsApp Web integration."""
        return {
            "error": "Il tool send_whatsapp_message non è più disponibile. L'integrazione WhatsApp verrà reintrodotta con le Business API."
        }

