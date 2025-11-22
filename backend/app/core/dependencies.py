"""Dependency functions for FastAPI"""
import logging
from typing import Optional

from app.core.config import settings
from app.core.mcp_client import MCPClient
from app.core.memory_manager import MemoryManager
from app.core.ollama_client import OllamaClient
from app.core.health_check import get_health_check_service
from app.services.agent_activity_stream import AgentActivityStream
from app.services.background_task_manager import BackgroundTaskManager
from app.services.notification_center import NotificationCenter
from app.services.service_health_agent import ServiceHealthAgent
from app.services.task_queue import TaskQueue
from app.services.agent_scheduler import AgentScheduler, ScheduledAgent
from app.services.background_agent import fetch_pending_contradiction_tasks
from app.services.task_dispatcher import TaskDispatcher
from app.services.daily_session_manager import DailySessionManager
from app.db.database import AsyncSessionLocal

# Global instances
# Note: These can be either OllamaClient or GeminiClient depending on llm_provider setting
_ollama_client = None  # Main LLM client (OllamaClient or GeminiClient)
_planner_client = None  # Planner LLM client (OllamaClient or GeminiClient)
_mcp_client: MCPClient = None
_memory_manager: MemoryManager = None
_agent_activity_stream: AgentActivityStream = None
_background_task_manager: BackgroundTaskManager = None
_notification_center: NotificationCenter = None
_service_health_agent: ServiceHealthAgent = None
_task_queue: TaskQueue = None
_agent_scheduler: AgentScheduler = None
_task_dispatcher: TaskDispatcher = None

logger = logging.getLogger(__name__)


