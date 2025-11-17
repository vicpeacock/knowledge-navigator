"""
Agent Evaluation Framework
Provides evaluation metrics and test execution for agent performance
"""
import asyncio
import time
import json
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EvaluationMetric(Enum):
    """Types of evaluation metrics"""
    ACCURACY = "accuracy"
    RELEVANCE = "relevance"
    LATENCY = "latency"
    TOOL_USAGE = "tool_usage"
    COMPLETENESS = "completeness"


@dataclass
class TestCase:
    """A single test case for agent evaluation"""
    id: str
    name: str
    description: str
    input_message: str
    expected_tools: Optional[List[str]] = None  # Tools that should be used
    expected_keywords: Optional[List[str]] = None  # Keywords that should appear in response
    expected_response_type: Optional[str] = None  # e.g., "calendar_query", "email_query", "web_search"
    min_response_length: int = 10  # Minimum response length
    max_latency_seconds: float = 30.0  # Maximum acceptable latency
    category: str = "general"  # e.g., "calendar", "email", "web_search", "memory"


@dataclass
class EvaluationResult:
    """Result of evaluating a single test case"""
    test_case_id: str
    test_case_name: str
    passed: bool
    metrics: Dict[str, Any]
    actual_response: str
    actual_tools_used: List[str]
    latency_seconds: float
    errors: List[str]
    timestamp: str


@dataclass
class EvaluationReport:
    """Complete evaluation report"""
    total_tests: int
    passed_tests: int
    failed_tests: int
    overall_accuracy: float
    average_latency: float
    tool_usage_stats: Dict[str, int]
    results: List[EvaluationResult]
    timestamp: str
    duration_seconds: float


