"""
FACEGUARD AI — Hugging Face Spaces & Standalone ASGI Application
Combines the production FastAPI microservice, Executive Dashboard UI,
and an interactive Gradio Biometric Lab on free CPU hardware.
"""

from typing import Any

import cv2
import gradio as gr
import numpy as np
from PIL import Image

from app.main import create_application
from app.vision.detector import FaceDetector
from app.vision.liveness import HybridLivenessDetector
from app.vision.quality import QualityAssessor

# Initialize production FastAPI application
app = create_application()

# Initialize vision processors for interactive testing
detector = FaceDetector()
quality_assessor = QualityAssessor()
liveness_detector = HybridLivenessDetector()

# Hugging Face ZeroGPU compatibility wrapper
try:
    import spaces  # type: ignore[import-untyped]
    gpu_decorator = spaces.GPU
except Exception:
    def gpu_decorator(fn=None, **kwargs):  # type: ignore[no-redef]
        if fn is not None:
            return fn
        def dec(f):
            return f
        return dec


@gpu_decorator
def analyze_biometric_image(input_image: np.ndarray[Any, Any] | None) -> tuple[Image.Image | None, dict[str, Any]]:
    """Analyzes a candidate selfie or webcam frame using YuNet, SFace, and Anti-spoof PAD."""
    if input_image is None:
        return None, {"error": "No image provided. Please upload an image or capture a webcam photo."}

    # Convert RGB (from Gradio/PIL) to BGR for OpenCV
    bgr_image = cv2.cvtColor(input_image, cv2.COLOR_RGB2BGR)
    det_result = detector.detect(bgr_image)

    annotated = input_image.copy()
    h, w, _ = input_image.shape

    if not det_result.faces:
        return Image.fromarray(annotated), {
            "faces_detected": 0,
            "status": "NO_FACE_DETECTED",
            "message": "No face found meeting detection threshold. Ensure face is centered and clearly lit.",
        }

    # Evaluate the primary detected face
    primary_face = det_result.faces[0]
    bbox = primary_face.bbox
    landmarks = primary_face.landmarks

    # Evaluate biometric quality and strict alignment / occlusion
    quality = quality_assessor.evaluate(bgr_image, primary_face, is_selfie=True)

    # Evaluate presentation attack detection (chroma, specular reflection, frequency)
    liveness = liveness_detector.evaluate_liveness(bgr_image, primary_face)

    # Draw bounding box on annotated RGB image
    color = (79, 70, 229) if liveness.status.value == "LIVE" else (225, 29, 72)
    cv2.rectangle(
        annotated,
        (int(bbox.x), int(bbox.y)),
        (int(bbox.x + bbox.width), int(bbox.y + bbox.height)),
        color,
        3,
    )

    # Draw 5 YuNet facial landmarks (right eye, left eye, nose tip, right mouth, left mouth)
    pts = [
        (int(landmarks.right_eye.x), int(landmarks.right_eye.y)),
        (int(landmarks.left_eye.x), int(landmarks.left_eye.y)),
        (int(landmarks.nose_tip.x), int(landmarks.nose_tip.y)),
        (int(landmarks.right_mouth.x), int(landmarks.right_mouth.y)),
        (int(landmarks.left_mouth.x), int(landmarks.left_mouth.y)),
    ]
    for pt in pts:
        cv2.circle(annotated, pt, 5, (16, 185, 129), -1)
        cv2.circle(annotated, pt, 7, (255, 255, 255), 1)

    result_summary: dict[str, Any] = {
        "faces_detected": len(det_result.faces),
        "primary_face": {
            "confidence": round(primary_face.confidence, 4),
            "bounding_box": {
                "x": int(bbox.x),
                "y": int(bbox.y),
                "width": int(bbox.width),
                "height": int(bbox.height),
            },
        },
        "quality_gate": {
            "acceptable": quality.is_acceptable,
            "blur_metric (variance)": round(quality.blur_metric, 2),
            "brightness": round(quality.brightness, 2),
            "contrast": round(quality.contrast, 2),
            "is_occluded": quality.is_occluded,
            "issues": quality.quality_issues,
        },
        "liveness_pad": {
            "status": liveness.status.value,
            "confidence": round(liveness.confidence or 0.0, 4),
            "method": liveness.method,
            "metrics": {k: round(v, 4) for k, v in liveness.metrics.items()},
            "reason": liveness.reason,
        },
    }

    return Image.fromarray(annotated), result_summary


