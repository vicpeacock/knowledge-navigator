from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.api import sessions, files, memory, tools, web, notifications
from app.api.integrations import calendars, emails, whatsapp
from app.core.dependencies import init_clients, get_ollama_client, get_mcp_client, get_memory_manager

# Configure logging
# Log to both console and file
from pathlib import Path
import sys

log_dir = Path("./logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "backend.log"

# Create handlers
console_handler = logging.StreamHandler(sys.stdout)
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)
console_handler.setLevel(logging.INFO)

# Create formatter
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

logging.info(f"Logging to file: {log_file.absolute()}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    # Startup
    logging.info("🚀 Starting Knowledge Navigator backend...")
    
    # Initialize clients
    init_clients()
    
    # Health check all services
    from app.core.health_check import get_health_check_service
    health_service = get_health_check_service()
    health_status = await health_service.check_all_services()
    
    # Log summary
    all_healthy = health_status.get("all_healthy", False)
    
    if all_healthy:
        logging.info("✅ All services are healthy. Backend ready!")
    else:
        logging.warning("⚠️  Some services are not healthy. Check logs above for details.")
        logging.warning("⚠️  Backend will start but some features may not work correctly.")
    
    yield
    
    # Shutdown
    logging.info("🛑 Shutting down Knowledge Navigator backend...")
    ollama = get_ollama_client()
    mcp = get_mcp_client()
    if ollama:
        await ollama.close()
    if mcp:
        await mcp.close()
    logging.info("✅ Shutdown complete")


app = FastAPI(
    title="Knowledge Navigator API",
    description="AI Assistant with multi-level memory and integrations",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3003", "http://localhost:3002", "http://localhost:3000"],  # Next.js frontend
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include routers
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(memory.router, prefix="/api/memory", tags=["memory"])
app.include_router(tools.router, prefix="/api/tools", tags=["tools"])
app.include_router(web.router, prefix="/api/web", tags=["web"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(calendars.router, prefix="/api/integrations/calendars", tags=["integrations", "calendars"])
app.include_router(emails.router, prefix="/api/integrations/emails", tags=["integrations", "emails"])
app.include_router(whatsapp.router, prefix="/api/integrations/whatsapp", tags=["integrations", "whatsapp"])
from app.api.integrations import mcp as mcp_integration
app.include_router(mcp_integration.router, prefix="/api/integrations/mcp", tags=["integrations", "mcp"])


@app.get("/")
async def root():
    return {"message": "Knowledge Navigator API", "version": "0.1.0"}


@app.get("/health")
async def health():
    """Health check endpoint - returns status of all services"""
    from app.core.health_check import get_health_check_service
    health_service = get_health_check_service()
    
    # Get current status (or run check if not done yet)
    if not health_service.health_status:
        await health_service.check_all_services()
    
    summary = health_service.get_status_summary()
    return summary


# Dependencies are imported from core.dependencies

