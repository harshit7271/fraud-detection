import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.services.session_service import get_session_service
from app.vision.utils import encode_image_to_jpeg
from tests.unit.test_detector import create_synthetic_face

VALID_AUTH_HEADER = {"X-Tenant-Key": "enterprise-a-key-2026"}
ALT_TENANT_HEADER = {"X-Tenant-Key": "enterprise-b-key-2026"}


@pytest.fixture(autouse=True)
def clean_sessions() -> None:
    service = get_session_service()
    service.reset()


@pytest.fixture
def valid_selfie_bytes() -> bytes:
    img = create_synthetic_face(320, 240, width=640, height=480)
    return encode_image_to_jpeg(img)


@pytest.fixture
def blank_image_bytes() -> bytes:
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    return encode_image_to_jpeg(blank)


@pytest.fixture
def multi_face_image_bytes() -> bytes:
    img = np.zeros((480, 800, 3), dtype=np.uint8)
    img[:] = (200, 200, 200)
    for cx in [220, 580]:
        cv2.ellipse(img, (cx, 240), (90, 130), 0, 0, 360, (180, 190, 230), -1)
        cv2.circle(img, (cx - 35, 200), 14, (50, 50, 50), -1)
        cv2.circle(img, (cx + 35, 200), 14, (50, 50, 50), -1)
        cv2.circle(img, (cx, 240), 9, (100, 100, 100), -1)
        cv2.ellipse(img, (cx, 300), (35, 14), 0, 0, 360, (40, 40, 150), -1)
    return encode_image_to_jpeg(img)


@pytest.fixture
def blurry_image_bytes() -> bytes:
    img = create_synthetic_face(320, 240)
    blurry = cv2.GaussianBlur(img, (45, 45), 25.0)
    return encode_image_to_jpeg(blurry)


@pytest.mark.integration
def test_register_session_auth_missing(client: TestClient, valid_selfie_bytes: bytes) -> None:
    response = client.post(
        "/api/v1/fraud/sessions",
        data={"candidate_id": "c1", "interview_id": "i1", "consent": "true"},
        files={"selfie_file": ("selfie.jpg", valid_selfie_bytes, "image/jpeg")},
    )
    assert response.status_code == 401


@pytest.mark.integration
def test_register_session_auth_invalid(client: TestClient, valid_selfie_bytes: bytes) -> None:
    response = client.post(
        "/api/v1/fraud/sessions",
        headers={"X-Tenant-Key": "invalid-secret-key"},
        data={"candidate_id": "c1", "interview_id": "i1", "consent": "true"},
        files={"selfie_file": ("selfie.jpg", valid_selfie_bytes, "image/jpeg")},
    )
    assert response.status_code == 403


@pytest.mark.integration
def test_register_session_missing_consent(client: TestClient, valid_selfie_bytes: bytes) -> None:
    response = client.post(
        "/api/v1/fraud/sessions",
        headers=VALID_AUTH_HEADER,
        data={"candidate_id": "c1", "interview_id": "i1", "consent": "false"},
        files={"selfie_file": ("selfie.jpg", valid_selfie_bytes, "image/jpeg")},
    )
    assert response.status_code == 400
    assert "CONSENT_REQUIRED" in response.text


@pytest.mark.integration
def test_register_session_no_face_detected(client: TestClient, blank_image_bytes: bytes) -> None:
    response = client.post(
        "/api/v1/fraud/sessions",
        headers=VALID_AUTH_HEADER,
        data={"candidate_id": "c1", "interview_id": "i1", "consent": "true"},
        files={"selfie_file": ("blank.jpg", blank_image_bytes, "image/jpeg")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "NO_FACE_DETECTED"


@pytest.mark.integration
def test_register_session_multiple_faces(client: TestClient, multi_face_image_bytes: bytes) -> None:
    response = client.post(
        "/api/v1/fraud/sessions",
        headers=VALID_AUTH_HEADER,
        data={"candidate_id": "c1", "interview_id": "i1", "consent": "true"},
        files={"selfie_file": ("multi.jpg", multi_face_image_bytes, "image/jpeg")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "MULTIPLE_FACES_DETECTED"


@pytest.mark.integration
def test_register_session_poor_quality(client: TestClient, blurry_image_bytes: bytes) -> None:
    response = client.post(
        "/api/v1/fraud/sessions",
        headers=VALID_AUTH_HEADER,
        data={"candidate_id": "c1", "interview_id": "i1", "consent": "true"},
        files={"selfie_file": ("blurry.jpg", blurry_image_bytes, "image/jpeg")},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "POOR_IMAGE_QUALITY"


@pytest.mark.integration
def test_register_session_success_and_detail(client: TestClient, valid_selfie_bytes: bytes) -> None:
    response = client.post(
        "/api/v1/fraud/sessions",
        headers=VALID_AUTH_HEADER,
        data={"candidate_id": "cand_101", "interview_id": "int_999", "consent": "true"},
        files={"selfie_file": ("selfie.jpg", valid_selfie_bytes, "image/jpeg")},
    )
    assert response.status_code == 201
    reg_data = response.json()
    session_id = reg_data["session_id"]
    assert reg_data["tenant_id"] in ("enterprise-a", "alorica")
    assert reg_data["candidate_id"] == "cand_101"
    assert reg_data["status"] == "INITIALIZED"
    assert reg_data["reference_face"]["face_detected"] is True

    # Get session details
    detail_res = client.get(f"/api/v1/fraud/sessions/{session_id}", headers=VALID_AUTH_HEADER)
    assert detail_res.status_code == 200
    assert detail_res.json()["session_id"] == session_id

    # Cross-tenant access attempt (Sagility attempts to read Alorica session)
    cross_res = client.get(f"/api/v1/fraud/sessions/{session_id}", headers=ALT_TENANT_HEADER)
    assert cross_res.status_code == 404
