import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.session_service import get_session_service
from app.vision.utils import encode_image_to_jpeg
from tests.unit.test_detector import create_synthetic_face

AUTH_HEADER = {"X-Tenant-Key": "enterprise-a-key-2026"}
ALT_AUTH = {"X-Tenant-Key": "enterprise-b-key-2026"}


@pytest.fixture(autouse=True)
def clean_state():
    service = get_session_service()
    service.reset()


@pytest.fixture
def synthetic_selfie_bytes() -> bytes:
    img = create_synthetic_face(320, 240, width=640, height=480)
    return encode_image_to_jpeg(img)


def test_dashboard_ui_serves_html():
    """Verifies that root and /ui routes serve the embedded interactive dashboard."""
    client = TestClient(app)

    resp_root = client.get("/")
    assert resp_root.status_code == 200
    assert "text/html" in resp_root.headers["content-type"]
    assert "Face Fraud Detection" in resp_root.text

    resp_ui = client.get("/ui")
    assert resp_ui.status_code == 200
    assert "text/html" in resp_ui.headers["content-type"]
    assert "Snap Baseline Selfie" in resp_ui.text


def test_matplotlib_analytics_chart_rendering(synthetic_selfie_bytes: bytes):
    """Verifies that the server renders dynamic Matplotlib PNG graphics for session telemetry."""
    client = TestClient(app)

    # 1. Register candidate session
    reg = client.post(
        "/api/v1/fraud/sessions",
        headers=AUTH_HEADER,
        data={"candidate_id": "c_chart_01", "interview_id": "i_chart_01", "consent": "true"},
        files={"selfie_file": ("selfie.jpg", synthetic_selfie_bytes, "image/jpeg")},
    )
    assert reg.status_code == 201
    session_id = reg.json()["session_id"]

    # 2. Query Matplotlib graphic endpoint
    chart_resp = client.get(
        f"/api/v1/fraud/sessions/{session_id}/analytics/chart",
        headers=AUTH_HEADER,
    )
    assert chart_resp.status_code == 200
    assert chart_resp.headers["content-type"] == "image/png"
    # Verify standard PNG file signature
    assert chart_resp.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(chart_resp.content) > 5000


def test_cross_tenant_chart_isolation(synthetic_selfie_bytes: bytes):
    """Tenant B cannot generate or access Tenant A's telemetry graphics."""
    client = TestClient(app)

    reg = client.post(
        "/api/v1/fraud/sessions",
        headers=AUTH_HEADER,
        data={"candidate_id": "c_alo_chart", "interview_id": "i_alo_chart", "consent": "true"},
        files={"selfie_file": ("selfie.jpg", synthetic_selfie_bytes, "image/jpeg")},
    )
    session_id = reg.json()["session_id"]

    # Sagility attempts to access Alorica's chart
    forbidden_resp = client.get(
        f"/api/v1/fraud/sessions/{session_id}/analytics/chart",
        headers=ALT_AUTH,
    )
    assert forbidden_resp.status_code == 404
