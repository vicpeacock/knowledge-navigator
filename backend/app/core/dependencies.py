"""Dependency functions for FastAPI"""
from app.core.ollama_client import OllamaClient
from app.core.mcp_client import MCPClient
from app.core.memory_manager import MemoryManager

# Global instances
_ollama_client: OllamaClient = None
_mcp_client: MCPClient = None
_memory_manager: MemoryManager = None


def init_clients():
    """Initialize global clients"""
    global _ollama_client, _mcp_client, _memory_manager
    if _ollama_client is None:
        _ollama_client = OllamaClient()
    if _mcp_client is None:
        _mcp_client = MCPClient()
    if _memory_manager is None:
        _memory_manager = MemoryManager()


def get_ollama_client() -> OllamaClient:
    return _ollama_client


def get_mcp_client() -> MCPClient:
    return _mcp_client


def get_memory_manager() -> MemoryManager:
    return _memory_manager

