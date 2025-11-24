from pydantic_settings import BaseSettings
from pydantic import ConfigDict, field_validator
from typing import Optional, List
import os
from pathlib import Path

# Find project root (where .env file is located)
# Go up from backend/app/core/config.py to find project root
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=str(_ENV_FILE) if _ENV_FILE.exists() else ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        # Give priority to .env file over environment variables
        # This ensures that .env file values are used even if env vars are set
        return (
            init_settings,
            dotenv_settings,  # .env file first
            env_settings,     # Then environment variables
            file_secret_settings,
        )
    
    def model_post_init(self, __context):
        """Load API keys from environment if not set, supporting both naming conventions"""
        import os
        # Support both GOOGLE_PSE_* and GOOGLE_CSE_* naming conventions
        if not self.google_pse_api_key:
            self.google_pse_api_key = os.getenv("GOOGLE_PSE_API_KEY") or os.getenv("GOOGLE_CSE_API_KEY")
        if not self.google_pse_cx:
            self.google_pse_cx = os.getenv("GOOGLE_PSE_CX") or os.getenv("GOOGLE_CSE_CX")
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
    # ChromaDB Cloud (for cloud deployment only)
    chromadb_cloud_api_key: Optional[str] = None  # API key for ChromaDB Cloud
    chromadb_cloud_tenant: Optional[str] = None  # Tenant ID for ChromaDB Cloud
    chromadb_cloud_database: Optional[str] = None  # Database name for ChromaDB Cloud
    chromadb_use_cloud: bool = False  # Set to True to use ChromaDB Cloud instead of HttpClient

    # LLM Provider Selection
    llm_provider: str = "ollama"  # Options: "ollama", "gemini"

    # Gemini Configuration (for cloud deployment)
    gemini_api_key: Optional[str] = None  # Google AI Studio API key
    gemini_model: str = "gemini-2.5-flash"  # Main model for chat (gemini-2.5-flash is fast and available)
    gemini_background_model: Optional[str] = None  # Background model (if None, uses gemini_model)
    gemini_planner_model: Optional[str] = None  # Planner model (if None, uses gemini_model)

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
    # IMPORTANTE: Il planner usa lo stesso LLM principale come default per garantire coerenza
    # Se si vuole un planner più leggero, configurare esplicitamente ollama_planner_base_url e ollama_planner_model
    ollama_planner_base_url: Optional[str] = None  # Se None, usa ollama_base_url (LLM principale)
    ollama_planner_model: Optional[str] = None  # Se None, usa ollama_model (LLM principale)

    # MCP Gateway (default, can be overridden per integration)
    # Default: localhost:8080 (if backend runs on host)
    # Use host.docker.internal:8080 if backend runs inside Docker
    # Users can override this when connecting via the UI
    mcp_gateway_url: str = "http://localhost:8080"  # Docker MCP Gateway default port
    # Optional Bearer token for MCP Gateway (if it requires auth)
    mcp_gateway_auth_token: Optional[str] = None
    
    # Google OAuth Configuration
    google_oauth_client_id: Optional[str] = None
    google_oauth_client_secret: Optional[str] = None
    # OAuth scopes for Google Workspace MCP
    google_workspace_oauth_scopes: List[str] = [
        "openid",  # Required for ID token
        "email",   # Required for user email in ID token
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/documents.readonly",
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/tasks.readonly",
    ]

    # Security
    secret_key: str = "your-secret-key-change-in-production"
    encryption_key: str = "your-32-byte-encryption-key"
    jwt_secret_key: str = "your-jwt-secret-key-change-in-production"  # Per JWT tokens
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15  # 15 minuti
    jwt_refresh_token_expire_days: int = 7  # 7 giorni

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
    integrity_confidence_threshold: float = 0.85  # Soglia confidenza contraddizioni (aumentata per ridurre falsi positivi)
    integrity_max_similar_memories: int = 5  # Numero memorie simili da controllare (ridotto per efficienza e precisione)
    integrity_check_exhaustive: bool = False  # Se True, controlla tutte (più lento)
    integrity_min_importance: float = 0.7  # Importanza minima delle memorie da controllare (filtra memorie poco importanti)
    
    # Feature flags
    use_langgraph_prototype: bool = True  # Enable LangGraph by default for proper agent telemetry
    
    # Google OAuth2 (for Calendar/Email)
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri_calendar: str = "http://localhost:8000/api/integrations/calendars/oauth/callback"
    google_redirect_uri_email: str = "http://localhost:8000/api/integrations/emails/oauth/callback"
    
    # Google OAuth2 (for Google Workspace MCP Server)
    # These are the application credentials (shared) - each user authenticates separately with their own Google account
    google_oauth_client_id: Optional[str] = None
    google_oauth_client_secret: Optional[str] = None
    
    # Google Maps API Key (for MCP Gateway)
    google_maps_api_key: Optional[str] = None
    
    # Google Custom Search Engine (for web search with Gemini)
    # Support both GOOGLE_PSE_API_KEY and GOOGLE_CSE_API_KEY (CSE = Custom Search Engine, PSE = Programmable Search Engine)
    google_pse_api_key: Optional[str] = None  # Google Programmable Search Engine API key
    google_pse_cx: Optional[str] = None  # Custom Search Engine ID
    
    def model_post_init(self, __context):
        """Load API keys from environment if not set, supporting both naming conventions"""
        import os
        import logging
        logger = logging.getLogger(__name__)
        
        if not self.google_pse_api_key:
            self.google_pse_api_key = os.getenv("GOOGLE_PSE_API_KEY") or os.getenv("GOOGLE_CSE_API_KEY")
            if self.google_pse_api_key:
                logger.info(f"✅ Loaded Google Custom Search API key (length: {len(self.google_pse_api_key)})")
            else:
                logger.warning("⚠️  GOOGLE_PSE_API_KEY and GOOGLE_CSE_API_KEY not found in environment")
        else:
            logger.info(f"✅ Google Custom Search API key already set (length: {len(self.google_pse_api_key)})")
        
        if not self.google_pse_cx:
            self.google_pse_cx = os.getenv("GOOGLE_PSE_CX") or os.getenv("GOOGLE_CSE_CX")
            if self.google_pse_cx:
                logger.info(f"✅ Loaded Google Custom Search CX: {self.google_pse_cx[:10]}...")
            else:
                logger.warning("⚠️  GOOGLE_PSE_CX and GOOGLE_CSE_CX not found in environment")
        else:
            logger.info(f"✅ Google Custom Search CX already set: {self.google_pse_cx[:10]}...")
    
    # Email sending (SMTP) - for invitation emails, password reset, etc.
    smtp_enabled: bool = False  # Set to True to enable email sending
    smtp_host: Optional[str] = None  # e.g., "smtp.gmail.com"
    smtp_port: int = 587  # 587 for TLS, 465 for SSL
    smtp_use_tls: bool = True  # Use TLS (True) or SSL (False)
    smtp_username: Optional[str] = None  # SMTP username (usually email)
    smtp_password: Optional[str] = None  # SMTP password or app password
    smtp_from_email: Optional[str] = None  # From email address
    smtp_from_name: Optional[str] = "Knowledge Navigator"  # From name
    
    # Frontend URL (for email links)
    frontend_url: str = "http://localhost:3003"
    base_url: str = "http://localhost:8000"  # Backend base URL for OAuth redirects
    
    # HuggingFace (for embedding models)
    huggingface_token: Optional[str] = None  # Optional token to avoid rate limits
    
    # Encryption for credentials
    credentials_encryption_key: str = "your-32-byte-encryption-key-change-me"

    # Service health monitoring
    service_health_monitor_enabled: bool = True
    service_health_check_interval_seconds: int = 60
    agent_scheduler_tick_seconds: int = 30
    integrity_scheduler_interval_seconds: int = 30  # Temporaneamente ridotto per test

    # Proactivity / Event Monitoring
    event_monitor_enabled: bool = True  # Enable proactive event monitoring
    event_monitor_poll_interval_seconds: int = 60  # Check for events every minute
    email_poller_enabled: bool = True  # Enable email polling
    calendar_watcher_enabled: bool = True  # Enable calendar watching
    
    # Email Intelligent Analysis
    email_analysis_enabled: bool = True  # Enable intelligent email analysis
    email_analysis_llm_model: Optional[str] = None  # Model for analysis (None = use default)
    email_analysis_auto_session_enabled: bool = True  # Auto-create sessions for actionable emails
    email_analysis_min_urgency_for_session: str = "medium"  # Only create sessions for medium+ urgency
    email_analysis_learn_from_responses: bool = True  # Update memory from user responses


settings = Settings()

# Create upload directory if it doesn't exist
settings.upload_dir.mkdir(parents=True, exist_ok=True)

# Populate planner defaults dinamically
# Planner should use main LLM (Ollama) as default, not background LLM
if settings.ollama_planner_base_url is None:
    settings.ollama_planner_base_url = settings.ollama_base_url
if settings.ollama_planner_model is None:
    settings.ollama_planner_model = settings.ollama_model