# Build Gradio UI Tabs
with gr.Blocks(title="FACEGUARD AI — Enterprise Biometric Proctoring") as demo:
    gr.Markdown(
        """
        # 🛡️ FACEGUARD AI — Proctoring & Biometric Fraud Detection
        **Sub-25ms Edge Face Detection (YuNet ONNX) · 128-D Biometric Embeddings (SFace ONNX) · Multi-Spectral Anti-Spoof Liveness**
        """
    )

    with gr.Tabs():
        with gr.TabItem("🖥️ Executive Proctoring Dashboard"):
            gr.HTML(
                """
                <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; background: #ffffff; padding: 12px 18px; border-radius: 10px; border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
                    <div>
                        <span style="font-weight: 700; color: #1e293b; font-size: 15px;">Executive Light Mode Dashboard</span>
                        <p style="margin: 0; color: #64748b; font-size: 12px;">Real-time video HUD, candidate session logs, and fraud risk analytics.</p>
                    </div>
                    <div style="display: flex; gap: 8px;">
                        <a href="/ui" target="_blank" style="text-decoration: none; padding: 8px 16px; background-color: #4f46e5; color: white; border-radius: 8px; font-weight: 600; font-size: 13px;">Open Fullscreen Dashboard ↗</a>
                        <a href="/monitor" target="_blank" style="text-decoration: none; padding: 8px 16px; background-color: #0f172a; color: white; border-radius: 8px; font-weight: 600; font-size: 13px;">Live Webcam Proctor 🎥</a>
                    </div>
                </div>
                <iframe src="/ui" style="width: 100%; height: 860px; border: 1px solid #cbd5e1; border-radius: 12px; background: white;" allow="camera; microphone"></iframe>
                """
            )

        with gr.TabItem("🧪 Interactive Biometric Lab"):
            gr.Markdown(
                "Upload a photo or capture a frame with your webcam to test edge YuNet 5-landmark alignment, quality evaluation, and multi-spectral anti-spoof liveness."
            )
            with gr.Row():
                with gr.Column(scale=1):
                    img_input = gr.Image(type="numpy", label="Input Candidate Image")
                    analyze_btn = gr.Button("Analyze Biometrics & Liveness", variant="primary")
                with gr.Column(scale=1):
                    annotated_output = gr.Image(type="pil", label="Annotated Bounding Box & Landmarks")
                    json_output = gr.JSON(label="Biometric Diagnostic Telemetry")

            analyze_btn.click(
                fn=analyze_biometric_image,
                inputs=[img_input],
                outputs=[annotated_output, json_output],
            )

        with gr.TabItem("📡 REST API & Health Telemetry"):
            gr.Markdown(
                """
                ### Production Microservice Endpoints
                * 📘 **Swagger Interactive OpenAPI Docs**: [`/docs`](/docs)
                * 🩺 **Kubernetes Liveness Probe**: [`/healthz`](/healthz)
                * 🔍 **Hardware & Model Readiness Probe**: [`/readyz`](/readyz)
                * 📊 **Prometheus Metrics**: [`/metrics`](/metrics)
                * 👥 **Candidate Session Management**: [`/api/v1/fraud/sessions`](/api/v1/fraud/sessions)
                * 📹 **Real-time Frame Biometric Analysis**: [`/api/v1/fraud/sessions/{id}/analyze`](/api/v1/fraud/sessions)
                """
            )

# Integrate all FastAPI proctoring routes & static files into Gradio's internal FastAPI app
demo.app.routes.extend(app.routes)

if __name__ == "__main__":
    demo.launch()
