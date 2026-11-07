import base64

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.session_service import get_session_service
from app.vision.utils import encode_image_to_jpeg
from tests.unit.test_detector import create_synthetic_face

ALORICA_AUTH = {"X-Tenant-Key": "alorica-live-key-2026"}
SAGILITY_AUTH = {"X-Tenant-Key": "sagility-live-key-2026"}
MASTEK_AUTH = {"X-Tenant-Key": "mastek-live-key-2026"}


@pytest.fixture(autouse=True)
def clean_state():
    service = get_session_service()
    service.reset()


@pytest.fixture
def synthetic_selfie_bytes() -> bytes:
    img = create_synthetic_face(320, 240, width=640, height=480)
    return encode_image_to_jpeg(img)


@pytest.fixture
def synthetic_frame_base64(synthetic_selfie_bytes: bytes) -> str:
    return base64.b64encode(synthetic_selfie_bytes).decode("utf-8")


def test_missing_credentials_returns_401(synthetic_selfie_bytes: bytes):
    """Endpoints reject requests lacking API keys with 401 Unauthorized."""
    client = TestClient(app)
    resp = client.post(
        "/api/v1/fraud/sessions",
        data={"candidate_id": "c1", "interview_id": "i1", "consent": "true"},
        files={"selfie_file": ("selfie.jpg", synthetic_selfie_bytes, "image/jpeg")},
    )
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers


def test_invalid_api_key_returns_403(synthetic_selfie_bytes: bytes):
    """Endpoints reject unknown or tampered API keys with 403 Forbidden."""
    client = TestClient(app)
    resp = client.post(
        "/api/v1/fraud/sessions",
        headers={"X-Tenant-Key": "unauthorized-hacker-key"},
        data={"candidate_id": "c1", "interview_id": "i1", "consent": "true"},
        files={"selfie_file": ("selfie.jpg", synthetic_selfie_bytes, "image/jpeg")},
    )
    assert resp.status_code == 403
    assert "Invalid or unauthorized" in resp.text


def test_bearer_token_authorization(synthetic_selfie_bytes: bytes):
    """Authorization: Bearer <key> is fully supported as alternative to X-Tenant-Key."""
    client = TestClient(app)
    resp = client.post(
        "/api/v1/fraud/sessions",
        headers={"Authorization": "Bearer alorica-live-key-2026"},
        data={"candidate_id": "cand_bearer_01", "interview_id": "int_b1", "consent": "true"},
        files={"selfie_file": ("selfie.jpg", synthetic_selfie_bytes, "image/jpeg")},
    )
    assert resp.status_code == 201
    assert resp.json()["candidate_id"] == "cand_bearer_01"


def test_cross_tenant_spoofing_prevented(synthetic_selfie_bytes: bytes):
    """Passing a tenant_id not matching the authenticated API key triggers 403 Forbidden."""
    client = TestClient(app)
    # Alorica credentials attempting to register on behalf of Sagility
    resp = client.post(
        "/api/v1/fraud/sessions",
        headers=ALORICA_AUTH,
        data={
            "candidate_id": "cand_spoof_01",
            "interview_id": "int_s1",
            "consent": "true",
            "tenant_id": "sagility",
        },
        files={"selfie_file": ("selfie.jpg", synthetic_selfie_bytes, "image/jpeg")},
    )
    assert resp.status_code == 403
    assert "Cross-tenant access forbidden" in resp.text


def test_cross_tenant_session_read_isolation(synthetic_selfie_bytes: bytes):
    """Tenant B cannot read or query sessions registered by Tenant A (returns 404)."""
    client = TestClient(app)

    # 1. Alorica creates a session
    reg_resp = client.post(
        "/api/v1/fraud/sessions",
        headers=ALORICA_AUTH,
        data={"candidate_id": "cand_alo_01", "interview_id": "int_alo_01", "consent": "true"},
        files={"selfie_file": ("selfie.jpg", synthetic_selfie_bytes, "image/jpeg")},
    )
    assert reg_resp.status_code == 201
    session_id = reg_resp.json()["session_id"]

    # 2. Alorica can read the session
    alo_read = client.get(f"/api/v1/fraud/sessions/{session_id}", headers=ALORICA_AUTH)
    assert alo_read.status_code == 200

    # 3. Sagility attempts to read Alorica's session -> Must be 404 Not Found
    sag_read = client.get(f"/api/v1/fraud/sessions/{session_id}", headers=SAGILITY_AUTH)
    assert sag_read.status_code == 404

    # 4. Sagility attempts to read Alorica's fraud report -> Must be 404 Not Found
    sag_report = client.get(f"/api/v1/fraud/sessions/{session_id}/report", headers=SAGILITY_AUTH)
    assert sag_report.status_code == 404


def test_cross_tenant_analysis_isolation(synthetic_selfie_bytes: bytes, synthetic_frame_base64: str):
    """Tenant B cannot analyze frames against Tenant A's session."""
    client = TestClient(app)

    # 1. Alorica registers session
    reg_resp = client.post(
        "/api/v1/fraud/sessions",
        headers=ALORICA_AUTH,
        data={"candidate_id": "cand_alo_02", "interview_id": "int_alo_02", "consent": "true"},
        files={"selfie_file": ("selfie.jpg", synthetic_selfie_bytes, "image/jpeg")},
    )
    session_id = reg_resp.json()["session_id"]

    # 2. Sagility attempts to analyze frames on Alorica's session
    analyze_payload = {
        "batch_id": "batch_cross_01",
        "frames": [{"frame_id": "f1", "timestamp_ms": 1000, "image_base64": synthetic_frame_base64}],
    }
    sag_resp = client.post(
        f"/api/v1/fraud/sessions/{session_id}/analyze",
        headers=SAGILITY_AUTH,
        json=analyze_payload,
    )
    assert sag_resp.status_code == 404


def test_tenant_profile_policy_customization(synthetic_selfie_bytes: bytes):
    """Verifies that sessions dynamically inherit tenant-specific event debounces and weights."""
    client = TestClient(app)
    session_service = get_session_service()

    # Sagility session (stricter multiple-face debounce of 1500ms)
    sag_reg = client.post(
        "/api/v1/fraud/sessions",
        headers=SAGILITY_AUTH,
        data={"candidate_id": "cand_sag_cfg", "interview_id": "int_sag_cfg", "consent": "true"},
        files={"selfie_file": ("selfie.jpg", synthetic_selfie_bytes, "image/jpeg")},
    )
    sag_sid = sag_reg.json()["session_id"]
    sag_session = session_service.get_session(sag_sid, "sagility")
    assert sag_session.event_engine.multiple_faces_debounce_ms == 1500

    # Mastek session (stricter face absence debounce of 2500ms)
    mastek_reg = client.post(
        "/api/v1/fraud/sessions",
        headers=MASTEK_AUTH,
        data={"candidate_id": "cand_mas_cfg", "interview_id": "int_mas_cfg", "consent": "true"},
        files={"selfie_file": ("selfie.jpg", synthetic_selfie_bytes, "image/jpeg")},
    )
    mastek_sid = mastek_reg.json()["session_id"]
    mastek_session = session_service.get_session(mastek_sid, "mastek")
    assert mastek_session.event_engine.face_absent_debounce_ms == 2500
