"""Dependency functions for FastAPI"""
import logging

from app.core.config import settings
from app.core.mcp_client import MCPClient
from app.core.memory_manager import MemoryManager
from app.core.ollama_client import OllamaClient
from app.services.agent_activity_stream import AgentActivityStream
from app.services.background_task_manager import BackgroundTaskManager

# Global instances
_ollama_client: OllamaClient = None
_planner_client: OllamaClient = None
_mcp_client: MCPClient = None
_memory_manager: MemoryManager = None
_agent_activity_stream: AgentActivityStream = None
_background_task_manager: BackgroundTaskManager = None

logger = logging.getLogger(__name__)


def init_clients():
    """Initialize global clients"""
    global _ollama_client, _planner_client, _mcp_client, _memory_manager, _agent_activity_stream, _background_task_manager

    if _ollama_client is None:
        try:
            _ollama_client = OllamaClient()
        except Exception as exc:
            logger.error("Failed to initialize main Ollama client: %s", exc, exc_info=True)
            raise

    if _planner_client is None:
        try:
            _planner_client = OllamaClient(
                base_url=settings.ollama_planner_base_url,
                model=settings.ollama_planner_model,
            )
        except Exception as exc:
            logger.error("Failed to initialize planner client: %s", exc, exc_info=True)
            raise

    if _mcp_client is None:
        try:
            _mcp_client = MCPClient()
        except Exception as exc:
            logger.error("Failed to initialize MCP client: %s", exc, exc_info=True)
            _mcp_client = None

    if _memory_manager is None:
        try:
            _memory_manager = MemoryManager()
        except Exception as exc:
            logger.error("Failed to initialize memory manager: %s", exc, exc_info=True)
            raise

    if _agent_activity_stream is None:
        _agent_activity_stream = AgentActivityStream()

    if _background_task_manager is None:
        _background_task_manager = BackgroundTaskManager()


def get_ollama_client() -> OllamaClient:
    """Get main Ollama client (for chat)"""
    return _ollama_client


def get_planner_client() -> OllamaClient:
    """Get dedicated planner LLM client"""
    return _planner_client


def get_ollama_background_client():
    """Get background LLM client (for background tasks) - can be Ollama or llama.cpp"""
    
    if settings.use_llama_cpp_background:
        from app.core.llama_cpp_client import LlamaCppClient
        return LlamaCppClient(
            base_url=settings.ollama_background_base_url,
            model=settings.ollama_background_model
        )
    else:
        return OllamaClient(
            base_url=settings.ollama_background_base_url,
            model=settings.ollama_background_model
        )


def get_mcp_client() -> MCPClient:
    return _mcp_client


def get_memory_manager() -> MemoryManager:
    return _memory_manager


def get_agent_activity_stream() -> AgentActivityStream:
    return _agent_activity_stream


def get_background_task_manager() -> BackgroundTaskManager:
    return _background_task_manager

