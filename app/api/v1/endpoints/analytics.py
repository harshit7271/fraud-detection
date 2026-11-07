from typing import Annotated

from fastapi import APIRouter, Depends, status
from starlette.responses import Response

from app.middleware.auth import TenantContext, get_current_tenant
from app.services.chart_service import ChartService
from app.services.session_service import SessionService, get_session_service

router = APIRouter(prefix="/fraud/sessions", tags=["Session Analytics & Visualizations"])


@router.get(
    "/{session_id}/analytics/chart",
    summary="Generate Dynamic Matplotlib Session Telemetry Graphic",
    status_code=status.HTTP_200_OK,
)
def get_session_analytics_chart(
    session_id: str,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> Response:
    """
    Renders an executive multi-panel Matplotlib graphic visualizing real-time identity
    similarity, risk accumulation, fraud event distribution, and input video quality.
    """
    session = service.get_session(session_id, tenant.tenant_id)

    # Compute event distribution
    event_counts: dict[str, int] = {
        "FACE_ABSENT": 0,
        "MULTIPLE_FACES": 0,
        "IDENTITY_MISMATCH": 0,
        "LOW_QUALITY": 0,
    }
    for ev in session.confirmed_events:
        name = str(ev.event_type)
        event_counts[name] = event_counts.get(name, 0) + 1

    # Extract quality scores
    q = session.reference_quality
    quality_scores = {
        "Blur Score": round(q.blur_score, 1),
        "Luminance": round(q.brightness_score, 1),
        "Contrast": round(q.contrast_score, 1),
    }

    chart_bytes = ChartService.generate_session_analytics_chart(
        session_id=session.session_id,
        tenant_name=tenant.tenant_name,
        event_counts=event_counts,
        quality_scores=quality_scores,
        match_threshold=tenant.profile.face_match_threshold,
        uncertain_threshold=tenant.profile.face_uncertain_threshold,
    )

    return Response(
        content=chart_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Content-Disposition": f"inline; filename=proctoring_analytics_{session_id[:8]}.png",
        },
    )
