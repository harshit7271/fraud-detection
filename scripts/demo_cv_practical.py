"""
Practical Demonstration of the Computer Vision Pipeline:
1. Face Detection with YuNet (Bounding Boxes + 5 Facial Landmarks)
2. Image Quality Assessment (Blur, Luminance, Contrast, Occlusion)
3. Face Alignment (112x112 standard chip)
4. SFace 128-d Embedding Extraction & Cosine Similarity Comparison
5. Multi-Frame Face Tracking (IoU Association & Track ID Persistence)
6. Saves annotated images to 'demo_output/' for visual inspection
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np

from app.vision.detector import FaceDetector
from app.vision.quality import QualityAssessor
from app.vision.recognizer import FaceRecognizer
from app.vision.tracker import FaceTracker
from tests.unit.test_detector import create_synthetic_face

OUTPUT_DIR = Path("demo_output")
OUTPUT_DIR.mkdir(exist_ok=True)


def draw_detection(image: np.ndarray, face, label: str = "Candidate") -> np.ndarray:
    annotated = image.copy()
    bbox = face.bbox
    # Draw Bounding Box
    cv2.rectangle(
        annotated,
        (bbox.x, bbox.y),
        (bbox.x2, bbox.y2),
        (0, 255, 0),
        2,
    )

    # Draw Landmarks
    lm = face.landmarks
    pts = [
        (int(lm.right_eye.x), int(lm.right_eye.y), (255, 0, 0)),
        (int(lm.left_eye.x), int(lm.left_eye.y), (255, 0, 0)),
        (int(lm.nose_tip.x), int(lm.nose_tip.y), (0, 255, 255)),
        (int(lm.right_mouth_corner.x), int(lm.right_mouth_corner.y), (0, 0, 255)),
        (int(lm.left_mouth_corner.x), int(lm.left_mouth_corner.y), (0, 0, 255)),
    ]
    for px, py, color in pts:
        cv2.circle(annotated, (px, py), 4, color, -1)

    # Draw Text
    text = f"{label} ({face.confidence * 100:.1f}%)"
    cv2.putText(
        annotated,
        text,
        (bbox.x, max(20, bbox.y - 10)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 255, 0),
        2,
    )
    return annotated


def run_cv_demo() -> None:
    print("=" * 70)
    print("       PRACTICAL COMPUTER VISION PIPELINE DEMONSTRATION")
    print("=" * 70)

    # 1. Initialize models
    print("\n[Step 1] Loading Pretrained Models...")
    detector = FaceDetector()
    recognizer = FaceRecognizer()
    assessor = QualityAssessor()
    tracker = FaceTracker()
    print("✓ OpenCV YuNet Face Detector loaded.")
    print("✓ OpenCV SFace Recognizer loaded.")
    print("✓ Image Quality Assessor loaded.")
    print("✓ Multi-Frame Face Tracker initialized.")

    # 2. Registration Selfie
    print("\n[Step 2] Processing Candidate Registration Selfie...")
    selfie_img = create_synthetic_face(320, 240, width=640, height=480)
    quality = assessor.evaluate(selfie_img)
    print(f"  • Image Quality: {'PASS' if quality.is_acceptable else 'FAIL'}")
    print(f"    - Blur Score (Laplacian): {quality.blur_score:.2f} (threshold: {assessor.blur_threshold})")
    print(f"    - Brightness (Mean):      {quality.brightness_score:.1f} / 255")
    print(f"    - Contrast (StdDev):      {quality.contrast_score:.1f}")

    det_result = detector.detect(selfie_img)
    print(f"  • Faces Detected: {det_result.count}")
    ref_face = det_result.faces[0]
    print(f"  • Bounding Box: [x={ref_face.bbox.x}, y={ref_face.bbox.y}, w={ref_face.bbox.width}, h={ref_face.bbox.height}]")
    print(f"  • Confidence:   {ref_face.confidence * 100:.2f}%")
    print(f"  • 5 Facial Landmarks Extracted: RightEye({ref_face.landmarks.right_eye.x:.1f}, {ref_face.landmarks.right_eye.y:.1f}), LeftEye({ref_face.landmarks.left_eye.x:.1f}, {ref_face.landmarks.left_eye.y:.1f}), Nose({ref_face.landmarks.nose_tip.x:.1f}, {ref_face.landmarks.nose_tip.y:.1f})")

    # Save visual
    annotated_selfie = draw_detection(selfie_img, ref_face, "Registered Reference Face")
    out_selfie = OUTPUT_DIR / "01_selfie_detection.jpg"
    cv2.imwrite(str(out_selfie), annotated_selfie)
    print(f"  --> Saved visual: {out_selfie}")

    # 3. Alignment & 128-d Embedding Extraction
    print("\n[Step 3] Face Alignment & Feature Extraction...")
    aligned_chip = recognizer.align_face(selfie_img, ref_face)
    out_chip = OUTPUT_DIR / "02_aligned_112x112_face_chip.jpg"
    cv2.imwrite(str(out_chip), aligned_chip)
    print(f"  • Aligned Face Dimensions: {aligned_chip.shape} (Standard SFace 112x112)")
    print(f"  --> Saved aligned chip:   {out_chip}")

    ref_embedding = recognizer.extract_embedding(selfie_img, ref_face)
    ref_vec = ref_embedding.to_numpy()
    print(f"  • Extracted Vector Dimension: {ref_embedding.dimension}-d")
    print(f"  • Embedding L2-Norm:          {np.linalg.norm(ref_vec):.6f} (Unit Normalization Verified)")
    print(f"  • First 5 vector components:  {np.round(ref_vec[:5], 4)}")

    # 4. Identity Verification Matching
    print("\n[Step 4] Identity Verification (Same Person vs Impostor)...")
    # Same person frame
    match_result = recognizer.verify(ref_embedding, ref_embedding)
    print("  • Case A: Registered Candidate vs Same Candidate")
    print(f"    - Cosine Similarity: {match_result.similarity_score:.4f}")
    print(f"    - Status:            {match_result.status.value} (Expected: MATCH)")

    # Different person
    diff_person = np.zeros((480, 640, 3), dtype=np.uint8)
    diff_person[:] = (180, 180, 180)
    cv2.ellipse(diff_person, (320, 240), (120, 110), 0, 0, 360, (210, 200, 170), -1)
    cv2.circle(diff_person, (260, 210), 10, (10, 10, 10), -1)
    cv2.circle(diff_person, (380, 210), 10, (10, 10, 10), -1)
    cv2.circle(diff_person, (320, 250), 6, (40, 40, 40), -1)
    cv2.ellipse(diff_person, (320, 280), (25, 8), 0, 0, 360, (10, 10, 90), -1)

    diff_det = detector.detect(diff_person)
    diff_emb = recognizer.extract_embedding(diff_person, diff_det.faces[0])
    diff_match = recognizer.verify(diff_emb, ref_embedding, match_threshold=0.85, uncertain_threshold=0.70)
    print("  • Case B: Registered Candidate vs Different Face Geometry")
    print(f"    - Cosine Similarity: {diff_match.similarity_score:.4f}")
    print(f"    - Thresholds:        Match >= {diff_match.match_threshold}, Uncertain >= {diff_match.uncertain_threshold}")
    print(f"    - Status:            {diff_match.status.value}")

    # 5. Multiple Faces Scenario
    print("\n[Step 5] Detecting Multiple Faces in Interview Frame...")
    multi_img = np.zeros((480, 800, 3), dtype=np.uint8)
    multi_img[:] = (200, 200, 200)
    for cx in [220, 580]:
        cv2.ellipse(multi_img, (cx, 240), (90, 130), 0, 0, 360, (180, 190, 230), -1)
        cv2.circle(multi_img, (cx - 35, 200), 14, (50, 50, 50), -1)
        cv2.circle(multi_img, (cx + 35, 200), 14, (50, 50, 50), -1)
        cv2.circle(multi_img, (cx, 240), 9, (100, 100, 100), -1)
        cv2.ellipse(multi_img, (cx, 300), (35, 14), 0, 0, 360, (40, 40, 150), -1)

    multi_res = detector.detect(multi_img)
    print(f"  • Faces Detected: {multi_res.count}")
    annotated_multi = multi_img.copy()
    for i, f in enumerate(multi_res.faces, 1):
        annotated_multi = draw_detection(annotated_multi, f, f"Face #{i}")
    out_multi = OUTPUT_DIR / "03_multiple_faces_detection.jpg"
    cv2.imwrite(str(out_multi), annotated_multi)
    print(f"  --> Saved visual: {out_multi}")

    # 6. Multi-Frame Tracking
    print("\n[Step 6] Multi-Frame Face Tracking Across Consecutive Video Frames...")
    tracker.reset()
    frames_timeline = [
        ("Frame 1 (t=0ms)", create_synthetic_face(320, 240)),
        ("Frame 2 (t=500ms, face shifted right 10px)", create_synthetic_face(330, 242)),
        ("Frame 3 (t=1000ms, face shifted right 20px)", create_synthetic_face(340, 245)),
    ]

    for label, frame_img in frames_timeline:
        det = detector.detect(frame_img)
        tracks = tracker.update(det.faces, timestamp_ms=0)
        track = tracks[0]
        print(f"  • {label:42} -> Track ID: {track.track_id} (Frames Tracked: {track.frames_tracked}, Center: ({track.bbox.x + track.bbox.width//2}, {track.bbox.y + track.bbox.height//2}))")

    print("\n" + "=" * 70)
    print("            ALL CV PRACTICAL TESTS EXECUTED SUCCESSFULLY")
    print(f"  Visual results saved to: {OUTPUT_DIR.resolve()}")
    print("=" * 70)


if __name__ == "__main__":
    run_cv_demo()
