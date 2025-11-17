"""
Tracing module for observability using OpenTelemetry
Provides distributed tracing for API calls, tool execution, and LLM interactions
"""
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager
from functools import wraps
import time

logger = logging.getLogger(__name__)

# Try to import OpenTelemetry, fallback to simple tracing if not available
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.trace import Status, StatusCode
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    
    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    logger.warning("OpenTelemetry not available. Using simple tracing fallback.")


class SimpleTracer:
    """Simple tracing fallback when OpenTelemetry is not available"""
    
    def __init__(self):
        self.spans: list = []
        self.current_span: Optional[Dict[str, Any]] = None
    
    def start_span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Start a new span"""
        span = {
            "name": name,
            "attributes": attributes or {},
            "start_time": time.time(),
            "end_time": None,
            "status": "OK",
            "events": []
        }
        self.current_span = span
        return span
    
    def end_span(self, span: Optional[Dict[str, Any]] = None, status: str = "OK"):
        """End a span"""
        if span is None:
            span = self.current_span
        if span:
            span["end_time"] = time.time()
            span["duration"] = span["end_time"] - span["start_time"]
            span["status"] = status
            self.spans.append(span)
            self.current_span = None
            logger.debug(f"Span {span['name']} completed in {span['duration']:.3f}s")
    
    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add an event to the current span"""
        if self.current_span:
            self.current_span["events"].append({
                "name": name,
                "attributes": attributes or {},
                "time": time.time()
            })
    
    def set_attribute(self, key: str, value: Any):
        """Set an attribute on the current span"""
        if self.current_span:
            self.current_span["attributes"][key] = value


# Global tracer instance
_tracer: Optional[Any] = None
_simple_tracer: Optional[SimpleTracer] = None


def init_tracing(service_name: str = "knowledge-navigator", enable_console: bool = True):
    """
    Initialize tracing system
    
    Args:
        service_name: Name of the service for tracing
        enable_console: Whether to export traces to console (for development)
    """
    global _tracer, _simple_tracer
    
    if OPENTELEMETRY_AVAILABLE:
        try:
            # Create resource
            resource = Resource.create({
                "service.name": service_name,
                "service.version": "1.0.0"
            })
            
            # Create tracer provider
            provider = TracerProvider(resource=resource)
            
            # Add console exporter for development
            if enable_console:
                console_exporter = ConsoleSpanExporter()
                provider.add_span_processor(BatchSpanProcessor(console_exporter))
            
            # Set global tracer provider
            trace.set_tracer_provider(provider)
            _tracer = trace.get_tracer(__name__)
            
            logger.info("✅ OpenTelemetry tracing initialized")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize OpenTelemetry: {e}", exc_info=True)
            _simple_tracer = SimpleTracer()
            logger.info("Using simple tracing fallback")
            return False
    else:
        _simple_tracer = SimpleTracer()
        logger.info("Using simple tracing fallback (OpenTelemetry not available)")
        return False


def get_tracer():
    """Get the current tracer instance"""
    global _tracer, _simple_tracer
    
    if OPENTELEMETRY_AVAILABLE and _tracer:
        return _tracer
    elif _simple_tracer:
        return _simple_tracer
    else:
        # Initialize with defaults if not already initialized
        init_tracing()
        return _simple_tracer if _simple_tracer else SimpleTracer()


@contextmanager
def trace_span(name: str, attributes: Optional[Dict[str, Any]] = None):
    """
    Context manager for creating a trace span
    
    Usage:
        with trace_span("operation_name", {"key": "value"}):
            # Your code here
            pass
    """
    tracer = get_tracer()
    
    if OPENTELEMETRY_AVAILABLE and hasattr(tracer, 'start_as_current_span'):
        with tracer.start_as_current_span(name, attributes=attributes) as span:
            yield span
    else:
        # Simple tracer fallback
        span = tracer.start_span(name, attributes)
        try:
            yield span
            tracer.end_span(span, status="OK")
        except Exception as e:
            tracer.end_span(span, status="ERROR")
            logger.error(f"Error in span {name}: {e}", exc_info=True)
            raise


def trace_function(name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
    """
    Decorator for tracing function execution
    
    Usage:
        @trace_function("my_function", {"component": "api"})
        def my_function():
            pass
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            func_name = name or f"{func.__module__}.{func.__name__}"
            with trace_span(func_name, attributes):
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            func_name = name or f"{func.__module__}.{func.__name__}"
            with trace_span(func_name, attributes):
                return func(*args, **kwargs)
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def add_trace_event(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Add an event to the current trace span"""
    tracer = get_tracer()
    
    if OPENTELEMETRY_AVAILABLE and hasattr(tracer, 'get_current_span'):
        span = trace.get_current_span()
        if span:
            span.add_event(name, attributes=attributes or {})
    elif hasattr(tracer, 'add_event'):
        tracer.add_event(name, attributes)


def set_trace_attribute(key: str, value: Any):
    """Set an attribute on the current trace span"""
    tracer = get_tracer()
    
    if OPENTELEMETRY_AVAILABLE and hasattr(tracer, 'get_current_span'):
        span = trace.get_current_span()
        if span:
            span.set_attribute(key, value)
    elif hasattr(tracer, 'set_attribute'):
        tracer.set_attribute(key, value)


def get_trace_id() -> Optional[str]:
    """Get the current trace ID"""
    if OPENTELEMETRY_AVAILABLE:
        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            return format(span.get_span_context().trace_id, '032x')
    return None


def get_span_id() -> Optional[str]:
    """Get the current span ID"""
    if OPENTELEMETRY_AVAILABLE:
        span = trace.get_current_span()
        if span and span.get_span_context().is_valid:
            return format(span.get_span_context().span_id, '016x')
    return None

