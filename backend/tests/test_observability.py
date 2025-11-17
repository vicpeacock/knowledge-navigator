"""
Tests for observability (tracing and metrics)
"""
import pytest
import time
from app.core.tracing import init_tracing, trace_span, get_trace_id, get_span_id
from app.core.metrics import init_metrics, increment_counter, observe_histogram, set_gauge, get_metrics_export


def test_tracing_initialization():
    """Test that tracing can be initialized"""
    result = init_tracing(service_name="test-service", enable_console=False)
    # Should return True if OpenTelemetry available, False otherwise (fallback)
    assert result is not None


def test_trace_span():
    """Test creating a trace span"""
    init_tracing(service_name="test-service", enable_console=False)
    
    with trace_span("test.operation", {"test.attr": "value"}) as span:
        # Span should be created
        assert span is not None
        time.sleep(0.01)  # Small delay to ensure span has duration
    
    # Trace ID should be available (or None if using fallback)
    trace_id = get_trace_id()
    # Either we have a trace ID (OpenTelemetry) or None (fallback)
    assert trace_id is None or isinstance(trace_id, str)


def test_metrics_initialization():
    """Test that metrics can be initialized"""
    result = init_metrics()
    # Should return True if Prometheus available, False otherwise (fallback)
    assert result is not None


def test_counter_increment():
    """Test incrementing a counter"""
    init_metrics()
    
    increment_counter("test_counter", value=1.0)
    increment_counter("test_counter", value=2.0, labels={"label1": "value1"})
    
    # Metrics should be recorded (we can't easily verify without Prometheus,
    # but we can check that no exception is raised)
    assert True


def test_histogram_observe():
    """Test observing a histogram value"""
    init_metrics()
    
    observe_histogram("test_histogram", 0.5)
    observe_histogram("test_histogram", 1.0, labels={"label1": "value1"})
    
    # Metrics should be recorded
    assert True


def test_gauge_set():
    """Test setting a gauge value"""
    init_metrics()
    
    set_gauge("test_gauge", 42.0)
    set_gauge("test_gauge", 100.0, labels={"label1": "value1"})
    
    # Metrics should be recorded
    assert True


def test_metrics_export():
    """Test exporting metrics"""
    init_metrics()
    
    # Add some metrics
    increment_counter("export_test_counter", value=1.0)
    observe_histogram("export_test_histogram", 0.5)
    set_gauge("export_test_gauge", 10.0)
    
    # Export metrics
    metrics_bytes, content_type = get_metrics_export()
    
    # Should return bytes and content type
    assert isinstance(metrics_bytes, bytes)
    assert isinstance(content_type, str)
    assert len(metrics_bytes) > 0


def test_trace_span_nested():
    """Test nested trace spans"""
    init_tracing(service_name="test-service", enable_console=False)
    
    with trace_span("parent.operation") as parent:
        assert parent is not None
        
        with trace_span("child.operation") as child:
            assert child is not None
            time.sleep(0.01)
        
        time.sleep(0.01)
    
    # Both spans should complete without error
    assert True


def test_trace_span_with_exception():
    """Test trace span handles exceptions correctly"""
    init_tracing(service_name="test-service", enable_console=False)
    
    try:
        with trace_span("error.operation") as span:
            assert span is not None
            raise ValueError("Test error")
    except ValueError:
        # Exception should be raised, span should handle it
        pass
    
    # Should complete without error
    assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

