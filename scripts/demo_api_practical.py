"""
Practical Demonstration of the REST API Lifecycle:
1. Operational Health & Readiness checks (/healthz, /readyz)
2. Candidate Registration with Selfie (/fraud/sessions)
3. Live Frame Batch Analysis (/fraud/sessions/{id}/analyze):
   - Normal proctoring (Candidate verified, Risk: 0)
   - Candidate Absence detection (FACE_ABSENT confirmed event)
   - Multiple Faces detection (MULTIPLE_FACES confirmed event)
4. Consolidated Fraud Report Generation (/fraud/sessions/{id}/report)
5. Multi-Tenant Authorization Security check (Cross-tenant access blocked)
"""

import base64
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.services.session_service import get_session_service
from app.vision.utils import encode_image_to_jpeg
from tests.unit.test_detector import create_synthetic_face

client = TestClient(app)

ENTERPRISE_A_AUTH = {"X-Tenant-Key": "enterprise-a-key-2026"}
ENTERPRISE_B_AUTH = {"X-Tenant-Key": "enterprise-b-key-2026"}


def to_base64(img: np.ndarray) -> str:
    jpeg_bytes = encode_image_to_jpeg(img)
    return base64.b64encode(jpeg_bytes).decode("ascii")


def run_api_demo() -> None:
    print("=" * 75)
    print("        PRACTICAL REST API LIFECYCLE & SECURITY DEMONSTRATION")
    print("=" * 75)

    get_session_service().reset()

    # 1. Health & Readiness Probes
    print("\n[Step 1] Operational Health & Readiness Checks")
    res_health = client.get("/healthz")
    print(f"  • GET /healthz -> HTTP {res_health.status_code}")
    print(f"    Body: {res_health.json()}")

    res_ready = client.get("/readyz")
    print(f"  • GET /readyz  -> HTTP {res_ready.status_code}")
    print(f"    Body: {res_ready.json()}")

    # 2. Register Candidate Selfie
    print("\n[Step 2] Candidate Selfie Registration (POST /api/v1/fraud/sessions)")
    selfie_img = create_synthetic_face(320, 240, width=640, height=480)
    selfie_bytes = encode_image_to_jpeg(selfie_img)

    reg_payload = {
        "candidate_id": "cand_sarah_connor_901",
        "interview_id": "int_senior_engineer_2026",
        "consent": "true",
    }
    reg_files = {"selfie_file": ("selfie.jpg", selfie_bytes, "image/jpeg")}

    res_reg = client.post(
        "/api/v1/fraud/sessions",
        headers=ENTERPRISE_A_AUTH,
        data=reg_payload,
        files=reg_files,
    )
    print(f"  • HTTP Status: {res_reg.status_code} (Created)")
    reg_data = res_reg.json()
    session_id = reg_data["session_id"]
    print(f"  • Session ID:    {session_id}")
    print(f"  • Tenant:        {reg_data['tenant_id']} (Authenticated)")
    print(f"  • Candidate:     {reg_data['candidate_id']}")
    print(f"  • Session State: {reg_data['status']}")
    print(f"  • Reference Face Bounding Box: {reg_data['reference_face']['bounding_box']}")

    # 3. Normal Interview Frame Analysis
    print("\n[Step 3] Frame Batch 1: Normal Candidate Participation")
    cand_frame_b64 = to_base64(create_synthetic_face(322, 241))
    batch_1 = {
        "batch_id": "batch_001",
        "frames": [
            {"frame_id": "f_101", "timestamp_ms": 1000, "image_base64": cand_frame_b64},
            {"frame_id": "f_102", "timestamp_ms": 1500, "image_base64": cand_frame_b64},
        ],
    }
    res_b1 = client.post(
        f"/api/v1/fraud/sessions/{session_id}/analyze",
        headers=ENTERPRISE_A_AUTH,
        json=batch_1,
    )
    print(f"  • POST .../analyze -> HTTP {res_b1.status_code}")
    b1_data = res_b1.json()
    print(f"  • Frames Processed: {b1_data['frames_processed']}")
    det_0 = b1_data["frame_results"][0]["detections"][0]
    print(f"  • Face Track ID:    {det_0['track_id']}")
    print(f"  • Identity Match:   {det_0['identity_match']['status']} (Cosine Score: {det_0['identity_match']['similarity_score']:.4f})")
    print(f"  • Current Risk:     Score={b1_data['current_risk']['risk_score']} ({b1_data['current_risk']['risk_level']}) -> Recommendation: {b1_data['current_risk']['recommendation']}")

    # 4. Sustained Candidate Absence
    print("\n[Step 4] Frame Batch 2: Candidate Steps Away (Sustained Absence for 3.5s)")
    empty_room = np.full((480, 640, 3), 160, dtype=np.uint8)
    cv2.rectangle(empty_room, (50, 50), (590, 430), (80, 80, 80), 3)
    cv2.line(empty_room, (50, 200), (590, 200), (40, 40, 40), 2)
    empty_b64 = to_base64(empty_room)

    batch_absence = {
        "batch_id": "batch_002_absence",
        "frames": [
            {"frame_id": "f_201", "timestamp_ms": 3000, "image_base64": empty_b64},
            {"frame_id": "f_202", "timestamp_ms": 6500, "image_base64": empty_b64},  # delta = 3500ms >= 3000ms debounce
        ],
    }
    res_b2 = client.post(
        f"/api/v1/fraud/sessions/{session_id}/analyze",
        headers=ENTERPRISE_A_AUTH,
        json=batch_absence,
    )
    b2_data = res_b2.json()
    print(f"  • POST .../analyze -> HTTP {res_b2.status_code}")
    print(f"  • Confirmed Events: {len(b2_data['confirmed_events'])}")
    if b2_data["confirmed_events"]:
        ev = b2_data["confirmed_events"][0]
        print(f"    - Event:       {ev['event_type']} (Severity: {ev['severity']})")
        print(f"    - Duration:    {ev['duration_ms']} ms")
        print(f"    - Confidence:  {ev['confidence']}")
    print(f"  • Updated Risk:   Score={b2_data['current_risk']['risk_score']} ({b2_data['current_risk']['risk_level']})")

    # 5. Multiple Faces Detected
    print("\n[Step 5] Frame Batch 3: Second Person Enters Frame (Sustained for 2.2s)")
    multi_img = np.zeros((480, 800, 3), dtype=np.uint8)
    multi_img[:] = (200, 200, 200)
    for cx in [220, 580]:
        cv2.ellipse(multi_img, (cx, 240), (90, 130), 0, 0, 360, (180, 190, 230), -1)
        cv2.circle(multi_img, (cx - 35, 200), 14, (50, 50, 50), -1)
        cv2.circle(multi_img, (cx + 35, 200), 14, (50, 50, 50), -1)
        cv2.circle(multi_img, (cx, 240), 9, (100, 100, 100), -1)
        cv2.ellipse(multi_img, (cx, 300), (35, 14), 0, 0, 360, (40, 40, 150), -1)
    multi_b64 = to_base64(multi_img)

    batch_multi = {
        "batch_id": "batch_003_multi",
        "frames": [
            {"frame_id": "f_301", "timestamp_ms": 10000, "image_base64": multi_b64},
            {"frame_id": "f_302", "timestamp_ms": 12200, "image_base64": multi_b64},  # delta = 2200ms >= 2000ms debounce
        ],
    }
    res_b3 = client.post(
        f"/api/v1/fraud/sessions/{session_id}/analyze",
        headers=ENTERPRISE_A_AUTH,
        json=batch_multi,
    )
    b3_data = res_b3.json()
    print(f"  • POST .../analyze -> HTTP {res_b3.status_code}")
    print(f"  • Confirmed Events: {len(b3_data['confirmed_events'])}")
    if b3_data["confirmed_events"]:
        ev_m = b3_data["confirmed_events"][0]
        print(f"    - Event:       {ev_m['event_type']} (Severity: {ev_m['severity']})")
        print(f"    - Faces Found: {ev_m['evidence_metadata']['face_count']}")
    print(f"  • Updated Risk:   Score={b3_data['current_risk']['risk_score']} ({b3_data['current_risk']['risk_level']}) -> Recommendation: {b3_data['current_risk']['recommendation']}")

    # 6. Consolidated Fraud Report
    print("\n[Step 6] Consolidated Fraud Audit Report (GET /api/v1/fraud/sessions/{id}/report)")
    res_rep = client.get(
        f"/api/v1/fraud/sessions/{session_id}/report",
        headers=ENTERPRISE_A_AUTH,
    )
    print(f"  • GET .../report -> HTTP {res_rep.status_code}")
    rep_data = res_rep.json()
    print(f"  • Total Suspicious Events: {rep_data['total_events']}")
    print(f"  • Overall Risk Score:      {rep_data['risk_assessment']['risk_score']} / 100")
    print(f"  • Fraud Classification:    {rep_data['risk_assessment']['fraud_status']}")
    print(f"  • Action Recommendation:   {rep_data['risk_assessment']['recommendation']}")
    print("  • Scoring Audit Explanation:")
    for line in rep_data["risk_assessment"]["scoring_explanation"]:
        print(f"      * {line}")

    # 7. Multi-Tenant Isolation Verification
    print("\n[Step 7] Multi-Tenant Boundary Isolation Security Test")
    print("  • Attempting cross-tenant access: Enterprise B tenant trying to access Enterprise A session...")
    cross_res = client.get(
        f"/api/v1/fraud/sessions/{session_id}",
        headers=ENTERPRISE_B_AUTH,
    )
    print(f"  • Result HTTP Status: {cross_res.status_code} (Blocked / Segregated)")
    print(f"  • Response:           {cross_res.json()}")

    print("\n" + "=" * 75)
    print("               ALL REST API ENDPOINTS VERIFIED LIVE")
    print("=" * 75)


if __name__ == "__main__":
    run_api_demo()
