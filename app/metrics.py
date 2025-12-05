"""
Prometheus metrics for monitoring.
Includes counters and latency histograms.
"""
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from typing import Optional

from app.config import Config


# HTTP request counters
http_requests_total = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['path', 'status']
)

# Webhook processing counters
webhook_requests_total = Counter(
    'webhook_requests_total',
    'Total number of webhook requests',
    ['result']
)

# Latency histograms with buckets in milliseconds
request_latency_ms = Histogram(
    'request_latency_ms',
    'Request latency in milliseconds',
    ['path'],
    buckets=[100, 500, 1000, 2500, 5000, 10000]
)


class MetricsCollector:
    """Helper class for collecting metrics."""
    
    @staticmethod
    def record_http_request(path: str, status: int, duration_ms: float) -> None:
        """Record HTTP request metrics."""
        if not Config.ENABLE_METRICS:
            return
        
        http_requests_total.labels(path=path, status=str(status)).inc()
        request_latency_ms.labels(path=path).observe(duration_ms)
    
    @staticmethod
    def record_webhook_request(result: str) -> None:
        """
        Record webhook request metrics.
        
        Args:
            result: One of "created", "duplicate", "invalid_signature", "validation_error"
        """
        if not Config.ENABLE_METRICS:
            return
        
        webhook_requests_total.labels(result=result).inc()


def get_metrics() -> tuple[bytes, str]:
    """
    Get current metrics in Prometheus format.
    
    Returns:
        Tuple of (metrics_data, content_type)
    """
    return generate_latest(), CONTENT_TYPE_LATEST
