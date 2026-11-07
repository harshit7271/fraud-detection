import base64

import cv2
import numpy as np
import pytest

from app.core.exceptions import InvalidImageError, ModelLoadError
from app.vision.detector import FaceDetector
from app.vision.utils import encode_image_to_jpeg


def create_synthetic_face(
    center_x: int = 320,
    center_y: int = 240,
    width: int = 640,
    height: int = 480,
    scale: float = 1.0,
) -> np.ndarray:
    """Generates an image containing a synthetic face that activates YuNet."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = (210, 210, 210)

    face_w = int(90 * scale)
    face_h = int(130 * scale)
    eye_r = max(2, int(14 * scale))
    eye_offset = int(35 * scale)
    mouth_w = max(4, int(35 * scale))
    mouth_h = max(2, int(14 * scale))

    # Face contour
    cv2.ellipse(img, (center_x, center_y), (face_w, face_h), 0, 0, 360, (180, 190, 230), -1)
    # Eyes
    cv2.circle(img, (center_x - eye_offset, center_y - int(40 * scale)), eye_r, (40, 40, 40), -1)
    cv2.circle(img, (center_x + eye_offset, center_y - int(40 * scale)), eye_r, (40, 40, 40), -1)
    # Nose
    cv2.circle(img, (center_x, center_y), max(2, int(9 * scale)), (80, 80, 80), -1)
    # Mouth
    cv2.ellipse(
        img, (center_x, center_y + int(60 * scale)), (mouth_w, mouth_h), 0, 0, 360, (30, 30, 140), -1
    )

    return img


@pytest.fixture
def detector() -> FaceDetector:
    return FaceDetector(score_threshold=0.30, min_face_size=30)


@pytest.mark.unit
def test_detector_invalid_model_path() -> None:
    with pytest.raises(ModelLoadError, match="not found at path"):
        FaceDetector(model_path="non_existent_model.onnx")


@pytest.mark.unit
def test_detector_invalid_inputs(detector: FaceDetector) -> None:
    # Not a numpy array
    with pytest.raises(InvalidImageError):
        detector.detect("not_an_image")  # type: ignore[arg-type]

    # Non-uint8 array
    with pytest.raises(InvalidImageError):
        detector.detect(np.zeros((100, 100, 3), dtype=np.float32))

    # 2D grayscale image
    with pytest.raises(InvalidImageError):
        detector.detect(np.zeros((100, 100), dtype=np.uint8))


@pytest.mark.unit
def test_detect_blank_image(detector: FaceDetector) -> None:
    blank = np.zeros((480, 640, 3), dtype=np.uint8)
    result = detector.detect(blank)

    assert result.count == 0
    assert len(result.faces) == 0
    assert result.has_faces is False
    assert result.primary_face is None
    assert result.image_width == 640
    assert result.image_height == 480


@pytest.mark.unit
def test_detect_single_face(detector: FaceDetector) -> None:
    face_img = create_synthetic_face(center_x=320, center_y=240, width=640, height=480)
    result = detector.detect(face_img)

    assert result.count == 1
    assert result.has_faces is True
    assert result.primary_face is not None

    detection = result.faces[0]
    assert detection.confidence >= 0.30
    assert detection.bbox.width > 30
    assert detection.bbox.height > 30
    assert detection.bbox.x >= 0
    assert detection.bbox.y >= 0
    assert detection.bbox.x2 <= 640
    assert detection.bbox.y2 <= 480

    # Verify landmarks
    lm = detection.landmarks
    assert lm.right_eye.x < lm.left_eye.x  # Subject's right eye is to the left in image
    assert lm.nose_tip.y > lm.right_eye.y
    assert lm.right_mouth_corner.y > lm.nose_tip.y


@pytest.mark.unit
def test_detect_multiple_faces(detector: FaceDetector) -> None:
    img = np.zeros((480, 800, 3), dtype=np.uint8)
    img[:] = (200, 200, 200)

    # Draw two faces
    for cx in [220, 580]:
        cv2.ellipse(img, (cx, 240), (90, 130), 0, 0, 360, (180, 190, 230), -1)
        cv2.circle(img, (cx - 35, 200), 14, (50, 50, 50), -1)
        cv2.circle(img, (cx + 35, 200), 14, (50, 50, 50), -1)
        cv2.circle(img, (cx, 240), 9, (100, 100, 100), -1)
        cv2.ellipse(img, (cx, 300), (35, 14), 0, 0, 360, (40, 40, 150), -1)

    result = detector.detect(img)
    assert result.count == 2
    assert len(result.faces) == 2


@pytest.mark.unit
def test_detect_min_face_size_filter() -> None:
    # Set min_face_size higher than the face dimensions
    strict_detector = FaceDetector(score_threshold=0.30, min_face_size=400)
    face_img = create_synthetic_face(center_x=320, center_y=240, scale=0.8)
    result = strict_detector.detect(face_img)

    # The face is ~200px wide, so strict 400px threshold must filter it out
    assert result.count == 0


@pytest.mark.unit
def test_detect_dynamic_resolutions(detector: FaceDetector) -> None:
    # Test consecutive detections at varied resolutions
    res1 = detector.detect(np.zeros((240, 320, 3), dtype=np.uint8))
    assert res1.image_width == 320 and res1.image_height == 240

    res2 = detector.detect(np.zeros((720, 1280, 3), dtype=np.uint8))
    assert res2.image_width == 1280 and res2.image_height == 720

    res3 = detector.detect(np.zeros((480, 640, 3), dtype=np.uint8))
    assert res3.image_width == 640 and res3.image_height == 480


@pytest.mark.unit
def test_detect_from_bytes_and_base64(detector: FaceDetector) -> None:
    face_img = create_synthetic_face(center_x=320, center_y=240)
    jpeg_bytes = encode_image_to_jpeg(face_img)
    b64_str = base64.b64encode(jpeg_bytes).decode("ascii")

    res_bytes = detector.detect_from_bytes(jpeg_bytes)
    assert res_bytes.count == 1

    res_b64 = detector.detect_from_base64(b64_str)
    assert res_b64.count == 1
