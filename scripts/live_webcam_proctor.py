"""
Interactive Live Webcam Proctoring Application.
Opens local webcam feed, renders real-time YuNet detection, facial landmarks,
SFace identity verification, multi-frame tracking, and temporal fraud risk scoring HUD.

Controls:
  [SPACE] or [r] - Capture/Register reference selfie from current face
  [c]           - Clear session & reset proctoring state
  [q] or [ESC]   - Quit live webcam proctoring
"""

import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2

from app.schemas.vision import IdentityStatus
from app.services.event_engine import TemporalEventEngine
from app.services.scoring import RiskScoringEngine
from app.vision.detector import FaceDetector
from app.vision.quality import QualityAssessor
from app.vision.recognizer import FaceRecognizer
from app.vision.tracker import FaceTracker


def main() -> None:
    print("=" * 70)
    print("      INITIALIZING LIVE WEBCAM FRAUD DETECTION MICROSERVICE")
    print("=" * 70)
    print("Loading YuNet Detector and SFace Recognizer...")

    detector = FaceDetector(score_threshold=0.50, min_face_size=50)
    recognizer = FaceRecognizer()
    assessor = QualityAssessor()
    tracker = FaceTracker()
    event_engine = TemporalEventEngine(session_id="live_demo", tenant_id="local_tester")
    scoring_engine = RiskScoringEngine()

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not access default webcam (index 0). Check camera connection.", file=sys.stderr)
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    window_name = "Blink Cloud - Live Face Fraud Detection Proctor"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1280, 720)

    ref_embedding = None
    confirmed_events = []
    fps_history = []
    prev_time = time.time()

    print("\nLive camera feed opened successfully!")
    print("Instructions:")
    print("  * Position your face and press [SPACE] or [r] to register reference selfie.")
    print("  * Test turning away (absence alert after 3s).")
    print("  * Test having a second person enter the frame (multi-face alert after 2s).")
    print("  * Press [c] to reset proctoring.")
    print("  * Press [q] or [ESC] to exit.")

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            print("Failed to grab video frame.")
            break

        current_time = time.time()
        fps = 1.0 / max(1e-4, current_time - prev_time)
        prev_time = current_time
        fps_history.append(fps)
        if len(fps_history) > 30:
            fps_history.pop(0)
        avg_fps = sum(fps_history) / len(fps_history)

        timestamp_ms = int(current_time * 1000)
        h, w = frame.shape[:2]

        # 1. Detection
        det_result = detector.detect(frame)
        primary_face = det_result.primary_face

        # 2. Quality Assessment
        quality = assessor.evaluate(frame, primary_face)

        # 3. Tracking
        tracked_faces = tracker.update(det_result.faces, timestamp_ms)

        # 4. Identity Verification
        primary_identity_status = None
        primary_sim_score = None

        if ref_embedding is not None and quality.is_acceptable and tracked_faces:
            for tracked in tracked_faces:
                if not tracked.is_identity_cached or tracked.similarity_score is None:
                    try:
                        from app.schemas.vision import FaceDetection
                        det_obj = FaceDetection(
                            bbox=tracked.bbox,
                            landmarks=tracked.landmarks,
                            confidence=tracked.confidence,
                            raw_face=tracked.raw_face,
                        )
                        cur_emb = recognizer.extract_embedding(frame, det_obj)
                        match_res = recognizer.verify(cur_emb, ref_embedding)
                        tracked.verified_identity_status = match_res.status
                        tracked.similarity_score = match_res.similarity_score
                    except Exception:
                        pass

                if primary_identity_status is None and tracked.verified_identity_status:
                    primary_identity_status = tracked.verified_identity_status
                    primary_sim_score = tracked.similarity_score

        # 5. Temporal Engine & Risk Scoring
        new_events = event_engine.process_observation(
            timestamp_ms=timestamp_ms,
            tracked_faces=tracked_faces,
            quality=quality,
            primary_identity_status=primary_identity_status,
            identity_similarity_score=primary_sim_score,
        )
        if new_events:
            confirmed_events.extend(new_events)

        risk = scoring_engine.calculate_risk(confirmed_events)

        # --- DRAW VISUAL HUD OVERLAY ---
        # Top Dashboard Bar
        cv2.rectangle(frame, (0, 0), (w, 85), (20, 20, 20), -1)

        # Status & Candidate Registration
        if ref_embedding is None:
            status_text = "STATUS: NO REFERENCE SELFIE (Press [SPACE] or [r] to Register)"
            status_color = (0, 165, 255)
        else:
            status_text = "STATUS: PROCTORING ACTIVE (Reference Registered)"
            status_color = (0, 255, 0)
        cv2.putText(frame, status_text, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, status_color, 2)

        # Telemetry & Quality Bar
        telemetry = (
            f"FPS: {avg_fps:.1f}  |  Faces: {len(tracked_faces)}  |  "
            f"Quality: {'PASS' if quality.is_acceptable else 'LOW'} (Blur: {quality.blur_score:.0f}, Lum: {quality.brightness_score:.0f})"
        )
        cv2.putText(frame, telemetry, (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

        # Risk Score Widget (Top Right)
        score_color = (0, 255, 0)
        if risk.risk_score >= 50.0:
            score_color = (0, 0, 255)
        elif risk.risk_score >= 25.0:
            score_color = (0, 165, 255)

        cv2.putText(frame, f"RISK: {risk.risk_score:.0f} / 100", (w - 240, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, score_color, 2)
        cv2.putText(frame, f"BAND: {risk.risk_level.value}", (w - 240, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.55, score_color, 1)

        # Draw Detected Faces & Landmarks
        for tracked in tracked_faces:
            bbox = tracked.bbox
            box_color = (0, 255, 0)
            status_label = f"Track #{tracked.track_id}"

            if ref_embedding is not None and tracked.verified_identity_status is not None:
                sim = tracked.similarity_score or 0.0
                if tracked.verified_identity_status == IdentityStatus.MATCH:
                    box_color = (0, 255, 0)
                    status_label += f" | MATCH ({sim:.2f})"
                elif tracked.verified_identity_status == IdentityStatus.UNCERTAIN:
                    box_color = (0, 165, 255)
                    status_label += f" | UNCERTAIN ({sim:.2f})"
                else:
                    box_color = (0, 0, 255)
                    status_label += f" | MISMATCH ({sim:.2f})"
            elif len(tracked_faces) > 1:
                box_color = (0, 0, 255)

            # Bounding Box
            cv2.rectangle(frame, (bbox.x, bbox.y), (bbox.x2, bbox.y2), box_color, 2)

            # Label Tag
            cv2.rectangle(frame, (bbox.x, max(0, bbox.y - 25)), (bbox.x + len(status_label) * 11, bbox.y), box_color, -1)
            cv2.putText(frame, status_label, (bbox.x + 4, max(18, bbox.y - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (255, 255, 255), 1)

            # 5 Landmarks
            lm = tracked.landmarks
            for px, py, c in [
                (int(lm.right_eye.x), int(lm.right_eye.y), (255, 0, 0)),
                (int(lm.left_eye.x), int(lm.left_eye.y), (255, 0, 0)),
                (int(lm.nose_tip.x), int(lm.nose_tip.y), (0, 255, 255)),
                (int(lm.right_mouth_corner.x), int(lm.right_mouth_corner.y), (0, 0, 255)),
                (int(lm.left_mouth_corner.x), int(lm.left_mouth_corner.y), (0, 0, 255)),
            ]:
                cv2.circle(frame, (px, py), 4, c, -1)

        # Active Alerts Banner (Bottom of Screen)
        active_alerts = []
        if len(tracked_faces) == 0:
            active_alerts.append("ALERT: NO FACE DETECTED (Face Absent)")
        elif len(tracked_faces) > 1:
            active_alerts.append(f"ALERT: {len(tracked_faces)} FACES DETECTED (Multiple Faces)")
        if primary_identity_status == IdentityStatus.MISMATCH:
            active_alerts.append("ALERT: IDENTITY MISMATCH DETECTED")

        if active_alerts:
            cv2.rectangle(frame, (0, h - 50), (w, h), (0, 0, 180), -1)
            cv2.putText(frame, "  |  ".join(active_alerts), (20, h - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        else:
            # Normal bottom footer
            cv2.rectangle(frame, (0, h - 35), (w, h), (30, 30, 30), -1)
            footer_text = f"Confirmed Fraud Events: {len(confirmed_events)}  |  Recommendation: {risk.recommendation.value}  |  Controls: [SPACE] Register Selfie, [c] Reset, [q] Quit"
            cv2.putText(frame, footer_text, (20, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (180, 180, 180), 1)

        cv2.imshow(window_name, frame)

        key = cv2.waitKey(1) & 0xFF
        if key in [ord("q"), 27]:  # 'q' or ESC
            break
        elif key in [ord(" "), ord("r")]:
            if primary_face is not None and quality.is_acceptable:
                ref_embedding = recognizer.extract_embedding(frame, primary_face)
                print(f"[{time.strftime('%H:%M:%S')}] ✓ Reference selfie registered successfully!")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] ⚠ Cannot register selfie: ensure 1 clear face is visible with good quality.")
        elif key == ord("c"):
            ref_embedding = None
            confirmed_events.clear()
            tracker.reset()
            event_engine = TemporalEventEngine(session_id="live_demo", tenant_id="local_tester")
            print(f"[{time.strftime('%H:%M:%S')}] Session reset.")

    cap.release()
    cv2.destroyAllWindows()
    print("Live webcam proctor closed.")


if __name__ == "__main__":
    main()
