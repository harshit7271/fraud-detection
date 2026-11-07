from fastapi import APIRouter
from starlette.responses import Response

from app.core.metrics import get_prometheus_metrics_response

router = APIRouter(tags=["Observability & Metrics"])


@router.get("/metrics", summary="Prometheus Metrics Exposition")
def prometheus_metrics() -> Response:
    """
    Exposes real-time microservice operational, throughput, and fraud detection metrics
    in Prometheus exposition format.
    """
    return get_prometheus_metrics_response()
