#!/usr/bin/env python3
"""
Unit tests per il framework di evaluation
Verifica che tutte le componenti funzionino correttamente
"""
import pytest
import asyncio
from datetime import datetime
from app.core.evaluation import (
    TestCase as EvalTestCase,  # Rename to avoid conflict with pytest
    EvaluationResult,
    EvaluationReport,
    AgentEvaluator,
    EvaluationMetric,
)


class TestEvalTestCase:
    """Test per TestCase dataclass"""
    
    def test_test_case_creation(self):
        """Test creazione TestCase"""
        tc = EvalTestCase(
            id="test_001",
            name="Test Case",
            description="Test description",
            input_message="Test message",
            expected_tools=["tool1"],
            expected_keywords=["keyword1"],
            category="test",
        )
        assert tc.id == "test_001"
        assert tc.name == "Test Case"
        assert tc.input_message == "Test message"
        assert tc.expected_tools == ["tool1"]
        assert tc.expected_keywords == ["keyword1"]
        assert tc.category == "test"
        assert tc.min_response_length == 10  # Default
        assert tc.max_latency_seconds == 30.0  # Default


class TestEvaluationResult:
    """Test per EvaluationResult dataclass"""
    
    def test_evaluation_result_creation(self):
        """Test creazione EvaluationResult"""
        result = EvaluationResult(
            test_case_id="test_001",
            test_case_name="Test Case",
            passed=True,
            metrics={"accuracy": 0.9, "relevance": 1.0},
            actual_response="Test response",
            actual_tools_used=["tool1"],
            latency_seconds=1.5,
            errors=[],
            timestamp=datetime.now().isoformat(),
        )
        assert result.test_case_id == "test_001"
        assert result.passed is True
        assert result.metrics["accuracy"] == 0.9
        assert len(result.errors) == 0


class TestEvaluationReport:
    """Test per EvaluationReport dataclass"""
    
    def test_evaluation_report_creation(self):
        """Test creazione EvaluationReport"""
        result1 = EvaluationResult(
            test_case_id="test_001",
            test_case_name="Test 1",
            passed=True,
            metrics={"accuracy": 0.9},
            actual_response="Response 1",
            actual_tools_used=[],
            latency_seconds=1.0,
            errors=[],
            timestamp=datetime.now().isoformat(),
        )
        result2 = EvaluationResult(
            test_case_id="test_002",
            test_case_name="Test 2",
            passed=False,
            metrics={"accuracy": 0.5},
            actual_response="Response 2",
            actual_tools_used=[],
            latency_seconds=2.0,
            errors=["Error"],
            timestamp=datetime.now().isoformat(),
        )
        
        report = EvaluationReport(
            total_tests=2,
            passed_tests=1,
            failed_tests=1,
            overall_accuracy=0.7,
            average_latency=1.5,
            tool_usage_stats={},
            results=[result1, result2],
            timestamp=datetime.now().isoformat(),
            duration_seconds=3.0,
        )
        
        assert report.total_tests == 2
        assert report.passed_tests == 1
        assert report.failed_tests == 1
        assert report.overall_accuracy == 0.7
        assert len(report.results) == 2