def init_clients():
    """Initialize global clients"""
    global _ollama_client
    global _planner_client
    global _mcp_client
    global _memory_manager
    global _agent_activity_stream
    global _background_task_manager
    global _notification_center
    global _service_health_agent
    global _agent_scheduler
    global _task_queue
    global _task_dispatcher

    if _ollama_client is None:
        try:
            if settings.llm_provider == "gemini":
                from app.core.gemini_client import GeminiClient
                logger.info(f"Initializing Gemini client (main): model={settings.gemini_model}")
                _ollama_client = GeminiClient(model=settings.gemini_model)
            else:
                logger.info(f"Initializing Ollama client (main): URL={settings.ollama_base_url}, model={settings.ollama_model}")
                _ollama_client = OllamaClient()
        except Exception as exc:
            logger.error("Failed to initialize main LLM client: %s", exc, exc_info=True)
            raise

    if _planner_client is None:
        try:
            if settings.llm_provider == "gemini":
                from app.core.gemini_client import GeminiClient
                planner_model = settings.gemini_planner_model or settings.gemini_model
                logger.info(f"Initializing Gemini client (planner): model={planner_model}")
                _planner_client = GeminiClient(model=planner_model)
            else:
                # Use planner URL if set, otherwise fallback to background or main Ollama URL
                planner_url = settings.ollama_planner_base_url or settings.ollama_background_base_url or settings.ollama_base_url
                planner_model = settings.ollama_planner_model or settings.ollama_background_model or settings.ollama_model
                
                # Check if planner URL is llama.cpp (11435) or if use_llama_cpp_background is True and planner_url matches background URL
                is_llama_cpp = (
                    "11435" in planner_url or 
                    (settings.use_llama_cpp_background and planner_url == settings.ollama_background_base_url)
                )
                
                if is_llama_cpp:
                    from app.core.llama_cpp_client import LlamaCppClient
                    logger.info(f"Initializing LlamaCpp client (planner): URL={planner_url}, model={planner_model}")
                    _planner_client = LlamaCppClient(
                        base_url=planner_url,
                        model=planner_model,
                    )
                else:
                    logger.info(f"Initializing Ollama client (planner): URL={planner_url}, model={planner_model}")
                    _planner_client = OllamaClient(
                        base_url=planner_url,
                        model=planner_model,
                    )
        except Exception as exc:
            logger.error("Failed to initialize planner LLM client: %s", exc, exc_info=True)
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

    if _notification_center is None:
        _notification_center = NotificationCenter()

    if _task_queue is None:
        _task_queue = TaskQueue()

    if _agent_scheduler is None:
        _agent_scheduler = AgentScheduler(
            task_queue=_task_queue,
            tick_seconds=settings.agent_scheduler_tick_seconds,
            agent_activity_stream=_agent_activity_stream,
        )

        async def integrity_poller():
            return await fetch_pending_contradiction_tasks(_task_queue)

        _agent_scheduler.register_agent(
            ScheduledAgent(
                name="integrity_contradictions",
                interval_seconds=settings.integrity_scheduler_interval_seconds,
                poller=integrity_poller,
            )
        )
        _background_task_manager.configure_agent_scheduler(_agent_scheduler)

    if _task_dispatcher is None:
        _task_dispatcher = TaskDispatcher(
            task_queue=_task_queue,
            background_tasks=_background_task_manager,
            session_factory=AsyncSessionLocal,
            agent_activity_stream=_agent_activity_stream,
            memory_manager=_memory_manager,
            ollama_client=_ollama_client,
            planner_client=_planner_client,
        )
        _agent_scheduler.register_dispatcher(_task_dispatcher)
        
        # Recreate tasks from pending notifications on startup
        async def _recreate_tasks_on_startup():
            try:
                from app.services.background_agent import fetch_pending_contradiction_tasks
                tasks = await fetch_pending_contradiction_tasks(_task_queue)
                if tasks:
                    logger.info(
                        "🔄 Recreated %d contradiction tasks from notifications on startup",
                        len(tasks),
                    )
                    for session_id, task in tasks:
                        _task_queue.enqueue(session_id, task)
                        _task_dispatcher.schedule_dispatch(session_id)
            except Exception as exc:
                logger.warning(
                    "Failed to recreate tasks on startup: %s", exc, exc_info=True
                )
        
        # Schedule task recreation in background
        if _background_task_manager:
            _background_task_manager.schedule_coroutine(
                _recreate_tasks_on_startup(), name="recreate-tasks-on-startup"
            )

    if (
        _service_health_agent is None
        and settings.service_health_monitor_enabled
    ):
        health_checker = get_health_check_service()
        _service_health_agent = ServiceHealthAgent(
            notification_center=_notification_center,
            agent_activity_stream=_agent_activity_stream,
            health_checker=health_checker,
        )
        _background_task_manager.start_service_health_monitor(
            _service_health_agent,
            interval_seconds=settings.service_health_check_interval_seconds,
        )


def get_ollama_client():
    """
    Get main LLM client (for chat)
    
    Returns OllamaClient or GeminiClient depending on llm_provider setting.
    Both implement the same interface, so the return type is compatible.
    """
    return _ollama_client


def get_planner_client():
    """
    Get dedicated planner LLM client
    
    Returns OllamaClient or GeminiClient depending on llm_provider setting.
    Both implement the same interface, so the return type is compatible.
    """
    return _planner_client


def get_ollama_background_client():
    """
    Get background LLM client (for background tasks)
    
    Can be Ollama, llama.cpp, or Gemini depending on configuration.
    All implement the same interface.
    """
    if settings.llm_provider == "gemini":
        from app.core.gemini_client import GeminiClient
        background_model = settings.gemini_background_model or settings.gemini_model
        return GeminiClient(model=background_model)
    elif settings.use_llama_cpp_background:
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


def get_notification_center() -> NotificationCenter:
    return _notification_center


def get_service_health_agent() -> Optional[ServiceHealthAgent]:
    return _service_health_agent


def get_task_queue() -> TaskQueue:
    return _task_queue


def get_task_dispatcher() -> TaskDispatcher:
    return _task_dispatcher


def get_daily_session_manager(db) -> DailySessionManager:
    """Get DailySessionManager instance for managing day-based sessions"""
    return DailySessionManager(
        db=db,
        memory_manager=get_memory_manager(),
        ollama_client=get_ollama_client(),
    )

