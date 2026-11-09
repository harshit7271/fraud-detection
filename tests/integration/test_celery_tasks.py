import base64
from collections.abc import Generator

import pytest
from starlette.testclient import TestClient

from app.core.redis import get_redis_service
from app.main import app
from app.services.session_service import get_session_service
from app.vision.utils import encode_image_to_jpeg
from app.workers.celery_app import (
    celery_app,
    get_worker_detector,
    get_worker_quality_assessor,
    get_worker_recognizer,
    warmup_cv_models,
)
from app.workers.tasks import process_frame_batch_task
from tests.unit.test_detector import create_synthetic_face

AUTH_HEADER = {"X-Tenant-Key": "enterprise-a-key-2026"}
TENANT_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture(autouse=True)
def configure_celery_eager() -> Generator[None, None, None]:
    """Ensure Celery runs tasks locally in eager mode during testing."""
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    yield
    celery_app.conf.task_always_eager = False
    celery_app.conf.task_eager_propagates = False


@pytest.fixture
def synthetic_face_bytes() -> bytes:
    img = create_synthetic_face(320, 240, width=640, height=480)
    return encode_image_to_jpeg(img)


@pytest.fixture
def synthetic_face_base64(synthetic_face_bytes: bytes) -> str:
    return base64.b64encode(synthetic_face_bytes).decode("utf-8")


def test_celery_worker_model_warmup() -> None:
    """Verifies that CV models are warmed up and cached at worker startup."""
    warmup_cv_models()
    detector = get_worker_detector()
    recognizer = get_worker_recognizer()
    quality = get_worker_quality_assessor()

    assert detector is not None
    assert recognizer is not None
    assert quality is not None


def test_process_frame_batch_task_execution(
    synthetic_face_bytes: bytes,
    synthetic_face_base64: str,
) -> None:
    """Verifies direct execution of the Celery batch analysis task."""
    session_service = get_session_service()
    reg = session_service.register_session(
        tenant_id=TENANT_ID,
        candidate_id="cand_celery_01",
        interview_id="int_celery_01",
        consent=True,
        selfie_bytes=synthetic_face_bytes,
    )

    request_payload = {
        "batch_id": "batch_celery_test_01",
        "frames": [
            {
                "frame_id": "frame_01",
                "timestamp_ms": 1000,
                "image_base64": synthetic_face_base64,
            }
        ],
        "client_metadata": {"device": "test_runner"},
    }

    job_id = "test-job-uuid-12345"

    result = process_frame_batch_task(
        session_id=reg.session_id,
        tenant_id=TENANT_ID,
        request_dict=request_payload,
        job_id=job_id,
    )

    assert result is not None
    assert result["batch_id"] == "batch_celery_test_01"
    assert result["frames_processed"] == 1
    assert "current_risk" in result

    # Verify Redis cache status
    import asyncio

    redis = get_redis_service()
    status_data = asyncio.run(redis.get_job_status(job_id))
    assert status_data is not None
    assert status_data["status"] == "COMPLETED"
    assert status_data["frames_count"] == 1
    assert status_data["processing_time_ms"] is not None


def test_async_analyze_api_flow(
    synthetic_face_bytes: bytes,
    synthetic_face_base64: str,
) -> None:
    """Verifies the async_mode=true API route returns 202 Accepted and allows job polling."""
    client = TestClient(app)

    # 1. Register candidate session via multipart upload
    reg_resp = client.post(
        "/api/v1/fraud/sessions",
        headers=AUTH_HEADER,
        data={
            "candidate_id": "cand_async_flow_02",
            "interview_id": "int_async_flow_02",
            "consent": "true",
        },
        files={"selfie_file": ("selfie.jpg", synthetic_face_bytes, "image/jpeg")},
    )
    assert reg_resp.status_code == 201, reg_resp.text
    session_id = reg_resp.json()["session_id"]

    # 2. Submit batch with async_mode=true
    batch_resp = client.post(
        f"/api/v1/fraud/sessions/{session_id}/analyze?async_mode=true",
        headers=AUTH_HEADER,
        json={
            "batch_id": "batch_async_api_01",
            "frames": [
                {
                    "frame_id": "frame_async_01",
                    "timestamp_ms": 1000,
                    "image_base64": synthetic_face_base64,
                }
            ],
        },
    )

    assert batch_resp.status_code == 202, batch_resp.text
    job_data = batch_resp.json()
    assert "job_id" in job_data
    job_id = job_data["job_id"]
    assert job_data["session_id"] == session_id
    assert job_data["frames_count"] == 1

    # 3. Query job status endpoint
    poll_resp = client.get(
        f"/api/v1/fraud/jobs/{job_id}",
        headers=AUTH_HEADER,
    )
    assert poll_resp.status_code == 200, poll_resp.text
    poll_data = poll_resp.json()
    assert poll_data["job_id"] == job_id
    assert poll_data["session_id"] == session_id
    # In eager mode, the task executes and populates the status
    assert poll_data["status"] == "COMPLETED"
    assert poll_data["result"] is not None
    assert poll_data["result"]["frames_processed"] == 1


def test_job_not_found_returns_404() -> None:
    """Verifies that polling a non-existent job ID returns 404."""
    client = TestClient(app)
    resp = client.get("/api/v1/fraud/jobs/non-existent-job-id", headers=AUTH_HEADER)
    assert resp.status_code == 404
