import base64

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.services.session_service import get_session_service
from app.vision.utils import encode_image_to_jpeg
from tests.unit.test_detector import create_synthetic_face

AUTH_HEADER = {"X-Tenant-Key": "alorica-live-key-2026"}


@pytest.fixture(autouse=True)
def clean_sessions() -> None:
    service = get_session_service()
    service.reset()


@pytest.fixture
def session_id(client: TestClient) -> str:
    # Register candidate session
    img = create_synthetic_face(320, 240, width=640, height=480)
    selfie_bytes = encode_image_to_jpeg(img)
    response = client.post(
        "/api/v1/fraud/sessions",
        headers=AUTH_HEADER,
        data={"candidate_id": "c_202", "interview_id": "int_777", "consent": "true"},
        files={"selfie_file": ("selfie.jpg", selfie_bytes, "image/jpeg")},
    )
    assert response.status_code == 201
    return str(response.json()["session_id"])


def to_base64(img: np.ndarray) -> str:
    jpeg_bytes = encode_image_to_jpeg(img)
    return base64.b64encode(jpeg_bytes).decode("ascii")


@pytest.mark.integration
def test_analyze_matching_frame(client: TestClient, session_id: str) -> None:
    # Frame identical to candidate selfie
    face_img = create_synthetic_face(320, 240)
    b64_img = to_base64(face_img)

    payload = {
        "batch_id": "b_001",
        "frames": [
            {
                "frame_id": "f_1",
                "timestamp_ms": 1000,
                "image_base64": b64_img,
            }
        ],
    }

    res = client.post(
        f"/api/v1/fraud/sessions/{session_id}/analyze",
        headers=AUTH_HEADER,
        json=payload,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["session_id"] == session_id
    assert data["frames_processed"] == 1
    assert len(data["frame_results"]) == 1

    f_res = data["frame_results"][0]
    assert f_res["faces_detected"] == 1
    det = f_res["detections"][0]
    assert det["identity_match"] is not None
    assert det["identity_match"]["status"] == "MATCH"
    assert data["current_risk"]["risk_score"] == 0.0
    assert len(data["confirmed_events"]) == 0


@pytest.mark.integration
def test_analyze_absence_temporal_confirmation(client: TestClient, session_id: str) -> None:
    empty_room = np.full((480, 640, 3), 160, dtype=np.uint8)
    cv2.rectangle(empty_room, (50, 50), (590, 430), (80, 80, 80), 3)
    cv2.line(empty_room, (50, 200), (590, 200), (40, 40, 40), 2)
    empty_b64 = to_base64(empty_room)

    payload = {
        "batch_id": "b_absence",
        "frames": [
            {"frame_id": "f_1", "timestamp_ms": 1000, "image_base64": empty_b64},
            {"frame_id": "f_2", "timestamp_ms": 4500, "image_base64": empty_b64},  # delta = 3500ms >= 3000ms
        ],
    }

    res = client.post(
        f"/api/v1/fraud/sessions/{session_id}/analyze",
        headers=AUTH_HEADER,
        json=payload,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["frames_processed"] == 2
    assert len(data["confirmed_events"]) == 1

    ev = data["confirmed_events"][0]
    assert ev["event_type"] == "FACE_ABSENT"
    assert ev["duration_ms"] == 3500
    assert data["current_risk"]["risk_score"] == 20.0


@pytest.mark.integration
def test_analyze_multiple_faces_temporal_confirmation(client: TestClient, session_id: str) -> None:
    # Generate frame with 2 faces
    multi_img = np.zeros((480, 800, 3), dtype=np.uint8)
    multi_img[:] = (200, 200, 200)
    for cx in [220, 580]:
        cv2.ellipse(multi_img, (cx, 240), (90, 130), 0, 0, 360, (180, 190, 230), -1)
        cv2.circle(multi_img, (cx - 35, 200), 14, (50, 50, 50), -1)
        cv2.circle(multi_img, (cx + 35, 200), 14, (50, 50, 50), -1)
        cv2.circle(multi_img, (cx, 240), 9, (100, 100, 100), -1)
        cv2.ellipse(multi_img, (cx, 300), (35, 14), 0, 0, 360, (40, 40, 150), -1)

    multi_b64 = to_base64(multi_img)

    payload = {
        "batch_id": "b_multi",
        "frames": [
            {"frame_id": "f_m1", "timestamp_ms": 1000, "image_base64": multi_b64},
            {"frame_id": "f_m2", "timestamp_ms": 3200, "image_base64": multi_b64},  # delta = 2200ms >= 2000ms
        ],
    }

    res = client.post(
        f"/api/v1/fraud/sessions/{session_id}/analyze",
        headers=AUTH_HEADER,
        json=payload,
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["confirmed_events"]) == 1
    assert data["confirmed_events"][0]["event_type"] == "MULTIPLE_FACES"

    # Verify consolidated fraud report
    report_res = client.get(
        f"/api/v1/fraud/sessions/{session_id}/report",
        headers=AUTH_HEADER,
    )
    assert report_res.status_code == 200
    report_data = report_res.json()
    assert report_data["total_events"] == 1
    assert report_data["risk_assessment"]["risk_score"] > 0.0


@pytest.mark.integration
def test_analyze_exceeds_max_batch_size(client: TestClient, session_id: str) -> None:
    blank_b64 = to_base64(np.zeros((100, 100, 3), dtype=np.uint8))
    # 11 frames exceeds max 10
    payload = {
        "batch_id": "b_oversized",
        "frames": [
            {"frame_id": f"f_{i}", "timestamp_ms": 1000 + i * 100, "image_base64": blank_b64}
            for i in range(11)
        ],
    }
    res = client.post(
        f"/api/v1/fraud/sessions/{session_id}/analyze",
        headers=AUTH_HEADER,
        json=payload,
    )
    assert res.status_code == 422
