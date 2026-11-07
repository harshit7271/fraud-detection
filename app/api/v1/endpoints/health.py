from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.health import HealthResponse, ReadinessResponse

router = APIRouter(tags=["Health & Diagnostics"])


@router.get("/healthz", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Liveness probe to confirm the HTTP server is alive."""
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        version=settings.APP_VERSION,
    )


@router.get("/readyz", response_model=ReadinessResponse)
def readiness_check() -> ReadinessResponse:
    """Readiness probe to confirm external models/dependencies are available."""
    settings = get_settings()
    yunet_ok = settings.resolved_yunet_path.exists()
    sface_ok = settings.resolved_sface_path.exists()
    is_ready = yunet_ok and sface_ok

    return ReadinessResponse(
        status="ready" if is_ready else "not_ready",
        models_loaded=is_ready,
        yunet_available=yunet_ok,
        sface_available=sface_ok,
    )
