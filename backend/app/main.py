from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.core.config import settings
from app.api import sessions, files, memory, tools, web
from app.api.integrations import calendars, emails, whatsapp
from app.core.dependencies import init_clients, get_ollama_client, get_mcp_client, get_memory_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    # Startup
    init_clients()
    
    yield
    
    # Shutdown
    ollama = get_ollama_client()
    mcp = get_mcp_client()
    if ollama:
        await ollama.close()
    if mcp:
        await mcp.close()


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
app.include_router(calendars.router, prefix="/api/integrations/calendars", tags=["integrations", "calendars"])
app.include_router(emails.router, prefix="/api/integrations/emails", tags=["integrations", "emails"])
app.include_router(whatsapp.router, prefix="/api/integrations/whatsapp", tags=["integrations", "whatsapp"])


@app.get("/")
async def root():
    return {"message": "Knowledge Navigator API", "version": "0.1.0"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


# Dependencies are imported from core.dependencies

