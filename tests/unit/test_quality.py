import cv2
import numpy as np
import pytest

from app.schemas.vision import BoundingBox, FaceDetection, Landmarks, Point
from app.vision.quality import QualityAssessor
from tests.unit.test_detector import create_synthetic_face


@pytest.fixture
def assessor() -> QualityAssessor:
    return QualityAssessor(
        blur_threshold=60.0,
        min_brightness=40.0,
        max_brightness=220.0,
        min_contrast=15.0,
        min_face_ratio=0.015,
    )


@pytest.mark.unit
def test_quality_normal_face_passes(assessor: QualityAssessor) -> None:
    img = create_synthetic_face(320, 240, width=640, height=480)
    face = FaceDetection(
        bbox=BoundingBox(x=220, y=100, width=200, height=280),
        landmarks=Landmarks(
            right_eye=Point(x=280, y=200),
            left_eye=Point(x=360, y=200),
            nose_tip=Point(x=320, y=240),
            right_mouth_corner=Point(x=280, y=300),
            left_mouth_corner=Point(x=360, y=300),
        ),
        confidence=0.95,
        raw_face=[220, 100, 200, 280, 280, 200, 360, 200, 320, 240, 280, 300, 360, 300, 0.95],
    )
    assessment = assessor.evaluate(img, face)
    assert assessment.is_acceptable is True
    assert assessment.is_blurry is False
    assert assessment.is_underexposed is False
    assert assessment.is_overexposed is False
    assert assessment.is_face_too_small is False
    assert len(assessment.quality_issues) == 0


@pytest.mark.unit
def test_quality_blurry_image(assessor: QualityAssessor) -> None:
    img = create_synthetic_face(320, 240)
    # Apply severe Gaussian blur
    blurry = cv2.GaussianBlur(img, (45, 45), 25.0)
    assessment = assessor.evaluate(blurry)

    assert assessment.is_blurry is True
    assert assessment.is_acceptable is False
    assert any("blurry" in issue.lower() for issue in assessment.quality_issues)


@pytest.mark.unit
def test_quality_underexposed_image(assessor: QualityAssessor) -> None:
    dark = np.full((480, 640, 3), 20, dtype=np.uint8)
    assessment = assessor.evaluate(dark)

    assert assessment.is_underexposed is True
    assert assessment.is_acceptable is False
    assert any("underexposed" in issue.lower() for issue in assessment.quality_issues)


@pytest.mark.unit
def test_quality_overexposed_image(assessor: QualityAssessor) -> None:
    bright = np.full((480, 640, 3), 240, dtype=np.uint8)
    assessment = assessor.evaluate(bright)

    assert assessment.is_overexposed is True
    assert assessment.is_acceptable is False
    assert any("overexposed" in issue.lower() for issue in assessment.quality_issues)


@pytest.mark.unit
def test_quality_face_too_small(assessor: QualityAssessor) -> None:
    img = np.full((1000, 1000, 3), 150, dtype=np.uint8)
    # Face of only 20x20 in a 1000x1000 image (0.04% of frame)
    tiny_face = FaceDetection(
        bbox=BoundingBox(x=100, y=100, width=20, height=20),
        landmarks=Landmarks(
            right_eye=Point(x=105, y=105),
            left_eye=Point(x=115, y=105),
            nose_tip=Point(x=110, y=110),
            right_mouth_corner=Point(x=106, y=115),
            left_mouth_corner=Point(x=114, y=115),
        ),
        confidence=0.8,
        raw_face=[],
    )
    assessment = assessor.evaluate(img, tiny_face)
    assert assessment.is_face_too_small is True
    assert assessment.is_acceptable is False


@pytest.mark.unit
def test_selfie_side_face_rejected(assessor: QualityAssessor) -> None:
    img = create_synthetic_face(320, 240, width=640, height=480)
    # Side face: nose is strongly displaced to the right (profile / yaw angle)
    side_face = FaceDetection(
        bbox=BoundingBox(x=220, y=100, width=200, height=280),
        landmarks=Landmarks(
            right_eye=Point(x=250, y=200),
            left_eye=Point(x=390, y=200),
            nose_tip=Point(x=380, y=240),  # Displaced close to left eye
            right_mouth_corner=Point(x=270, y=300),
            left_mouth_corner=Point(x=385, y=300),
        ),
        confidence=0.90,
        raw_face=[],
    )
    assessment = assessor.evaluate(img, side_face, is_selfie=True)
    assert assessment.is_acceptable is False
    assert assessment.is_occluded is True
    assert any("side" in issue.lower() or "turned" in issue.lower() for issue in assessment.quality_issues)


@pytest.mark.unit
def test_selfie_half_covered_face_rejected(assessor: QualityAssessor) -> None:
    img = create_synthetic_face(320, 240, width=640, height=480)
    # Half-covered face: compressed eye span relative to width (one side covered by hand/paper)
    covered_face = FaceDetection(
        bbox=BoundingBox(x=200, y=100, width=250, height=280),
        landmarks=Landmarks(
            right_eye=Point(x=280, y=200),
            left_eye=Point(x=320, y=200),  # Compressed eye span (40px vs 250px box = 0.16)
            nose_tip=Point(x=300, y=240),
            right_mouth_corner=Point(x=285, y=300),
            left_mouth_corner=Point(x=315, y=300),
        ),
        confidence=0.85,
        raw_face=[],
    )
    assessment = assessor.evaluate(img, covered_face, is_selfie=True)
    assert assessment.is_acceptable is False
    assert assessment.is_occluded is True
    assert any("covered" in issue.lower() for issue in assessment.quality_issues)

