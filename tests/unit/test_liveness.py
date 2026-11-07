import numpy as np
import pytest

from app.schemas.vision import BoundingBox, FaceDetection, Landmarks, Point
from app.vision.liveness import HybridLivenessDetector, LivenessStatus, PassiveLivenessInterface


@pytest.fixture
def dummy_face() -> FaceDetection:
    return FaceDetection(
        bbox=BoundingBox(x=50, y=50, width=100, height=100),
        landmarks=Landmarks(
            right_eye=Point(x=70, y=70),
            left_eye=Point(x=130, y=70),
            nose_tip=Point(x=100, y=100),
            right_mouth_corner=Point(x=80, y=130),
            left_mouth_corner=Point(x=120, y=130),
        ),
        confidence=0.95,
        raw_face=[],
    )


@pytest.mark.unit
def test_passive_liveness_interface(dummy_face: FaceDetection) -> None:
    interface = PassiveLivenessInterface()
    img = np.zeros((200, 200, 3), dtype=np.uint8)

    result = interface.evaluate_liveness(img, dummy_face)
    assert result.status == LivenessStatus.NOT_EVALUATED
    assert result.confidence is None
    assert "not prove liveness" in result.reason.lower()


@pytest.mark.unit
def test_hybrid_liveness_live_face(dummy_face: FaceDetection) -> None:
    detector = HybridLivenessDetector()
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    # Natural skin tone in BGR: e.g. B=160, G=180, R=220
    img[50:150, 50:150] = (160, 180, 220)

    result = detector.evaluate_liveness(img, dummy_face)
    assert result.status in (LivenessStatus.LIVE, LivenessStatus.UNCERTAIN)
    assert result.confidence is not None
    assert "metrics" in result.model_dump()


@pytest.mark.unit
def test_hybrid_liveness_screen_glare_spoof(dummy_face: FaceDetection) -> None:
    detector = HybridLivenessDetector(glare_threshold=0.05)
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    img[50:150, 50:150] = (160, 180, 220)
    # Inject specular screen glare hotspot (pure white)
    img[70:110, 70:110] = (255, 255, 255)

    result = detector.evaluate_liveness(img, dummy_face)
    assert result.status == LivenessStatus.SPOOF
    assert any("glare" in r.lower() or "specular" in r.lower() for r in [result.reason])


@pytest.mark.unit
def test_hybrid_liveness_static_photo_spoof(dummy_face: FaceDetection) -> None:
    detector = HybridLivenessDetector()
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    img[50:150, 50:150] = (160, 180, 220)

    # Completely stationary history across frames (zero motion)
    static_history = [dummy_face] * 4
    result = detector.evaluate_liveness(img, dummy_face, history=static_history)
    assert result.status == LivenessStatus.SPOOF
    assert "static photo" in result.reason.lower()

