from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.middleware.auth import (
    TenantContext,
    get_current_tenant,
    verify_tenant_boundary,
)
from app.schemas.fraud import FraudEvent
from app.schemas.session import (
    FraudReportResponse,
    SessionDetailResponse,
    SessionRegisterResponse,
)
from app.services.session_service import SessionService, get_session_service
from app.vision.utils import decode_image_bytes

router = APIRouter(prefix="/fraud/sessions", tags=["Session Proctoring"])


@router.post(
    "",
    response_model=SessionRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Interview Session & Reference Selfie",
)
async def register_session(
    candidate_id: Annotated[str, Form(description="Candidate identifier")],
    interview_id: Annotated[str, Form(description="Interview identifier")],
    consent: Annotated[bool, Form(description="Candidate biometric processing consent")],
    selfie_file: Annotated[UploadFile, File(description="Candidate reference selfie (JPEG, PNG, WebP)")],
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    service: Annotated[SessionService, Depends(get_session_service)],
    tenant_id: Annotated[str | None, Form(description="Optional explicit tenant identifier for cross-verification")] = None,
) -> SessionRegisterResponse:
    """
    Registers a new interview session.
    Validates tenant credentials, candidate consent, and selfie quality.
    Detects exactly one face and generates an encrypted reference biometric embedding.
    """
    if tenant_id is not None:
        verify_tenant_boundary(tenant_id, tenant)

    selfie_bytes = await selfie_file.read()
    return service.register_session(
        tenant_id=tenant.tenant_id,
        candidate_id=candidate_id,
        interview_id=interview_id,
        consent=consent,
        selfie_bytes=selfie_bytes,
    )


@router.post(
    "/validate-selfie",
    summary="Pre-validate Candidate Selfie Quality & Face Presence",
    status_code=status.HTTP_200_OK,
)
async def validate_selfie(
    selfie_file: Annotated[UploadFile, File(description="Candidate selfie image")],
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> dict[str, Any]:
    """
    Evaluates selfie image quality, blur, illumination, and face count before registration.
    Provides instant visual feedback to candidate.
    """
    selfie_bytes = await selfie_file.read()
    try:
        image = decode_image_bytes(selfie_bytes)
    except Exception as e:
        return {"valid": False, "faces_detected": 0, "error": f"Invalid image format: {e}"}

    detection = service.detector.detect_selfie(image)
    if detection.count == 0:
        return {
            "valid": False,
            "faces_detected": 0,
            "error": "No face detected in selfie. Please look directly into camera without occluding your face.",
        }
    if detection.count > 1:
        return {
            "valid": False,
            "faces_detected": detection.count,
            "error": f"Multiple faces ({detection.count}) detected. Exactly 1 face is required.",
        }

    primary_face = detection.faces[0]
    if primary_face.confidence < 0.50:
        return {
            "valid": False,
            "faces_detected": 1,
            "blur_score": 0.0,
            "brightness_score": 0.0,
            "contrast_score": 0.0,
            "face_size_ratio": 0.0,
            "is_blurry": False,
            "is_occluded": True,
            "quality_issues": [f"Face confidence too low ({primary_face.confidence:.2f} < 0.50) — partial occlusion"],
            "error": "Face appears partially covered by hands or objects. Please uncover your face and look directly at camera.",
        }

    quality = service.quality_assessor.evaluate(image, primary_face, is_selfie=True)

    return {
        "valid": quality.is_acceptable,
        "faces_detected": 1,
        "blur_score": round(quality.blur_score, 1),
        "brightness_score": round(quality.brightness_score, 1),
        "contrast_score": round(quality.contrast_score, 1),
        "face_size_ratio": round(quality.face_size_ratio, 3),
        "is_blurry": quality.is_blurry,
        "is_occluded": quality.is_occluded,
        "quality_issues": quality.quality_issues,
        "error": None if quality.is_acceptable else "; ".join(quality.quality_issues),
    }


@router.get(
    "/{session_id}",
    response_model=SessionDetailResponse,
    summary="Get Interview Session Details",
)
def get_session_detail(
    session_id: str,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> SessionDetailResponse:
    """
    Retrieves current proctoring session state, verifying tenant ownership.
    """
    return service.get_session_detail(session_id=session_id, tenant_id=tenant.tenant_id)


@router.get(
    "/{session_id}/report",
    response_model=FraudReportResponse,
    summary="Get Consolidated Fraud Report",
)
def get_fraud_report(
    session_id: str,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> FraudReportResponse:
    """
    Generates a structured fraud report containing risk scoring, confirmed events,
    and audit recommendations for the session.
    """
    return service.get_fraud_report(session_id=session_id, tenant_id=tenant.tenant_id)


@router.get(
    "",
    response_model=list[SessionDetailResponse],
    summary="List Interview Sessions for Tenant",
)
def list_sessions(
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> list[SessionDetailResponse]:
    """
    Returns all registered interview sessions for the authenticated tenant.
    """
    return service.list_sessions(tenant_id=tenant.tenant_id)


@router.get(
    "/{session_id}/events",
    response_model=list[FraudEvent],
    summary="Get Session Confirmed Fraud Events",
)
def get_session_events(
    session_id: str,
    tenant: Annotated[TenantContext, Depends(get_current_tenant)],
    service: Annotated[SessionService, Depends(get_session_service)],
) -> list[FraudEvent]:
    """
    Returns chronological confirmed fraud events for the interview session.
    """
    return service.get_session_events(session_id=session_id, tenant_id=tenant.tenant_id)
