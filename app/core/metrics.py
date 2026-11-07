
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.responses import Response

# 1. HTTP Traffic Metrics
HTTP_REQUESTS_TOTAL = Counter(
    "fraud_http_requests_total",
    "Total HTTP requests handled by the Face Fraud Detection microservice",
    ["method", "endpoint", "status_code", "tenant_id"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "fraud_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint", "tenant_id"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# 2. Computer Vision Pipeline Metrics
FRAMES_PROCESSED_TOTAL = Counter(
    "fraud_frames_processed_total",
    "Total candidate video frames processed across sessions",
    ["tenant_id"],
)

CV_INFERENCE_DURATION_SECONDS = Histogram(
    "fraud_cv_inference_duration_seconds",
    "Processing latency of computer vision pipeline stages in seconds",
    ["stage"],  # "detection", "recognition_embedding", "tracking", "quality"
    buckets=(0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5),
)

# 3. Fraud and Session State Metrics
FRAUD_EVENTS_TOTAL = Counter(
    "fraud_events_total",
    "Total confirmed fraud events emitted by the proctoring engine",
    ["tenant_id", "event_type", "severity"],
)

ACTIVE_SESSIONS_GAUGE = Gauge(
    "fraud_active_sessions",
    "Number of currently active candidate proctoring sessions",
    ["tenant_id"],
)


def record_request_metrics(
    method: str,
    endpoint: str,
    status_code: int,
    duration: float,
    tenant_id: str = "anonymous",
) -> None:
    HTTP_REQUESTS_TOTAL.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(status_code),
        tenant_id=tenant_id,
    ).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(
        method=method,
        endpoint=endpoint,
        tenant_id=tenant_id,
    ).observe(duration)


def record_frames_processed(tenant_id: str, count: int) -> None:
    FRAMES_PROCESSED_TOTAL.labels(tenant_id=tenant_id).inc(count)


def record_fraud_event(tenant_id: str, event_type: str, severity: str) -> None:
    FRAUD_EVENTS_TOTAL.labels(
        tenant_id=tenant_id,
        event_type=event_type,
        severity=severity,
    ).inc()


def record_active_sessions(tenant_id: str, count: int) -> None:
    ACTIVE_SESSIONS_GAUGE.labels(tenant_id=tenant_id).set(count)


def get_prometheus_metrics_response() -> Response:
    """Exports raw Prometheus metrics formatted in standard text exposition."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
