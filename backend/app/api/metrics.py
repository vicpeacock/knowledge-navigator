"""
Metrics API endpoint for Prometheus scraping and evaluation reports
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import Optional, List
import logging

from app.core.metrics import get_metrics_export
from app.db.database import get_db, AsyncSessionLocal
from app.models.database import Session as SessionModel, User, Tenant
from app.core.user_context import get_current_user, require_admin
from app.core.evaluation import AgentEvaluator
from app.core.dependencies import (
    init_clients,
    get_ollama_client,
    get_memory_manager,
    get_planner_client,
    get_agent_activity_stream,
    get_background_task_manager,
)
from app.agents import run_langgraph_chat
from app.models.schemas import ChatRequest
from tests.evaluation.test_cases import ALL_TEST_CASES, get_test_cases_by_category, get_test_cases_by_id

logger = logging.getLogger(__name__)

router = APIRouter()

# Semaforo per limitare evaluation concurrenti (solo 1 alla volta per evitare sovraccarico)
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any
from enum import Enum

_evaluation_semaphore = asyncio.Semaphore(1)

# Storage per i job di evaluation (in memoria, chiave: user_id)
_evaluation_jobs: Dict[str, Dict[str, Any]] = {}
_evaluation_reports: Dict[str, str] = {}  # HTML reports salvati (chiave: user_id)


class EvaluationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@router.get("/metrics")
async def get_metrics():
    """
    Prometheus metrics endpoint
    Returns metrics in Prometheus format for scraping
    """
    metrics_bytes, content_type = get_metrics_export()
    return Response(content=metrics_bytes, media_type=content_type)


async def run_agent_for_evaluation(
    message: str,
    session_id: UUID,
    db: AsyncSession,
    current_user: Optional[User] = None,
) -> dict:
    """Wrapper function to run agent for evaluation"""
    init_clients()
    ollama = get_ollama_client()
    planner_client = get_planner_client()
    memory_manager = get_memory_manager()
    agent_activity_stream = get_agent_activity_stream()
    
    request = ChatRequest(
        session_id=session_id,
        message=message,
        use_memory=True,
        force_web_search=False,
    )
    
    session_context = []
    retrieved_memory = []
    memory_used = {}
    
    result = await run_langgraph_chat(
        db=db,
        session_id=session_id,
        request=request,
        ollama=ollama,
        planner_client=planner_client,
        agent_activity_stream=agent_activity_stream,
        memory_manager=memory_manager,
        session_context=session_context,
        retrieved_memory=retrieved_memory,
        memory_used=memory_used,
        previous_messages=None,
        pending_plan=None,
        current_user=current_user,
    )
    
    chat_response = result.get("chat_response")
    if chat_response:
        return {
            "response": chat_response.response if hasattr(chat_response, "response") else "",
            "tools_used": chat_response.tools_used if hasattr(chat_response, "tools_used") else [],
            "agent_activity": chat_response.agent_activity if hasattr(chat_response, "agent_activity") else [],
        }
    else:
        return {
            "response": "",
            "tools_used": [],
            "agent_activity": [],
        }


@router.post("/api/v1/evaluation/start")
async def start_evaluation_report(
    category: Optional[str] = Query(None, description="Filter by category"),
    test_ids: Optional[List[str]] = Query(None, description="Specific test IDs to run"),
    parallel: bool = Query(False, description="Run tests in parallel"),
    max_tests: Optional[int] = Query(None, description="Maximum number of test cases to run (default: all)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
    background_task_manager = Depends(get_background_task_manager),
):
    """
    Start async evaluation report generation (admin only)
    Returns job status immediately, report will be generated in background
    """
    user_id_str = str(current_user.id)
    
    # Verifica se c'è già un job in corso per questo utente
    if user_id_str in _evaluation_jobs:
        job = _evaluation_jobs[user_id_str]
        if job["status"] in [EvaluationStatus.PENDING, EvaluationStatus.RUNNING]:
            return {
                "job_id": user_id_str,
                "status": job["status"],
                "message": "Evaluation already in progress",
                "started_at": job["started_at"],
            }
    
    # Get test cases
    if test_ids:
        test_cases = get_test_cases_by_id(test_ids)
    elif category:
        test_cases = get_test_cases_by_category(category)
    else:
        test_cases = ALL_TEST_CASES
    
    # Limit number of test cases if max_tests is specified
    if max_tests and max_tests > 0:
        test_cases = test_cases[:max_tests]
        logger.info(f"Limited to {max_tests} test cases (from {len(ALL_TEST_CASES)} total)")
    
    if not test_cases:
        raise HTTPException(status_code=400, detail="No test cases found")
    
    # Crea job entry
    _evaluation_jobs[user_id_str] = {
        "status": EvaluationStatus.PENDING,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "test_cases_count": len(test_cases),
        "parallel": parallel,
        "error": None,
    }
    
    # Avvia generazione in background
    async def _generate_report():
        try:
            _evaluation_jobs[user_id_str]["status"] = EvaluationStatus.RUNNING
            
            # Get or create evaluation session
            async with AsyncSessionLocal() as db_session:
                # Check if cancelled
                if _evaluation_jobs[user_id_str].get("cancelled"):
                    logger.info(f"Evaluation cancelled for user {user_id_str}")
                    return
                tenant_result = await db_session.execute(select(Tenant).limit(1))
                tenant = tenant_result.scalar_one_or_none()
                if not tenant:
                    raise Exception("No tenant found")
                
                session_result = await db_session.execute(
                    select(SessionModel)
                    .where(SessionModel.tenant_id == tenant.id)
                    .where(SessionModel.name.like("%Evaluation%"))
                    .limit(1)
                )
                session = session_result.scalar_one_or_none()
                
                if not session:
                    session_name = f"Evaluation Session {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    session = SessionModel(
                        tenant_id=tenant.id,
                        name=session_name,
                        title=session_name,
                    )
                    db_session.add(session)
                    await db_session.commit()
                    await db_session.refresh(session)
                
                # Initialize evaluator
                evaluator = AgentEvaluator(
                    run_agent_fn=lambda **kwargs: run_agent_for_evaluation(**kwargs),
                    db_session=db_session,
                    session_id=session.id,
                    current_user=current_user,
                )
                
                # Run evaluation
                async with _evaluation_semaphore:
                    evaluation_timeout = 600.0  # 10 minuti
                    logger.info(f"Starting async evaluation with {len(test_cases)} test cases")
                    
                    # Check cancellation before starting
                    if _evaluation_jobs[user_id_str].get("cancelled"):
                        logger.info(f"Evaluation cancelled before start for user {user_id_str}")
                        return
                    
                    report = await asyncio.wait_for(
                        evaluator.evaluate_test_suite(
                            test_cases=test_cases,
                            parallel=parallel,
                        ),
                        timeout=evaluation_timeout
                    )
                    
                    # Check cancellation after completion
                    if _evaluation_jobs[user_id_str].get("cancelled"):
                        logger.info(f"Evaluation cancelled after completion for user {user_id_str}")
                        return
                    
                    logger.info(f"Evaluation completed successfully in {report.duration_seconds:.2f}s")
                
                # Generate HTML report
                html_report = evaluator.generate_report_html(report)
                
                # Salva report
                _evaluation_reports[user_id_str] = html_report
                _evaluation_jobs[user_id_str]["status"] = EvaluationStatus.COMPLETED
                _evaluation_jobs[user_id_str]["completed_at"] = datetime.now(timezone.utc).isoformat()
                
        except asyncio.TimeoutError:
            logger.error(f"Evaluation timeout for user {user_id_str}")
            _evaluation_jobs[user_id_str]["status"] = EvaluationStatus.FAILED
            _evaluation_jobs[user_id_str]["error"] = "Evaluation timeout: took longer than 10 minutes"
        except asyncio.CancelledError:
            logger.info(f"Evaluation task cancelled for user {user_id_str}")
            _evaluation_jobs[user_id_str]["status"] = EvaluationStatus.FAILED
            _evaluation_jobs[user_id_str]["error"] = "Evaluation cancelled by user"
            raise
        except Exception as e:
            logger.error(f"Error during async evaluation: {e}", exc_info=True)
            _evaluation_jobs[user_id_str]["status"] = EvaluationStatus.FAILED
            _evaluation_jobs[user_id_str]["error"] = str(e)
        finally:
            # Rimuovi il task dalla lista quando finisce
            _evaluation_tasks.pop(user_id_str, None)
    
    # Crea il task e traccialo
    task = background_task_manager._loop.create_task(_generate_report(), name=f"evaluation-{user_id_str}")
    background_task_manager._track_task(task)
    _evaluation_tasks[user_id_str] = task
    
    return {
        "job_id": user_id_str,
        "status": EvaluationStatus.PENDING,
        "message": "Evaluation started",
        "started_at": _evaluation_jobs[user_id_str]["started_at"],
    }


@router.get("/api/v1/evaluation/status")
async def get_evaluation_status(
    current_user: User = Depends(require_admin),
):
    """Get evaluation job status for current user"""
    user_id_str = str(current_user.id)
    
    if user_id_str not in _evaluation_jobs:
        return {
            "job_id": user_id_str,
            "status": None,
            "has_report": user_id_str in _evaluation_reports,
        }
    
    job = _evaluation_jobs[user_id_str]
    return {
        "job_id": user_id_str,
        "status": job["status"],
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "error": job.get("error"),
        "has_report": user_id_str in _evaluation_reports,
    }


@router.post("/api/v1/evaluation/stop")
async def stop_evaluation_report(
    current_user: User = Depends(require_admin),
):
    """Stop ongoing evaluation report generation (admin only)"""
    user_id_str = str(current_user.id)
    
    if user_id_str not in _evaluation_jobs:
        raise HTTPException(status_code=404, detail="No evaluation job found")
    
    job = _evaluation_jobs[user_id_str]
    if job["status"] not in [EvaluationStatus.PENDING, EvaluationStatus.RUNNING]:
        raise HTTPException(status_code=400, detail=f"Evaluation is not running (status: {job['status']})")
    
    # Marca come cancellato
    job["cancelled"] = True
    job["status"] = EvaluationStatus.FAILED
    job["error"] = "Cancelled by user"
    
    # Cancella il task se esiste
    if user_id_str in _evaluation_tasks:
        task = _evaluation_tasks[user_id_str]
        if not task.done():
            task.cancel()
            logger.info(f"Cancelling evaluation task for user {user_id_str}")
        _evaluation_tasks.pop(user_id_str, None)
    
    return {
        "job_id": user_id_str,
        "status": EvaluationStatus.FAILED,
        "message": "Evaluation stopped",
    }


@router.get("/api/v1/evaluation/report", response_class=HTMLResponse)
async def get_evaluation_report(
    current_user: User = Depends(require_admin),
):
    """Get evaluation report HTML (if available)"""
    user_id_str = str(current_user.id)
    
    if user_id_str not in _evaluation_reports:
        raise HTTPException(status_code=404, detail="No evaluation report available")
    
    return HTMLResponse(content=_evaluation_reports[user_id_str])


@router.post("/api/v1/evaluation/generate", response_class=HTMLResponse)
async def generate_evaluation_report(
    category: Optional[str] = Query(None, description="Filter by category"),
    test_ids: Optional[List[str]] = Query(None, description="Specific test IDs to run"),
    parallel: bool = Query(False, description="Run tests in parallel"),
    max_tests: Optional[int] = Query(None, description="Maximum number of test cases to run (default: all)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Generate evaluation report synchronously (admin only) - DEPRECATED
    Use /api/v1/evaluation/start for async generation
    
    Note: This endpoint may take 5-15 minutes depending on the number of test cases.
    Consider using max_tests parameter to limit execution time.
    """
    try:
        # Get test cases
        if test_ids:
            test_cases = get_test_cases_by_id(test_ids)
        elif category:
            test_cases = get_test_cases_by_category(category)
        else:
            test_cases = ALL_TEST_CASES
        
        # Limit number of test cases if max_tests is specified
        if max_tests and max_tests > 0:
            test_cases = test_cases[:max_tests]
            logger.info(f"Limited to {max_tests} test cases (from {len(ALL_TEST_CASES)} total)")
        
        if not test_cases:
            raise HTTPException(status_code=400, detail="No test cases found")
        
        logger.info(f"Running evaluation with {len(test_cases)} test cases (parallel={parallel})")
        
        # Get or create evaluation session
        tenant_result = await db.execute(select(Tenant).limit(1))
        tenant = tenant_result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=404, detail="No tenant found")
        
        from datetime import datetime
        session_result = await db.execute(
            select(SessionModel)
            .where(SessionModel.tenant_id == tenant.id)
            .where(SessionModel.name.like("%Evaluation%"))
            .limit(1)
        )
        session = session_result.scalar_one_or_none()
        
        if not session:
            session_name = f"Evaluation Session {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            session = SessionModel(
                tenant_id=tenant.id,
                name=session_name,
                title=session_name,
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
        
        # Initialize evaluator
        evaluator = AgentEvaluator(
            run_agent_fn=lambda **kwargs: run_agent_for_evaluation(**kwargs),
            db_session=db,
            session_id=session.id,
            current_user=current_user,
        )
        
        # Run evaluation with timeout and semaphore to prevent hanging/overload
        # Usa semaforo per evitare multiple evaluation simultanee che possono bloccare il backend
        async with _evaluation_semaphore:
            try:
                # Timeout di 10 minuti per evitare che il backend si blocchi
                evaluation_timeout = 600.0  # 10 minuti
                logger.info(f"Starting evaluation with timeout {evaluation_timeout}s and {len(test_cases)} test cases")
                report = await asyncio.wait_for(
                    evaluator.evaluate_test_suite(
                        test_cases=test_cases,
                        parallel=parallel,
                    ),
                    timeout=evaluation_timeout
                )
                logger.info(f"Evaluation completed successfully in {report.duration_seconds:.2f}s")
            except asyncio.TimeoutError:
                logger.error(f"Evaluation timeout after {evaluation_timeout} seconds")
                raise HTTPException(
                    status_code=504,
                    detail=f"Evaluation timeout: took longer than {evaluation_timeout} seconds. Try running fewer test cases or use parallel mode."
                )
            except Exception as eval_error:
                logger.error(f"Error during evaluation: {eval_error}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Error during evaluation: {str(eval_error)}"
                )
        
        # Generate HTML report
        html_report = evaluator.generate_report_html(report)
        
        return HTMLResponse(content=html_report)
        
    except Exception as e:
        logger.error(f"Error generating evaluation report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error generating report: {str(e)}")

