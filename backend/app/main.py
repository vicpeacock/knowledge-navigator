from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import asyncio
import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.api import sessions, files, memory, tools, web, notifications, apikeys, auth, users
from app.api.integrations import calendars, emails
from app.api import metrics as metrics_api
from app.core.dependencies import init_clients, get_ollama_client, get_mcp_client, get_memory_manager
from app.core.tracing import init_tracing
from app.core.metrics import init_metrics, increment_counter, observe_histogram

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
    
    # Initialize observability (tracing and metrics)
    logging.info("📊 Initializing observability...")
    init_tracing(service_name="knowledge-navigator", enable_console=True)
    init_metrics()
    logging.info("✅ Observability initialized")
    
    # Run database migrations (for Cloud Run deployment)
    logging.info("🔄 Running database migrations...")
    try:
        from alembic.config import Config
        from alembic import command
        from pathlib import Path
        from app.core.config import settings
        
        # Find alembic.ini (it's in backend/ directory)
        backend_dir = Path(__file__).parent.parent
        alembic_ini_path = backend_dir / "alembic.ini"
        
        if not alembic_ini_path.exists():
            # Try current directory (for Cloud Run)
            alembic_ini_path = Path("alembic.ini")
        
        if alembic_ini_path.exists():
            # Run migrations using Alembic
            alembic_cfg = Config(str(alembic_ini_path))
            # Override database URL for Alembic (it needs sync URL)
            alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url.replace("+asyncpg", ""))
            
            # Run migrations
            command.upgrade(alembic_cfg, "head")
            logging.info("✅ Database migrations completed")
        else:
            logging.warning(f"⚠️  alembic.ini not found at {alembic_ini_path}. Skipping migrations.")
    except Exception as e:
        logging.error(f"❌ Failed to run database migrations: {e}", exc_info=True)
        logging.error("⚠️  Database might not be properly initialized. Some features may not work.")
        # Don't fail startup - let the app start and log the error
    
    # Initialize clients
    init_clients()
    
    # Initialize default tenant (for multi-tenancy)
    from app.db.database import get_db
    from app.core.tenant_context import initialize_default_tenant
    try:
        async for db in get_db():
            await initialize_default_tenant(db)
            break
    except Exception as e:
        logging.warning(f"⚠️  Failed to initialize default tenant: {e}")
        logging.warning("⚠️  Multi-tenant features may not work correctly.")
    
    # Check SMTP configuration
    from app.services.email_sender import get_email_sender
    email_sender = get_email_sender()
    if email_sender.is_configured():
        logging.info("✅ SMTP email sending is configured and enabled")
    else:
        logging.info("ℹ️  SMTP email sending is not configured (emails will not be sent)")
    
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
    
    # Start Event Monitor (proactive event monitoring)
    if settings.event_monitor_enabled:
        try:
            from app.services.event_monitor import EventMonitor
            from app.core.dependencies import get_agent_activity_stream
            agent_activity_stream = get_agent_activity_stream()
            event_monitor = EventMonitor(agent_activity_stream=agent_activity_stream)
            await event_monitor.start()
            logging.info("✅ Event Monitor started (proactive email/calendar monitoring)")
        except Exception as e:
            logging.warning(f"⚠️  Failed to start Event Monitor: {e}")
            logging.warning("⚠️  Proactive event monitoring will not be available.")
    else:
        logging.info("ℹ️  Event Monitor disabled (event_monitor_enabled=false)")
    
    yield
    
    # Shutdown
    logging.info("🛑 Shutting down Knowledge Navigator backend...")
    
    # Stop Event Monitor
    if settings.event_monitor_enabled:
        try:
            from app.services.event_monitor import EventMonitor
            event_monitor = EventMonitor()
            await event_monitor.stop()
        except Exception as e:
            logging.warning(f"Error stopping Event Monitor: {e}")
    
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