class AgentEvaluator:
    """Evaluator for agent performance"""
    
    def __init__(
        self,
        run_agent_fn: Callable,
        db_session: Any,
        session_id: Any,
        current_user: Optional[Any] = None,
    ):
        """
        Initialize evaluator
        
        Args:
            run_agent_fn: Function to run agent (should accept message and return response)
            db_session: Database session
            session_id: Session ID for testing
            current_user: Current user (optional)
        """
        self.run_agent_fn = run_agent_fn
        self.db_session = db_session
        self.session_id = session_id
        self.current_user = current_user
    
    async def evaluate_test_case(self, test_case: TestCase) -> EvaluationResult:
        """
        Evaluate a single test case
        
        Args:
            test_case: Test case to evaluate
            
        Returns:
            EvaluationResult with metrics and pass/fail status
        """
        logger.info(f"Evaluating test case: {test_case.name} ({test_case.id})")
        
        metrics = {}
        errors = []
        actual_response = ""
        actual_tools_used = []
        latency_seconds = 0.0
        
        try:
            # Run agent
            start_time = time.time()
            result = await self.run_agent_fn(
                message=test_case.input_message,
                session_id=self.session_id,
                db=self.db_session,
                current_user=self.current_user,
            )
            latency_seconds = time.time() - start_time
            
            # Extract response and tools
            if isinstance(result, dict):
                actual_response = result.get("response", "") or result.get("content", "")
                actual_tools_used = result.get("tools_used", []) or []
            elif hasattr(result, "response"):
                actual_response = result.response or ""
                actual_tools_used = getattr(result, "tools_used", []) or []
            else:
                actual_response = str(result)
            
            # Calculate metrics
            metrics = self._calculate_metrics(
                test_case=test_case,
                actual_response=actual_response,
                actual_tools_used=actual_tools_used,
                latency_seconds=latency_seconds,
            )
            
            # Determine if test passed
            passed = self._determine_pass(test_case, metrics, errors)
            
        except Exception as e:
            logger.error(f"Error evaluating test case {test_case.id}: {e}", exc_info=True)
            errors.append(str(e))
            metrics = {
                "accuracy": 0.0,
                "relevance": 0.0,
                "latency": latency_seconds,
                "tool_usage": 0.0,
                "completeness": 0.0,
            }
            passed = False
        
        return EvaluationResult(
            test_case_id=test_case.id,
            test_case_name=test_case.name,
            passed=passed,
            metrics=metrics,
            actual_response=actual_response,
            actual_tools_used=actual_tools_used,
            latency_seconds=latency_seconds,
            errors=errors,
            timestamp=datetime.now().isoformat(),
        )
    
    def _calculate_metrics(
        self,
        test_case: TestCase,
        actual_response: str,
        actual_tools_used: List[str],
        latency_seconds: float,
    ) -> Dict[str, Any]:
        """Calculate evaluation metrics"""
        metrics = {}
        
        # 1. Accuracy (based on expected keywords)
        accuracy = 1.0
        if test_case.expected_keywords:
            found_keywords = sum(
                1 for keyword in test_case.expected_keywords
                if keyword.lower() in actual_response.lower()
            )
            accuracy = found_keywords / len(test_case.expected_keywords) if test_case.expected_keywords else 1.0
        metrics["accuracy"] = accuracy
        
        # 2. Relevance (response is not empty and has minimum length)
        relevance = 1.0 if len(actual_response) >= test_case.min_response_length else 0.0
        metrics["relevance"] = relevance
        
        # 3. Latency
        metrics["latency"] = latency_seconds
        
        # 4. Tool Usage (correct tools were used)
        tool_usage = 0.0
        if test_case.expected_tools:
            if actual_tools_used:
                used_expected = sum(
                    1 for tool in test_case.expected_tools
                    if any(tool in used for used in actual_tools_used)
                )
                tool_usage = used_expected / len(test_case.expected_tools)
            else:
                tool_usage = 0.0
        else:
            # If no tools expected, check if response is reasonable without tools
            tool_usage = 1.0 if len(actual_response) >= test_case.min_response_length else 0.0
        metrics["tool_usage"] = tool_usage
        
        # 5. Completeness (response is complete, not truncated)
        completeness = 1.0 if len(actual_response) >= test_case.min_response_length else 0.0
        metrics["completeness"] = completeness
        
        return metrics
    
    def _determine_pass(
        self,
        test_case: TestCase,
        metrics: Dict[str, Any],
        errors: List[str],
    ) -> bool:
        """Determine if test case passed"""
        if errors:
            return False
        
        # Check latency
        if metrics["latency"] > test_case.max_latency_seconds:
            return False
        
        # Check minimum requirements
        if metrics["relevance"] < 0.5:  # Response too short
            return False
        
        # Check accuracy (if keywords expected)
        if test_case.expected_keywords and metrics["accuracy"] < 0.5:
            return False
        
        # Check tool usage (if tools expected)
        if test_case.expected_tools and metrics["tool_usage"] < 0.5:
            return False
        
        return True
    
    async def evaluate_test_suite(
        self,
        test_cases: List[TestCase],
        parallel: bool = False,
    ) -> EvaluationReport:
        """
        Evaluate a suite of test cases
        
        Args:
            test_cases: List of test cases to evaluate
            parallel: Whether to run tests in parallel (default: False)
            
        Returns:
            EvaluationReport with aggregated results
        """
        logger.info(f"Evaluating test suite: {len(test_cases)} test cases")
        start_time = time.time()
        
        if parallel:
            # Run tests in parallel
            tasks = [self.evaluate_test_case(tc) for tc in test_cases]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Handle exceptions
            results = [
                r if not isinstance(r, Exception) else EvaluationResult(
                    test_case_id="error",
                    test_case_name="Error",
                    passed=False,
                    metrics={},
                    actual_response="",
                    actual_tools_used=[],
                    latency_seconds=0.0,
                    errors=[str(r)],
                    timestamp=datetime.now().isoformat(),
                )
                for r in results
            ]
        else:
            # Run tests sequentially
            results = []
            for test_case in test_cases:
                result = await self.evaluate_test_case(test_case)
                results.append(result)
        
        duration_seconds = time.time() - start_time
        
        # Aggregate results
        passed_tests = sum(1 for r in results if r.passed)
        failed_tests = len(results) - passed_tests
        
        # Calculate overall accuracy
        accuracies = [r.metrics.get("accuracy", 0.0) for r in results]
        overall_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0.0
        
        # Calculate average latency
        latencies = [r.latency_seconds for r in results]
        average_latency = sum(latencies) / len(latencies) if latencies else 0.0
        
        # Tool usage stats
        tool_usage_stats = {}
        for result in results:
            for tool in result.actual_tools_used:
                tool_usage_stats[tool] = tool_usage_stats.get(tool, 0) + 1
        
        return EvaluationReport(
            total_tests=len(test_cases),
            passed_tests=passed_tests,
            failed_tests=failed_tests,
            overall_accuracy=overall_accuracy,
            average_latency=average_latency,
            tool_usage_stats=tool_usage_stats,
            results=results,
            timestamp=datetime.now().isoformat(),
            duration_seconds=duration_seconds,
        )
    
    def generate_report_json(self, report: EvaluationReport) -> str:
        """Generate JSON report"""
        return json.dumps(asdict(report), indent=2, ensure_ascii=False, default=str)
    
    def generate_report_text(self, report: EvaluationReport) -> str:
        """Generate human-readable text report"""
        lines = []
        lines.append("=" * 80)
        lines.append("AGENT EVALUATION REPORT")
        lines.append("=" * 80)
        lines.append(f"Timestamp: {report.timestamp}")
        lines.append(f"Duration: {report.duration_seconds:.2f} seconds")
        lines.append("")
        lines.append("SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Total Tests: {report.total_tests}")
        lines.append(f"Passed: {report.passed_tests} ({report.passed_tests/report.total_tests*100:.1f}%)")
        lines.append(f"Failed: {report.failed_tests} ({report.failed_tests/report.total_tests*100:.1f}%)")
        lines.append(f"Overall Accuracy: {report.overall_accuracy:.2%}")
        lines.append(f"Average Latency: {report.average_latency:.2f} seconds")
        lines.append("")
        lines.append("TOOL USAGE STATISTICS")
        lines.append("-" * 80)
        for tool, count in sorted(report.tool_usage_stats.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  {tool}: {count}")
        lines.append("")
        lines.append("DETAILED RESULTS")
        lines.append("-" * 80)
        for result in report.results:
            status = "✅ PASS" if result.passed else "❌ FAIL"
            lines.append(f"\n{status} - {result.test_case_name} ({result.test_case_id})")
            lines.append(f"  Latency: {result.latency_seconds:.2f}s")
            lines.append(f"  Accuracy: {result.metrics.get('accuracy', 0.0):.2%}")
            lines.append(f"  Relevance: {result.metrics.get('relevance', 0.0):.2%}")
            lines.append(f"  Tool Usage: {result.metrics.get('tool_usage', 0.0):.2%}")
            lines.append(f"  Tools Used: {', '.join(result.actual_tools_used) if result.actual_tools_used else 'None'}")
            if result.errors:
                lines.append(f"  Errors: {', '.join(result.errors)}")
            if not result.passed:
                lines.append(f"  Response Preview: {result.actual_response[:200]}...")
        lines.append("")
        lines.append("=" * 80)
        return "\n".join(lines)
    
    def generate_report_html(self, report: EvaluationReport) -> str:
        """Generate HTML report with embedded CSS"""
        html_parts = []
        
        # HTML header with embedded CSS
        html_parts.append("""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Evaluation Report</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            padding: 30px;
        }
        h1 {
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }
        .summary-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }
        .summary-card h3 {
            font-size: 14px;
            opacity: 0.9;
            margin-bottom: 10px;
        }
        .summary-card .value {
            font-size: 32px;
            font-weight: bold;
            margin: 10px 0;
        }
        .summary-card.success {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }
        .summary-card.warning {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }
        .summary-card.info {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }
        .section {
            margin: 30px 0;
        }
        .section h2 {
            color: #2c3e50;
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .tool-stats {
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }
        .tool-badge {
            background: #3498db;
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
        }
        .test-result {
            border: 1px solid #ecf0f1;
            border-radius: 8px;
            padding: 20px;
            margin: 15px 0;
            background: #fafafa;
        }
        .test-result.passed {
            border-left: 4px solid #27ae60;
        }
        .test-result.failed {
            border-left: 4px solid #e74c3c;
        }
        .test-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        .test-title {
            font-size: 18px;
            font-weight: bold;
            color: #2c3e50;
        }
        .test-status {
            padding: 6px 12px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 14px;
        }
        .test-status.pass {
            background: #27ae60;
            color: white;
        }
        .test-status.fail {
            background: #e74c3c;
            color: white;
        }
        .metrics {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin: 15px 0;
        }
        .metric {
            background: white;
            padding: 15px;
            border-radius: 6px;
            border: 1px solid #ecf0f1;
        }
        .metric-label {
            font-size: 12px;
            color: #7f8c8d;
            text-transform: uppercase;
            margin-bottom: 5px;
        }
        .metric-value {
            font-size: 24px;
            font-weight: bold;
            color: #2c3e50;
        }
        .metric-value.good {
            color: #27ae60;
        }
        .metric-value.warning {
            color: #f39c12;
        }
        .metric-value.bad {
            color: #e74c3c;
        }
        .response-preview {
            background: #ecf0f1;
            padding: 15px;
            border-radius: 6px;
            margin-top: 15px;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            color: #34495e;
        }
        .errors {
            background: #fee;
            border: 1px solid #e74c3c;
            padding: 15px;
            border-radius: 6px;
            margin-top: 15px;
            color: #c0392b;
        }
        .footer {
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ecf0f1;
            color: #7f8c8d;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧪 Agent Evaluation Report</h1>
        <div class="section">
            <p><strong>Timestamp:</strong> {report.timestamp}</p>
            <p><strong>Duration:</strong> {report.duration_seconds:.2f} seconds</p>
        </div>
""")
        
        # Summary cards
        pass_rate = (report.passed_tests / report.total_tests * 100) if report.total_tests > 0 else 0
        fail_rate = 100 - pass_rate
        accuracy_pct = report.overall_accuracy * 100
        html_parts.append(f"""
        <div class="summary">
            <div class="summary-card">
                <h3>Total Tests</h3>
                <div class="value">{report.total_tests}</div>
            </div>
            <div class="summary-card success">
                <h3>Passed</h3>
                <div class="value">{report.passed_tests}</div>
                <div>{pass_rate:.1f}%</div>
            </div>
            <div class="summary-card warning">
                <h3>Failed</h3>
                <div class="value">{report.failed_tests}</div>
                <div>{fail_rate:.1f}%</div>
            </div>
            <div class="summary-card info">
                <h3>Overall Accuracy</h3>
                <div class="value">{accuracy_pct:.1f}%</div>
            </div>
            <div class="summary-card info">
                <h3>Avg Latency</h3>
                <div class="value">{report.average_latency:.2f}s</div>
            </div>
        </div>
""")
        
        # Tool usage statistics
        if report.tool_usage_stats:
            html_parts.append("""
        <div class="section">
            <h2>🔧 Tool Usage Statistics</h2>
            <div class="tool-stats">
""")
            for tool, count in sorted(report.tool_usage_stats.items(), key=lambda x: x[1], reverse=True):
                html_parts.append(f'                <span class="tool-badge">{tool}: {count}</span>\n')
            html_parts.append("            </div>\n        </div>\n")
        
        # Detailed results
        html_parts.append("""
        <div class="section">
            <h2>📊 Detailed Results</h2>
""")
        
        for result in report.results:
            status_class = "passed" if result.passed else "failed"
            status_text = "✅ PASS" if result.passed else "❌ FAIL"
            status_badge = "pass" if result.passed else "fail"
            
            # Determine metric value classes
            accuracy = result.metrics.get('accuracy', 0.0)
            latency = result.latency_seconds
            accuracy_class = "good" if accuracy >= 0.8 else "warning" if accuracy >= 0.5 else "bad"
            latency_class = "good" if latency < 10 else "warning" if latency < 30 else "bad"
            
            html_parts.append(f"""
            <div class="test-result {status_class}">
                <div class="test-header">
                    <div class="test-title">{result.test_case_name}</div>
                    <div class="test-status {status_badge}">{status_text}</div>
                </div>
                <p><strong>Test ID:</strong> {result.test_case_id}</p>
                <div class="metrics">
                    <div class="metric">
                        <div class="metric-label">Latency</div>
                        <div class="metric-value {latency_class}">{latency:.2f}s</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Accuracy</div>
                        <div class="metric-value {accuracy_class}">{accuracy:.1%}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Relevance</div>
                        <div class="metric-value good">{result.metrics.get('relevance', 0.0):.1%}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">Tool Usage</div>
                        <div class="metric-value good">{result.metrics.get('tool_usage', 0.0):.1%}</div>
                    </div>
                </div>
""")
            
            if result.actual_tools_used:
                html_parts.append(f'                <p><strong>Tools Used:</strong> {", ".join(result.actual_tools_used)}</p>\n')
            else:
                html_parts.append('                <p><strong>Tools Used:</strong> None</p>\n')
            
            if result.errors:
                html_parts.append('                <div class="errors">\n')
                html_parts.append('                    <strong>Errors:</strong><br>\n')
                for error in result.errors:
                    html_parts.append(f'                    • {error}<br>\n')
                html_parts.append('                </div>\n')
            
            if not result.passed and result.actual_response:
                preview = result.actual_response[:300] + "..." if len(result.actual_response) > 300 else result.actual_response
                html_parts.append(f"""
                <div class="response-preview">
                    <strong>Response Preview:</strong><br>
                    {preview}
                </div>
""")
            
            html_parts.append("            </div>\n")
        
        html_parts.append("        </div>\n")
        
        # Footer
        html_parts.append("""
        <div class="footer">
            <p>Generated by Agent Evaluation System</p>
            <p>Knowledge Navigator - Kaggle Challenge Submission</p>
        </div>
    </div>
</body>
</html>
""")
        
        return "".join(html_parts)

