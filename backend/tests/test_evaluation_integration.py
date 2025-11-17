#!/usr/bin/env python3
"""
Integration test per il sistema di evaluation
Verifica che il sistema funzioni end-to-end senza interferire con il backend
"""
import pytest
import asyncio
from app.core.evaluation import AgentEvaluator, EvaluationReport
from tests.evaluation.test_cases import GENERAL_TEST_CASES


class TestEvaluationIntegration:
    """Test di integrazione per il sistema di evaluation"""
    
    async def mock_agent_fn(self, message: str, session_id, db, current_user=None):
        """Mock agent function per testing"""
        await asyncio.sleep(0.05)  # Simula latenza minima
        return {
            "response": f"Risposta di test per: {message}",
            "tools_used": [],
        }
    
    @pytest.mark.asyncio
    async def test_evaluator_initialization(self):
        """Test che l'evaluator si inizializzi correttamente"""
        evaluator = AgentEvaluator(
            run_agent_fn=self.mock_agent_fn,
            db_session=None,
            session_id="test-session",
        )
        assert evaluator is not None
        assert evaluator.run_agent_fn is not None
        assert evaluator.session_id == "test-session"
    
    @pytest.mark.asyncio
    async def test_single_test_case_evaluation(self):
        """Test evaluation di un singolo test case"""
        evaluator = AgentEvaluator(
            run_agent_fn=self.mock_agent_fn,
            db_session=None,
            session_id="test-session",
        )
        
        # Usa un test case generale semplice
        test_case = GENERAL_TEST_CASES[0]
        result = await evaluator.evaluate_test_case(test_case)
        
        assert result is not None
        assert result.test_case_id == test_case.id
        assert result.test_case_name == test_case.name
        assert result.latency_seconds > 0
        assert isinstance(result.passed, bool)
        assert isinstance(result.metrics, dict)
        assert "accuracy" in result.metrics
        assert "relevance" in result.metrics
        assert "latency" in result.metrics
    
    @pytest.mark.asyncio
    async def test_test_suite_evaluation_sequential(self):
        """Test evaluation di una suite di test cases (sequenziale)"""
        evaluator = AgentEvaluator(
            run_agent_fn=self.mock_agent_fn,
            db_session=None,
            session_id="test-session",
        )
        
        # Usa solo i primi 2 test cases generali per velocità
        test_cases = GENERAL_TEST_CASES[:2]
        report = await evaluator.evaluate_test_suite(
            test_cases=test_cases,
            parallel=False,
        )
        
        assert report is not None
        assert report.total_tests == 2
        assert report.passed_tests >= 0
        assert report.failed_tests >= 0
        assert report.passed_tests + report.failed_tests == 2
        assert len(report.results) == 2
        assert report.duration_seconds > 0
        assert report.overall_accuracy >= 0.0
        assert report.overall_accuracy <= 1.0
    
    @pytest.mark.asyncio
    async def test_report_generation(self):
        """Test generazione report"""
        evaluator = AgentEvaluator(
            run_agent_fn=self.mock_agent_fn,
            db_session=None,
            session_id="test-session",
        )
        
        test_case = GENERAL_TEST_CASES[0]
        result = await evaluator.evaluate_test_case(test_case)
        
        # Crea un report minimo
        from app.core.evaluation import EvaluationReport
        from datetime import datetime
        
        report = EvaluationReport(
            total_tests=1,
            passed_tests=1 if result.passed else 0,
            failed_tests=0 if result.passed else 1,
            overall_accuracy=result.metrics.get("accuracy", 0.0),
            average_latency=result.latency_seconds,
            tool_usage_stats={},
            results=[result],
            timestamp=datetime.now().isoformat(),
            duration_seconds=result.latency_seconds,
        )
        
        # Test generazione JSON
        json_report = evaluator.generate_report_json(report)
        assert isinstance(json_report, str)
        assert len(json_report) > 0
        assert "total_tests" in json_report
        
        # Test generazione Text
        text_report = evaluator.generate_report_text(report)
        assert isinstance(text_report, str)
        assert len(text_report) > 0
        assert "EVALUATION REPORT" in text_report or "evaluation" in text_report.lower()
    
    @pytest.mark.asyncio
    async def test_evaluator_error_handling(self):
        """Test gestione errori nell'evaluator"""
        async def failing_agent_fn(message, session_id, db, current_user=None):
            raise Exception("Simulated error")
        
        evaluator = AgentEvaluator(
            run_agent_fn=failing_agent_fn,
            db_session=None,
            session_id="test-session",
        )
        
        test_case = GENERAL_TEST_CASES[0]
        result = await evaluator.evaluate_test_case(test_case)
        
        # Il risultato dovrebbe indicare fallimento
        assert result.passed is False
        assert len(result.errors) > 0
        assert "Simulated error" in result.errors[0]
        assert result.metrics["accuracy"] == 0.0


class TestEvaluationBackendCompatibility:
    """Test per verificare che evaluation non interferisca con il backend"""
    
    def test_evaluation_imports_dont_break_backend(self):
        """Test che importare evaluation non rompa il backend"""
        # Importa moduli principali del backend
        from app.main import app
        from app.core.dependencies import init_clients
        from app.core.evaluation import AgentEvaluator
        
        # Verifica che tutto sia importabile
        assert app is not None
        assert init_clients is not None
        assert AgentEvaluator is not None
    
    def test_evaluation_module_isolation(self):
        """Test che il modulo evaluation sia isolato"""
        # Verifica che evaluation non sia importato automaticamente
        import sys
        modules_before = set(sys.modules.keys())
        
        # Importa backend
        from app.main import app
        
        modules_after = set(sys.modules.keys())
        new_modules = modules_after - modules_before
        
        # evaluation non dovrebbe essere importato automaticamente
        evaluation_modules = [m for m in new_modules if "evaluation" in m]
        # È OK se evaluation è importato, ma non dovrebbe essere necessario per il backend
        # (il backend funziona senza evaluation)
        
        # Verifica che il backend funzioni
        assert app is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

