from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional
import os
from pathlib import Path


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    # Database
    database_url: str = "postgresql+asyncpg://knavigator:knavigator_pass@localhost:5432/knowledge_navigator"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "knavigator"
    postgres_password: str = "knavigator_pass"
    postgres_db: str = "knowledge_navigator"

    # ChromaDB
    chromadb_host: str = "localhost"
    chromadb_port: int = 8001  # Changed from 8000 to avoid conflict with FastAPI backend

    # Ollama Main (per chat)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gpt-oss:20b"
    ollama_api_key: Optional[str] = None  # API key for Ollama web search (from https://ollama.com)
    
    # Ollama Background (per task in background)
    # Può essere Ollama o llama.cpp (OpenAI-compatible API)
    ollama_background_base_url: str = "http://127.0.0.1:11435"  # Per llama.cpp: aggiungere /v1 automaticamente (usa 127.0.0.1 invece di localhost per evitare problemi IPv6)
    ollama_background_model: str = "Phi-3-mini-4k-instruct-q4"  # Modello llama.cpp (Phi-3-mini quantizzato Q4)
    use_llama_cpp_background: bool = True  # Se True, usa llama.cpp invece di Ollama per background
    require_background_llm: bool = False  # Se True, il background LLM è considerato mandatory

    # Planner LLM (dedicato alla generazione del piano)
    ollama_planner_base_url: Optional[str] = None  # Se None, usa ollama_background_base_url o ollama_base_url
    ollama_planner_model: Optional[str] = None  # Se None, usa ollama_background_model o ollama_model

    # MCP Gateway (default, can be overridden per integration)
    # Default: localhost:8080 (if backend runs on host)
    # Use host.docker.internal:8080 if backend runs inside Docker
    # Users can override this when connecting via the UI
    mcp_gateway_url: str = "http://localhost:8080"  # Docker MCP Gateway default port

    # Security
    secret_key: str = "your-secret-key-change-in-production"
    encryption_key: str = "your-32-byte-encryption-key"

    # File Storage
    upload_dir: Path = Path("./uploads")
    max_file_size: int = 10485760  # 10MB

    # Memory Settings
    short_term_memory_ttl: int = 3600  # 1 hour
    medium_term_memory_days: int = 30
    long_term_importance_threshold: float = 0.7
    
    # Context Management
    max_context_tokens: int = 8000  # Maximum tokens before summarizing
    context_keep_recent_messages: int = 10  # Keep last N messages when summarizing
    
    # Semantic Integrity Check
    integrity_confidence_threshold: float = 0.7  # Soglia confidenza contraddizioni (ridotta da 0.8 per catturare più casi)
    integrity_max_similar_memories: int = 15  # Numero memorie simili da controllare (aumentato da 10)
    integrity_check_exhaustive: bool = False  # Se True, controlla tutte (più lento)
    
    # Feature flags
    use_langgraph_prototype: bool = False
    
    # Google OAuth2 (for Calendar/Email)
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri_calendar: str = "http://localhost:8000/api/integrations/calendars/oauth/callback"
    google_redirect_uri_email: str = "http://localhost:8000/api/integrations/emails/oauth/callback"
    
    # Encryption for credentials
    credentials_encryption_key: str = "your-32-byte-encryption-key-change-me"


settings = Settings()

# Create upload directory if it doesn't exist
settings.upload_dir.mkdir(parents=True, exist_ok=True)

# Populate planner defaults dinamically
if settings.ollama_planner_base_url is None:
    settings.ollama_planner_base_url = (
        settings.ollama_background_base_url or settings.ollama_base_url
    )
if settings.ollama_planner_model is None:
    settings.ollama_planner_model = (
        settings.ollama_background_model or settings.ollama_model
    )

