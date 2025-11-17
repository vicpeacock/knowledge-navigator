#!/usr/bin/env python3
"""
Script per eseguire evaluation dell'agent
Esegue una suite di test cases e genera un report
"""
import asyncio
import sys
import json
from pathlib import Path
from uuid import UUID
from datetime import datetime
from typing import Any, Optional, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.database import AsyncSessionLocal
from app.models.schemas import ChatRequest
from app.core.dependencies import (
    init_clients,
    get_ollama_client,
    get_memory_manager,
    get_planner_client,
    get_agent_activity_stream,
)
from app.agents import run_langgraph_chat
from app.models.database import Session as SessionModel, User, Tenant
from sqlalchemy import select
from app.core.evaluation import AgentEvaluator
from tests.evaluation.test_cases import ALL_TEST_CASES, get_test_cases_by_category


async def run_agent_for_evaluation(
    message: str,
    session_id: UUID,
    db: Any,
    current_user: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Wrapper function to run agent for evaluation
    
    Args:
        message: User message
        session_id: Session ID
        db: Database session
        current_user: Current user (optional)
        
    Returns:
        Dict with response, tools_used, etc.
    """
    # Initialize clients if not already done
    init_clients()
    ollama = get_ollama_client()
    planner_client = get_planner_client()
    memory_manager = get_memory_manager()
    agent_activity_stream = get_agent_activity_stream()
    
    # Create chat request
    request = ChatRequest(
        session_id=session_id,
        message=message,
        use_memory=True,
        force_web_search=False,
    )
    
    # Prepare context
    session_context = []
    retrieved_memory = []
    memory_used = {}
    
    # Run LangGraph
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
    
    # Extract response
    # LangGraphResult is a TypedDict, so access as dict
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


async def main():
    """Main evaluation function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run agent evaluation")
    parser.add_argument(
        "--category",
        type=str,
        help="Filter test cases by category (calendar, email, web_search, maps, memory, general)",
    )
    parser.add_argument(
        "--test-ids",
        type=str,
        nargs="+",
        help="Run specific test cases by ID",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run tests in parallel",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="evaluation_report.json",
        help="Output file for JSON report",
    )
    parser.add_argument(
        "--text-output",
        type=str,
        default="evaluation_report.txt",
        help="Output file for text report",
    )
    parser.add_argument(
        "--html-output",
        type=str,
        default=None,
        help="Output file for HTML report (optional)",
    )
    args = parser.parse_args()
    
    print("🧪 Agent Evaluation System")
    print("=" * 80)
    print()
    
    # Get test cases
    if args.test_ids:
        from tests.evaluation.test_cases import get_test_cases_by_id
        test_cases = get_test_cases_by_id(args.test_ids)
        print(f"📋 Running {len(test_cases)} specific test cases")
    elif args.category:
        test_cases = get_test_cases_by_category(args.category)
        print(f"📋 Running {len(test_cases)} test cases in category: {args.category}")
    else:
        test_cases = ALL_TEST_CASES
        print(f"📋 Running all {len(test_cases)} test cases")
    
    if not test_cases:
        print("❌ No test cases found")
        return
    
    # Setup database and session
    print("\n1️⃣  Setting up database and session...")
    async with AsyncSessionLocal() as db:
        # Get default tenant
        tenant_result = await db.execute(select(Tenant).limit(1))
        tenant = tenant_result.scalar_one_or_none()
        if not tenant:
            print("❌ No tenant found")
            return
        print(f"   ✅ Tenant: {tenant.id}")
        
        # Get or create evaluation session
        session_result = await db.execute(
            select(SessionModel)
            .where(SessionModel.tenant_id == tenant.id)
            .where(SessionModel.title.like("%Evaluation%"))
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
            print(f"   ✅ Created evaluation session: {session.id}")
        else:
            print(f"   ✅ Using existing evaluation session: {session.id}")
        
        # Get or create user
        user_result = await db.execute(
            select(User).where(User.tenant_id == tenant.id).limit(1)
        )
        user = user_result.scalar_one_or_none()
        if user:
            print(f"   ✅ Using user: {user.email}")
        else:
            print("   ⚠️  No user found, evaluation may be limited")
        
        # Initialize evaluator
        print("\n2️⃣  Initializing evaluator...")
        evaluator = AgentEvaluator(
            run_agent_fn=lambda **kwargs: run_agent_for_evaluation(**kwargs),
            db_session=db,
            session_id=session.id,
            current_user=user,
        )
        print("   ✅ Evaluator initialized")
        
        # Run evaluation
        print(f"\n3️⃣  Running evaluation ({'parallel' if args.parallel else 'sequential'})...")
        print(f"   This may take several minutes...")
        report = await evaluator.evaluate_test_suite(
            test_cases=test_cases,
            parallel=args.parallel,
        )
        
        # Generate reports
        print("\n4️⃣  Generating reports...")
        json_report = evaluator.generate_report_json(report)
        text_report = evaluator.generate_report_text(report)
        
        # Save reports
        output_path = Path(args.output)
        text_output_path = Path(args.text_output)
        
        output_path.write_text(json_report, encoding="utf-8")
        text_output_path.write_text(text_report, encoding="utf-8")
        
        print(f"   ✅ JSON report saved: {output_path}")
        print(f"   ✅ Text report saved: {text_output_path}")
        
        # Generate HTML report if requested
        if args.html_output:
            html_report = evaluator.generate_report_html(report)
            html_output_path = Path(args.html_output)
            html_output_path.write_text(html_report, encoding="utf-8")
            print(f"   ✅ HTML report saved: {html_output_path}")
        
        # Print summary
        print("\n" + "=" * 80)
        print("EVALUATION SUMMARY")
        print("=" * 80)
        print(f"Total Tests: {report.total_tests}")
        print(f"Passed: {report.passed_tests} ({report.passed_tests/report.total_tests*100:.1f}%)")
        print(f"Failed: {report.failed_tests} ({report.failed_tests/report.total_tests*100:.1f}%)")
        print(f"Overall Accuracy: {report.overall_accuracy:.2%}")
        print(f"Average Latency: {report.average_latency:.2f} seconds")
        print(f"Duration: {report.duration_seconds:.2f} seconds")
        print("=" * 80)
        
        # Print failed tests
        failed_results = [r for r in report.results if not r.passed]
        if failed_results:
            print("\n❌ FAILED TESTS:")
            for result in failed_results:
                print(f"  - {result.test_case_name} ({result.test_case_id})")
                if result.errors:
                    print(f"    Errors: {', '.join(result.errors)}")
                print(f"    Response: {result.actual_response[:100]}...")
        
        print(f"\n📄 Full report available in: {text_output_path}")


if __name__ == "__main__":
    asyncio.run(main())

