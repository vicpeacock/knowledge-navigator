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
    ollama_background_base_url: str = "http://localhost:11435"
    ollama_background_model: str = "phi3:mini"  # Modello piccolo ed efficiente per background tasks

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