class TestAgentEvaluator:
    """Test per AgentEvaluator"""
    
    async def mock_agent_fn(self, message: str, session_id, db, current_user=None):
        """Mock agent function per testing"""
        await asyncio.sleep(0.1)  # Simula latenza
        return {
            "response": f"Mock response to: {message}",
            "tools_used": ["mock_tool"],
        }
    
    @pytest.mark.asyncio
    async def test_calculate_metrics_accuracy(self):
        """Test calcolo metriche - accuracy"""
        evaluator = AgentEvaluator(
            run_agent_fn=self.mock_agent_fn,
            db_session=None,
            session_id="test-session",
        )
        
        test_case = EvalTestCase(
            id="test_001",
            name="Test",
            description="Test",
            input_message="Test message with keyword1 and keyword2",
            expected_keywords=["keyword1", "keyword2"],
            category="test",
        )
        
        metrics = evaluator._calculate_metrics(
            test_case=test_case,
            actual_response="This response contains keyword1 and keyword2",
            actual_tools_used=[],
            latency_seconds=1.0,
        )
        
        assert metrics["accuracy"] == 1.0  # Entrambe le keywords trovate
        assert metrics["relevance"] == 1.0  # Risposta abbastanza lunga
        assert metrics["latency"] == 1.0
    
    @pytest.mark.asyncio
    async def test_calculate_metrics_partial_accuracy(self):
        """Test calcolo metriche - accuracy parziale"""
        evaluator = AgentEvaluator(
            run_agent_fn=self.mock_agent_fn,
            db_session=None,
            session_id="test-session",
        )
        
        test_case = EvalTestCase(
            id="test_002",
            name="Test",
            description="Test",
            input_message="Test message",
            expected_keywords=["keyword1", "keyword2", "keyword3"],
            category="test",
        )
        
        metrics = evaluator._calculate_metrics(
            test_case=test_case,
            actual_response="This response contains keyword1 only",
            actual_tools_used=[],
            latency_seconds=1.0,
        )
        
        # Solo 1 su 3 keywords trovate
        assert metrics["accuracy"] == pytest.approx(1.0 / 3.0, abs=0.01)
    
    @pytest.mark.asyncio
    async def test_calculate_metrics_tool_usage(self):
        """Test calcolo metriche - tool usage"""
        evaluator = AgentEvaluator(
            run_agent_fn=self.mock_agent_fn,
            db_session=None,
            session_id="test-session",
        )
        
        test_case = EvalTestCase(
            id="test_003",
            name="Test",
            description="Test",
            input_message="Test message",
            expected_tools=["tool1", "tool2"],
            category="test",
        )
        
        # Tutti i tool attesi sono stati usati
        metrics = evaluator._calculate_metrics(
            test_case=test_case,
            actual_response="Response",
            actual_tools_used=["tool1", "tool2"],
            latency_seconds=1.0,
        )
        assert metrics["tool_usage"] == 1.0
        
        # Solo metà dei tool attesi sono stati usati
        metrics = evaluator._calculate_metrics(
            test_case=test_case,
            actual_response="Response",
            actual_tools_used=["tool1"],
            latency_seconds=1.0,
        )
        assert metrics["tool_usage"] == 0.5
    
    @pytest.mark.asyncio
    async def test_determine_pass(self):
        """Test determinazione pass/fail"""
        evaluator = AgentEvaluator(
            run_agent_fn=self.mock_agent_fn,
            db_session=None,
            session_id="test-session",
        )
        
        test_case = EvalTestCase(
            id="test_004",
            name="Test",
            description="Test",
            input_message="Test",
            expected_keywords=["keyword1"],
            category="test",
            max_latency_seconds=5.0,
        )
        
        # Test che passa
        metrics = {
            "accuracy": 1.0,
            "relevance": 1.0,
            "latency": 2.0,
            "tool_usage": 1.0,
            "completeness": 1.0,
        }
        passed = evaluator._determine_pass(test_case, metrics, [])
        assert passed is True
        
        # Test che fallisce per latenza
        metrics["latency"] = 10.0
        passed = evaluator._determine_pass(test_case, metrics, [])
        assert passed is False
        
        # Test che fallisce per accuracy
        metrics["latency"] = 2.0
        metrics["accuracy"] = 0.3
        passed = evaluator._determine_pass(test_case, metrics, [])
        assert passed is False
        
        # Test che fallisce per errori
        passed = evaluator._determine_pass(test_case, metrics, ["Error occurred"])
        assert passed is False
    
    @pytest.mark.asyncio
    async def test_evaluate_test_case_success(self):
        """Test evaluation di un test case con successo"""
        evaluator = AgentEvaluator(
            run_agent_fn=self.mock_agent_fn,
            db_session=None,
            session_id="test-session",
        )
        
        test_case = EvalTestCase(
            id="test_005",
            name="Test Success",
            description="Test",
            input_message="Test message",
            expected_keywords=["response"],
            category="test",
        )
        
        result = await evaluator.evaluate_test_case(test_case)
        
        assert result.test_case_id == "test_005"
        assert result.passed is True
        assert "Mock response" in result.actual_response
        assert len(result.errors) == 0
        assert result.latency_seconds > 0
    
    @pytest.mark.asyncio
    async def test_evaluate_test_case_failure(self):
        """Test evaluation di un test case con fallimento"""
        async def failing_agent_fn(message, session_id, db, current_user=None):
            raise Exception("Agent failed")
        
        evaluator = AgentEvaluator(
            run_agent_fn=failing_agent_fn,
            db_session=None,
            session_id="test-session",
        )
        
        test_case = EvalTestCase(
            id="test_006",
            name="Test Failure",
            description="Test",
            input_message="Test message",
            category="test",
        )
        
        result = await evaluator.evaluate_test_case(test_case)
        
        assert result.test_case_id == "test_006"
        assert result.passed is False
        assert len(result.errors) > 0
        assert "Agent failed" in result.errors[0]


class TestReportGeneration:
    """Test per generazione report"""
    
    def test_generate_report_json(self):
        """Test generazione report JSON"""
        evaluator = AgentEvaluator(
            run_agent_fn=None,
            db_session=None,
            session_id="test-session",
        )
        
        report = EvaluationReport(
            total_tests=1,
            passed_tests=1,
            failed_tests=0,
            overall_accuracy=1.0,
            average_latency=1.0,
            tool_usage_stats={"tool1": 1},
            results=[],
            timestamp=datetime.now().isoformat(),
            duration_seconds=1.0,
        )
        
        json_report = evaluator.generate_report_json(report)
        assert isinstance(json_report, str)
        assert "total_tests" in json_report
        assert "1" in json_report
    
    def test_generate_report_text(self):
        """Test generazione report text"""
        evaluator = AgentEvaluator(
            run_agent_fn=None,
            db_session=None,
            session_id="test-session",
        )
        
        result = EvaluationResult(
            test_case_id="test_001",
            test_case_name="Test Case",
            passed=True,
            metrics={"accuracy": 0.9},
            actual_response="Response",
            actual_tools_used=["tool1"],
            latency_seconds=1.0,
            errors=[],
            timestamp=datetime.now().isoformat(),
        )
        
        report = EvaluationReport(
            total_tests=1,
            passed_tests=1,
            failed_tests=0,
            overall_accuracy=0.9,
            average_latency=1.0,
            tool_usage_stats={"tool1": 1},
            results=[result],
            timestamp=datetime.now().isoformat(),
            duration_seconds=1.0,
        )
        
        text_report = evaluator.generate_report_text(report)
        assert isinstance(text_report, str)
        assert "AGENT EVALUATION REPORT" in text_report
        assert "Test Case" in text_report
        assert "✅ PASS" in text_report or "PASS" in text_report


if __name__ == "__main__":
    # Esegui test con pytest
    pytest.main([__file__, "-v"])

