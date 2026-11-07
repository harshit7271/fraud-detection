"""
Seeds realistic enterprise candidate proctoring sessions into durable JSON storage.
Populates candidates, interviews, and confirmed fraud events for dashboard telemetry.
"""
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path


def create_demo_sessions():
    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    store_file = data_dir / "sessions_store.json"

    now = datetime.now(UTC)

    candidates = [
        {"cid": "cand_492198", "iid": "int_eval_7812", "tenant": "alorica", "events": []},
        {
            "cid": "cand_381042",
            "iid": "int_eval_6541",
            "tenant": "alorica",
            "events": [
                {
                    "event_type": "FACE_ABSENT",
                    "severity": "MEDIUM",
                    "timestamp_ms": int((now - timedelta(minutes=15)).timestamp() * 1000),
                    "duration_ms": 3500,
                    "confidence": 0.95,
                    "evidence_metadata": {"consecutive_absent_frames": 4},
                }
            ],
        },
        {
            "cid": "cand_817290",
            "iid": "int_eval_9103",
            "tenant": "alorica",
            "events": [
                {
                    "event_type": "MULTIPLE_FACES",
                    "severity": "CRITICAL",
                    "timestamp_ms": int((now - timedelta(minutes=22)).timestamp() * 1000),
                    "duration_ms": 4200,
                    "confidence": 0.98,
                    "evidence_metadata": {"max_faces": 2},
                },
                {
                    "event_type": "IDENTITY_MISMATCH",
                    "severity": "HIGH",
                    "timestamp_ms": int((now - timedelta(minutes=20)).timestamp() * 1000),
                    "duration_ms": 3000,
                    "confidence": 0.89,
                    "evidence_metadata": {"similarity_score": 0.18},
                },
            ],
        },
        {"cid": "cand_109283", "iid": "int_eval_3319", "tenant": "alorica", "events": []},
        {
            "cid": "cand_554129",
            "iid": "int_eval_8820",
            "tenant": "alorica",
            "events": [
                {
                    "event_type": "FACE_ABSENT",
                    "severity": "MEDIUM",
                    "timestamp_ms": int((now - timedelta(minutes=35)).timestamp() * 1000),
                    "duration_ms": 3200,
                    "confidence": 0.92,
                    "evidence_metadata": {"consecutive_absent_frames": 3},
                }
            ],
        },
        {"cid": "cand_672911", "iid": "int_eval_4102", "tenant": "alorica", "events": []},
        {
            "cid": "cand_992104",
            "iid": "int_eval_1048",
            "tenant": "alorica",
            "events": [
                {
                    "event_type": "MULTIPLE_FACES",
                    "severity": "CRITICAL",
                    "timestamp_ms": int((now - timedelta(minutes=48)).timestamp() * 1000),
                    "duration_ms": 5000,
                    "confidence": 0.99,
                    "evidence_metadata": {"max_faces": 3},
                }
            ],
        },
        {"cid": "cand_781920", "iid": "int_eval_5501", "tenant": "alorica", "events": []},
        {"cid": "cand_220918", "iid": "int_eval_9482", "tenant": "alorica", "events": []},
        {
            "cid": "cand_612849",
            "iid": "int_eval_7219",
            "tenant": "alorica",
            "events": [
                {
                    "event_type": "FACE_ABSENT",
                    "severity": "MEDIUM",
                    "timestamp_ms": int((now - timedelta(minutes=65)).timestamp() * 1000),
                    "duration_ms": 3400,
                    "confidence": 0.91,
                    "evidence_metadata": {"consecutive_absent_frames": 3},
                }
            ],
        },
        {"cid": "cand_338192", "iid": "int_eval_4490", "tenant": "alorica", "events": []},
        {
            "cid": "cand_847291",
            "iid": "int_eval_6612",
            "tenant": "alorica",
            "events": [
                {
                    "event_type": "MULTIPLE_FACES",
                    "severity": "HIGH",
                    "timestamp_ms": int((now - timedelta(minutes=90)).timestamp() * 1000),
                    "duration_ms": 2800,
                    "confidence": 0.94,
                    "evidence_metadata": {"max_faces": 2},
                }
            ],
        },
    ]

    sessions_dict = {}

    for i, c in enumerate(candidates):
        sid = str(uuid.uuid4())
        created_time = (now - timedelta(minutes=(i * 10 + 5))).isoformat()
        
        events_list = []
        for ev in c["events"]:
            events_list.append({
                "event_id": str(uuid.uuid4()),
                "session_id": sid,
                "tenant_id": c["tenant"],
                "event_type": ev["event_type"],
                "timestamp_ms": ev["timestamp_ms"],
                "duration_ms": ev["duration_ms"],
                "confidence": ev["confidence"],
                "severity": ev["severity"],
                "evidence_metadata": ev["evidence_metadata"],
                "created_at": created_time,
            })

        sessions_dict[sid] = {
            "session_id": sid,
            "tenant_id": c["tenant"],
            "candidate_id": c["cid"],
            "interview_id": c["iid"],
            "consent_recorded": True,
            "status": "ACTIVE",
            "created_at": created_time,
            "reference_bbox": {"x": 220, "y": 100, "width": 200, "height": 280},
            "reference_embedding": {"vector": [0.01 * (j % 10) for j in range(128)], "dimension": 128},
            "reference_quality": {
                "blur_score": 85.0,
                "is_blurry": False,
                "brightness_score": 120.0,
                "is_underexposed": False,
                "is_overexposed": False,
                "contrast_score": 45.0,
                "is_low_contrast": False,
                "face_size_ratio": 0.18,
                "is_face_too_small": False,
                "is_occluded": False,
                "is_acceptable": True,
                "quality_issues": [],
            },
            "confirmed_events": events_list,
        }

    with open(store_file, "w", encoding="utf-8") as f:
        json.dump(sessions_dict, f, indent=2)

    print(f"Successfully seeded {len(sessions_dict)} durable proctoring sessions into {store_file}")


if __name__ == "__main__":
    create_demo_sessions()
