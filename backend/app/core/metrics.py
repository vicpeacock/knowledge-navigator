"""
Metrics module for observability
Provides metrics collection for performance, errors, and business metrics
"""
import logging
import time
from typing import Optional, Dict, Any, Callable
from functools import wraps
from collections import defaultdict
from datetime import datetime
import threading

logger = logging.getLogger(__name__)

# Try to import Prometheus, fallback to simple metrics if not available
try:
    from prometheus_client import Counter, Histogram, Gauge, Summary, generate_latest, REGISTRY
    from prometheus_client import CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("Prometheus not available. Using simple metrics fallback.")


class SimpleMetrics:
    """Simple metrics fallback when Prometheus is not available"""
    
    def __init__(self):
        self._lock = threading.Lock()
        self.counters: Dict[str, float] = defaultdict(float)
        self.histograms: Dict[str, list] = defaultdict(list)
        self.gauges: Dict[str, float] = {}
        self.summaries: Dict[str, list] = defaultdict(list)
    
    def increment(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """Increment a counter"""
        with self._lock:
            key = self._make_key(name, labels)
            self.counters[key] += value
    
    def observe(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Observe a value for histogram/summary"""
        with self._lock:
            key = self._make_key(name, labels)
            self.histograms[key].append(value)
            # Keep only last 1000 values to avoid memory issues
            if len(self.histograms[key]) > 1000:
                self.histograms[key] = self.histograms[key][-1000:]
    
    def set(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge value"""
        with self._lock:
            key = self._make_key(name, labels)
            self.gauges[key] = value
    
    def _make_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Create a key from name and labels"""
        if labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            return f"{name}{{{label_str}}}"
        return name
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics as a dictionary"""
        with self._lock:
            return {
                "counters": dict(self.counters),
                "histograms": {
                    k: {
                        "count": len(v),
                        "sum": sum(v),
                        "min": min(v) if v else 0,
                        "max": max(v) if v else 0,
                        "avg": sum(v) / len(v) if v else 0
                    }
                    for k, v in self.histograms.items()
                },
                "gauges": dict(self.gauges)
            }


# Global metrics instance
_metrics: Optional[Any] = None
_simple_metrics: Optional[SimpleMetrics] = None

# Prometheus metrics (if available)
if PROMETHEUS_AVAILABLE:
    _prometheus_counters: Dict[str, Counter] = {}
    _prometheus_histograms: Dict[str, Histogram] = {}
    _prometheus_gauges: Dict[str, Gauge] = {}
    _prometheus_summaries: Dict[str, Summary] = {}
else:
    _prometheus_counters: Dict[str, Any] = {}
    _prometheus_histograms: Dict[str, Any] = {}
    _prometheus_gauges: Dict[str, Any] = {}
    _prometheus_summaries: Dict[str, Any] = {}


def init_metrics():
    """Initialize metrics system"""
    global _simple_metrics
    
    if not PROMETHEUS_AVAILABLE:
        _simple_metrics = SimpleMetrics()
        logger.info("Using simple metrics fallback (Prometheus not available)")
        return False
    
    logger.info("✅ Prometheus metrics initialized")
    return True


def _get_or_create_counter(name: str, description: str = "", labelnames: tuple = ()) -> Any:
    """Get or create a Prometheus counter"""
    if not PROMETHEUS_AVAILABLE:
        return None
    if name not in _prometheus_counters:
        _prometheus_counters[name] = Counter(name, description, labelnames)
    return _prometheus_counters[name]


def _get_or_create_histogram(name: str, description: str = "", labelnames: tuple = ()) -> Any:
    """Get or create a Prometheus histogram"""
    if not PROMETHEUS_AVAILABLE:
        return None
    if name not in _prometheus_histograms:
        _prometheus_histograms[name] = Histogram(
            name, description, labelnames,
            buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
        )
    return _prometheus_histograms[name]


def _get_or_create_gauge(name: str, description: str = "", labelnames: tuple = ()) -> Any:
    """Get or create a Prometheus gauge"""
    if not PROMETHEUS_AVAILABLE:
        return None
    if name not in _prometheus_gauges:
        _prometheus_gauges[name] = Gauge(name, description, labelnames)
    return _prometheus_gauges[name]


def _get_or_create_summary(name: str, description: str = "", labelnames: tuple = ()) -> Any:
    """Get or create a Prometheus summary"""
    if not PROMETHEUS_AVAILABLE:
        return None
    if name not in _prometheus_summaries:
        _prometheus_summaries[name] = Summary(name, description, labelnames)
    return _prometheus_summaries[name]


def increment_counter(name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
    """Increment a counter metric"""
    if PROMETHEUS_AVAILABLE:
        counter = _get_or_create_counter(name, f"Counter for {name}")
        if labels:
            counter.labels(**labels).inc(value)
        else:
            counter.inc(value)
    else:
        if _simple_metrics:
            _simple_metrics.increment(name, value, labels)


def observe_histogram(name: str, value: float, labels: Optional[Dict[str, str]] = None):
    """Observe a value in a histogram"""
    if PROMETHEUS_AVAILABLE:
        histogram = _get_or_create_histogram(name, f"Histogram for {name}")
        if labels:
            histogram.labels(**labels).observe(value)
        else:
            histogram.observe(value)
    else:
        if _simple_metrics:
            _simple_metrics.observe(name, value, labels)


def set_gauge(name: str, value: float, labels: Optional[Dict[str, str]] = None):
    """Set a gauge value"""
    if PROMETHEUS_AVAILABLE:
        gauge = _get_or_create_gauge(name, f"Gauge for {name}")
        if labels:
            gauge.labels(**labels).set(value)
        else:
            gauge.set(value)
    else:
        if _simple_metrics:
            _simple_metrics.set(name, value, labels)


def observe_summary(name: str, value: float, labels: Optional[Dict[str, str]] = None):
    """Observe a value in a summary"""
    if PROMETHEUS_AVAILABLE:
        summary = _get_or_create_summary(name, f"Summary for {name}")
        if labels:
            summary.labels(**labels).observe(value)
        else:
            summary.observe(value)
    else:
        if _simple_metrics:
            _simple_metrics.observe(name, value, labels)


def time_function(metric_name: str, labels: Optional[Dict[str, str]] = None):
    """
    Decorator to measure function execution time
    
    Usage:
        @time_function("api_request_duration", {"endpoint": "/api/sessions"})
        async def my_function():
            pass
    """
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                observe_histogram(metric_name, duration, labels)
                return result
            except Exception as e:
                duration = time.time() - start_time
                observe_histogram(metric_name, duration, labels)
                increment_counter(f"{metric_name}_errors", labels=labels)
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                observe_histogram(metric_name, duration, labels)
                return result
            except Exception as e:
                duration = time.time() - start_time
                observe_histogram(metric_name, duration, labels)
                increment_counter(f"{metric_name}_errors", labels=labels)
                raise
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def get_metrics_export() -> tuple[bytes, str]:
    """
    Get metrics in Prometheus format
    
    Returns:
        Tuple of (metrics_bytes, content_type)
    """
    if PROMETHEUS_AVAILABLE:
        return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
    else:
        if _simple_metrics:
            import json
            metrics_data = _simple_metrics.get_metrics()
            # Convert to Prometheus-like format
            lines = []
            for name, value in metrics_data.get("counters", {}).items():
                lines.append(f"# TYPE {name} counter")
                lines.append(f"{name} {value}")
            for name, stats in metrics_data.get("histograms", {}).items():
                lines.append(f"# TYPE {name} histogram")
                lines.append(f"{name}_count {stats['count']}")
                lines.append(f"{name}_sum {stats['sum']}")
                lines.append(f"{name}_avg {stats['avg']}")
            for name, value in metrics_data.get("gauges", {}).items():
                lines.append(f"# TYPE {name} gauge")
                lines.append(f"{name} {value}")
            
            content = "\n".join(lines).encode('utf-8')
            return content, "text/plain; version=0.0.4"
        else:
            return b"", "text/plain"


# Initialize metrics on import
init_metrics()

