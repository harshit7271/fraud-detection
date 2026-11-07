"""
FACEGUARD AI - Locust Load & Performance Benchmark Suite
Simulates concurrent candidate proctoring streams, biometric inferences,
executive dashboard queries, and Prometheus observability scraping.
"""
import base64
import random
import time
import uuid

import cv2
import numpy as np
from locust import HttpUser, between, tag, task


def generate_face_frame(scale: float = 1.0, offset_x: int = 0) -> str:
    """Generates a synthetic JPEG base64 frame for streaming analysis."""
    width, height = 640, 480
    cx, cy = 320 + offset_x, 240
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = (210, 210, 210)

    face_w = int(90 * scale)
    face_h = int(130 * scale)
    eye_r = max(2, int(14 * scale))
    eye_offset = int(35 * scale)

    # Face contour
    cv2.ellipse(img, (cx, cy), (face_w, face_h),
                0, 0, 360, (180, 190, 230), -1)
    # Eyes
    cv2.circle(img, (cx - eye_offset, cy - int(40 * scale)),
               eye_r, (40, 40, 40), -1)
    cv2.circle(img, (cx + eye_offset, cy - int(40 * scale)),
               eye_r, (40, 40, 40), -1)
    # Nose
    cv2.circle(img, (cx, cy), max(2, int(9 * scale)), (80, 80, 80), -1)
    # Mouth
    cv2.ellipse(img, (cx, cy + int(60 * scale)), (max(4, int(35 * scale)),
                max(2, int(14 * scale))), 0, 0, 360, (30, 30, 140), -1)

    _, encoded = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    return base64.b64encode(encoded.tobytes()).decode("utf-8")


def generate_selfie_bytes() -> bytes:
    """Generates a clean synthetic selfie image in JPEG format."""
    width, height = 640, 480
    cx, cy = 320, 240
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = (215, 215, 215)
    cv2.ellipse(img, (cx, cy), (95, 135), 0, 0, 360, (180, 190, 230), -1)
    cv2.circle(img, (cx - 35, cy - 40), 14, (40, 40, 40), -1)
    cv2.circle(img, (cx + 35, cy - 40), 14, (40, 40, 40), -1)
    cv2.circle(img, (cx, cy), 9, (80, 80, 80), -1)
    cv2.ellipse(img, (cx, cy + 60), (35, 14), 0, 0, 360, (30, 30, 140), -1)
    _, encoded = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return encoded.tobytes()


TENANT_KEYS = [
    "alorica-live-key-2026",
    "sagility-live-key-2026",
    "mastek-live-key-2026",
]


class CandidateProctoringUser(HttpUser):
    """
    Simulates a live candidate undergoing an interview session:
    1. Registers candidate session with a reference selfie.
    2. Streams continuous video frames (normal, micro-movement, absent).
    3. Retrieves proctoring report and risk evaluation.
    """
    wait_time = between(0.8, 1.2)  # 1 FPS proctoring cadence
    weight = 5

    def on_start(self) -> None:
        self.tenant_key = random.choice(TENANT_KEYS)
        self.headers = {
            "X-Tenant-Key": self.tenant_key,
            "X-Correlation-ID": str(uuid.uuid4()),
        }
        self.candidate_id = f"cand_bench_{uuid.uuid4().hex[:6]}"
        self.interview_id = f"int_bench_{uuid.uuid4().hex[:6]}"
        self.session_id: str | None = None
        self.frame_index = 0
        self.selfie_bytes = generate_selfie_bytes()
        self._register()

    def _register(self) -> None:
        """Register the proctoring session on startup."""
        files = {
            "selfie_file": ("selfie.jpg", self.selfie_bytes, "image/jpeg"),
        }
        data = {
            "candidate_id": self.candidate_id,
            "interview_id": self.interview_id,
            "consent": "true",
        }
        with self.client.post(
            "/api/v1/fraud/sessions",
            headers=self.headers,
            data=data,
            files=files,
            name="/api/v1/fraud/sessions [Register]",
            catch_response=True,
        ) as response:
            if response.status_code == 201:
                res_data = response.json()
                self.session_id = res_data.get("session_id")
                response.success()
            else:
                response.failure(
                    f"Registration failed: {response.status_code} {response.text}")

    @task(8)
    @tag("stream")
    def stream_frame_analysis(self) -> None:
        """High-frequency frame analysis (CV detection + SFace matching + Temporal Engine)."""
        if not self.session_id:
            return

        self.frame_index += 1
        jitter_x = random.randint(-15, 15)
        frame_b64 = generate_face_frame(scale=1.0, offset_x=jitter_x)
        timestamp_ms = int(time.time() * 1000)

        payload = {
            "batch_id": f"batch_{uuid.uuid4().hex[:8]}",
            "frames": [
                {
                    "frame_id": f"frm_{self.frame_index}",
                    "timestamp_ms": timestamp_ms,
                    "image_base64": frame_b64,
                }
            ],
            "client_metadata": {
                "source": "locust_benchmark",
            },
        }

        with self.client.post(
            f"/api/v1/fraud/sessions/{self.session_id}/analyze",
            headers=self.headers,
            json=payload,
            name="/api/v1/fraud/sessions/{id}/analyze",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(
                    f"Frame analysis failed: {response.status_code} {response.text[:100]}")

    @task(1)
    @tag("telemetry")
    def get_session_status(self) -> None:
        """Query ongoing risk score and active fraud status."""
        if not self.session_id:
            return

        with self.client.get(
            f"/api/v1/fraud/sessions/{self.session_id}",
            headers=self.headers,
            name="/api/v1/fraud/sessions/{id}",
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(
                    f"Session query failed: {response.status_code}")


class DashboardTelemetryUser(HttpUser):
    """
    Simulates enterprise proctoring administrators viewing real-time
    dashboards, filtered session lists, and forensic reports.
    """
    wait_time = between(2.0, 5.0)
    weight = 2

    def on_start(self) -> None:
        self.tenant_key = random.choice(TENANT_KEYS)
        self.headers = {"X-Tenant-Key": self.tenant_key}

    @task(3)
    @tag("dashboard")
    def list_tenant_sessions(self) -> None:
        """Polls active sessions list for the executive dashboard table."""
        self.client.get(
            "/api/v1/fraud/sessions",
            headers=self.headers,
            name="/api/v1/fraud/sessions [List]",
        )

    @task(1)
    @tag("ui")
    def load_dashboard_pages(self) -> None:
        """Requests static UI templates."""
        self.client.get("/", name="/ [Dashboard UI]")
        self.client.get("/session-details", name="/session-details [UI]")
        self.client.get("/history", name="/history [UI]")


class ObservabilityScraperUser(HttpUser):
    """
    Simulates Prometheus metric scrapers and Kubernetes health probes.
    """
    wait_time = between(1.0, 3.0)
    weight = 1

    @task(3)
    @tag("observability")
    def scrape_metrics(self) -> None:
        """Scrapes standard Prometheus metrics."""
        self.client.get("/metrics", name="/metrics [Prometheus]")

    @task(2)
    @tag("health")
    def health_probes(self) -> None:
        """Executes K8s liveness and readiness probes."""
        self.client.get("/healthz", name="/healthz")
        self.client.get("/readyz", name="/readyz")