# Observability middleware for tracing HTTP requests
class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware to trace and measure HTTP requests"""
    
    async def dispatch(self, request: Request, call_next):
        from app.core.tracing import trace_span, set_trace_attribute, get_trace_id
        from app.core.metrics import increment_counter, observe_histogram
        
        # Skip metrics endpoint to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)
        
        start_time = time.time()
        method = request.method
        path = request.url.path
        
        # Get trace ID from frontend if present
        frontend_trace_id = request.headers.get("X-Trace-ID")
        
        # Start trace span
        span_attributes = {
            "http.method": method,
            "http.path": path,
            "http.url": str(request.url),
        }
        if frontend_trace_id:
            span_attributes["frontend.trace_id"] = frontend_trace_id
        
        # Use trace_span but wrap it in try/except to avoid blocking
        try:
            with trace_span(f"{method} {path}", span_attributes):
                set_trace_attribute("http.method", method)
                set_trace_attribute("http.path", path)
                if frontend_trace_id:
                    set_trace_attribute("frontend.trace_id", frontend_trace_id)
                    # Log correlation for debugging
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug(f"Frontend trace ID received: {frontend_trace_id}")
                
                # Increment request counter
                increment_counter("http_requests_total", labels={
                    "method": method,
                    "path": path,
                    "status": "unknown"
                })
                
                try:
                    # Add timeout to prevent infinite blocking in middleware
                    response = await asyncio.wait_for(
                        call_next(request),
                        timeout=600.0  # 10 minutes max - should be enough for chat requests
                    )
                    duration = time.time() - start_time
                    
                    # Record metrics
                    status_code = response.status_code
                    observe_histogram("http_request_duration_seconds", duration, labels={
                        "method": method,
                        "path": path,
                        "status": str(status_code)
                    })
                    
                    increment_counter("http_requests_total", value=1, labels={
                        "method": method,
                        "path": path,
                        "status": str(status_code)
                    })
                    
                    # Add trace ID to response headers
                    trace_id = get_trace_id()
                    if trace_id:
                        response.headers["X-Trace-ID"] = trace_id
                    
                    return response
                except asyncio.TimeoutError:
                    duration = time.time() - start_time
                    logger.error(f"Request timeout after {duration:.2f}s: {method} {path}")
                    observe_histogram("http_request_duration_seconds", duration, labels={
                        "method": method,
                        "path": path,
                        "status": "504"
                    })
                    increment_counter("http_requests_errors_total", labels={
                        "method": method,
                        "path": path,
                        "error_type": "TimeoutError"
                    })
                    from fastapi import HTTPException, status as http_status
                    raise HTTPException(
                        status_code=http_status.HTTP_504_GATEWAY_TIMEOUT,
                        detail=f"Request timed out after {duration:.2f} seconds"
                    )
                except Exception as e:
                    duration = time.time() - start_time
                    status_code = 500
                    
                    # Record error metrics
                    observe_histogram("http_request_duration_seconds", duration, labels={
                        "method": method,
                        "path": path,
                        "status": "500"
                    })
                    
                    increment_counter("http_requests_errors_total", labels={
                        "method": method,
                        "path": path,
                        "error_type": type(e).__name__
                    })
                    
                    raise
        except Exception as trace_error:
            # If tracing fails, continue anyway - don't block requests
            logger = logging.getLogger(__name__)
            logger.warning(f"Tracing error (continuing anyway): {trace_error}")
            try:
                response = await asyncio.wait_for(
                    call_next(request),
                    timeout=600.0
                )
                duration = time.time() - start_time
                status_code = response.status_code
                # Log metrics even if tracing failed
                observe_histogram("http_request_duration_seconds", duration, labels={
                    "method": method,
                    "path": path,
                    "status": str(status_code)
                })
                increment_counter("http_requests_total", value=1, labels={
                    "method": method,
                    "path": path,
                    "status": str(status_code)
                })
                return response
            except asyncio.TimeoutError:
                duration = time.time() - start_time
                logger.error(f"Request timeout after {duration:.2f}s (fallback): {method} {path}")
                observe_histogram("http_request_duration_seconds", duration, labels={
                    "method": method,
                    "path": path,
                    "status": "504"
                })
                increment_counter("http_requests_errors_total", labels={
                    "method": method,
                    "path": path,
                    "error_type": "TimeoutError"
                })
                from fastapi import HTTPException, status as http_status
                raise HTTPException(
                    status_code=http_status.HTTP_504_GATEWAY_TIMEOUT,
                    detail=f"Request timed out after {duration:.2f} seconds (fallback)"
                )
            except Exception as e:
                duration = time.time() - start_time
                status_code = 500
                logger.error(f"Error in request (fallback): {e}", exc_info=True)
                observe_histogram("http_request_duration_seconds", duration, labels={
                    "method": method,
                    "path": path,
                    "status": "500"
                })
                increment_counter("http_requests_errors_total", labels={
                    "method": method,
                    "path": path,
                    "error_type": type(e).__name__
                })
                raise


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3003",  # Frontend locale (dev)
        "http://localhost:3002",  # MCP Gateway
        "http://localhost:3000",  # Frontend locale (alternativo)
        "http://localhost:3004",  # Frontend Docker (test cloud)
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Observability middleware (after CORS)
app.add_middleware(ObservabilityMiddleware)

# Include routers
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(memory.router, prefix="/api/memory", tags=["memory"])
app.include_router(tools.router, prefix="/api/tools", tags=["tools"])
app.include_router(web.router, prefix="/api/web", tags=["web"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(apikeys.router, tags=["apikeys"])
app.include_router(auth.router, tags=["auth"])
app.include_router(users.router, tags=["users"])
app.include_router(calendars.router, prefix="/api/integrations/calendars", tags=["integrations", "calendars"])
app.include_router(emails.router, prefix="/api/integrations/emails", tags=["integrations", "emails"])
from app.api.integrations import mcp as mcp_integration
app.include_router(mcp_integration.router, prefix="/api/integrations/mcp", tags=["integrations", "mcp"])
app.include_router(metrics_api.router, tags=["observability"])


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

