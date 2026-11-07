import threading
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.core.config import get_settings
from app.core.exceptions import InvalidImageError, ModelLoadError
from app.schemas.vision import (
    BoundingBox,
    DetectionResult,
    FaceDetection,
    Landmarks,
    Point,
)
from app.vision.utils import decode_base64_image, decode_image_bytes


class FaceDetector:
    """
    OpenCV FaceDetectorYN wrapper for YuNet ONNX face detection model.
    Handles dynamic input sizing, 5-point facial landmark extraction,
    bounding box boundary validation, and minimum face size constraints.
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        score_threshold: float | None = None,
        nms_threshold: float | None = None,
        min_face_size: int | None = None,
        top_k: int = 50,
    ) -> None:
        settings = get_settings()
        resolved_path = (
            Path(model_path)
            if model_path is not None
            else settings.resolved_yunet_path
        )

        if not resolved_path.exists():
            raise ModelLoadError(
                f"YuNet model weights not found at path: {resolved_path}. "
                "Ensure weights have been downloaded via scripts/download_models.py."
            )

        self.model_path = str(resolved_path)
        self.score_threshold = (
            score_threshold
            if score_threshold is not None
            else settings.CV_CONFIDENCE_THRESHOLD
        )
        self.nms_threshold = (
            nms_threshold
            if nms_threshold is not None
            else settings.CV_NMS_THRESHOLD
        )
        self.min_face_size = (
            min_face_size
            if min_face_size is not None
            else settings.CV_MIN_FACE_SIZE
        )
        self.top_k = top_k

        self._lock = threading.Lock()
        self._current_size = (320, 320)

        try:
            self._detector = cv2.FaceDetectorYN.create(
                model=self.model_path,
                config="",
                input_size=self._current_size,
                score_threshold=float(self.score_threshold),
                nms_threshold=float(self.nms_threshold),
                top_k=int(self.top_k),
            )
        except Exception as e:
            raise ModelLoadError(f"Failed to initialize cv2.FaceDetectorYN: {e}") from e

    def detect(self, image: np.ndarray[Any, Any]) -> DetectionResult:
        """
        Executes face detection on a BGR uint8 NumPy image array.
        Dynamically adjusts the detector input resolution to match image dimensions.
        """
        if not isinstance(image, np.ndarray) or image.dtype != np.uint8:
            raise InvalidImageError("Input image must be a uint8 NumPy array")

        if len(image.shape) != 3 or image.shape[2] != 3:
            raise InvalidImageError(
                f"Expected 3-channel BGR image, received shape: {image.shape}"
            )

        img_h, img_w = image.shape[:2]
        if img_h == 0 or img_w == 0:
            raise InvalidImageError("Image has invalid zero dimensions")

        target_size = (img_w, img_h)

        with self._lock:
            if self._current_size != target_size:
                self._detector.setInputSize(target_size)
                self._current_size = target_size

            # Execute OpenCV C++ inference
            _, raw_faces = self._detector.detect(image)

        if raw_faces is None or len(raw_faces) == 0:
            return DetectionResult(
                faces=[],
                count=0,
                image_width=img_w,
                image_height=img_h,
            )

        detections: list[FaceDetection] = []
        for raw in raw_faces:
            confidence = float(raw[14])
            if confidence < self.score_threshold:
                continue

            x = int(raw[0])
            y = int(raw[1])
            w = int(raw[2])
            h = int(raw[3])

            # Filter small background faces
            if w < self.min_face_size or h < self.min_face_size:
                continue

            # Clamp coordinates to image boundaries
            clamped_x = max(0, min(x, img_w - 1))
            clamped_y = max(0, min(y, img_h - 1))
            clamped_w = max(1, min(w, img_w - clamped_x))
            clamped_h = max(1, min(h, img_h - clamped_y))

            bbox = BoundingBox(
                x=clamped_x,
                y=clamped_y,
                width=clamped_w,
                height=clamped_h,
            )

            # 5 Facial Landmarks (Right Eye, Left Eye, Nose Tip, Right Mouth, Left Mouth)
            landmarks = Landmarks(
                right_eye=Point(x=float(raw[4]), y=float(raw[5])),
                left_eye=Point(x=float(raw[6]), y=float(raw[7])),
                nose_tip=Point(x=float(raw[8]), y=float(raw[9])),
                right_mouth_corner=Point(x=float(raw[10]), y=float(raw[11])),
                left_mouth_corner=Point(x=float(raw[12]), y=float(raw[13])),
            )

            detections.append(
                FaceDetection(
                    bbox=bbox,
                    landmarks=landmarks,
                    confidence=confidence,
                    raw_face=[float(val) for val in raw],
                )
            )

        # Sort detections by bounding box area descending
        detections.sort(key=lambda d: d.bbox.area, reverse=True)

        # Deduplicate overlapping bounding boxes (NMS cleanup)
        deduped: list[FaceDetection] = []
        for det in detections:
            if any(det.bbox.iou(kept.bbox) > 0.30 for kept in deduped):
                continue
            deduped.append(det)
        detections = deduped

        return DetectionResult(
            faces=detections,
            count=len(detections),
            image_width=img_w,
            image_height=img_h,
        )

    def detect_selfie(self, image: np.ndarray[Any, Any]) -> DetectionResult:
        """
        Specialized face detection for candidate registration selfies.
        Suppresses low-confidence background noise, distant poster artifacts,
        and duplicate detections to prevent false multiple-face rejections.
        """
        result = self.detect(image)
        if result.count <= 1:
            return result

        primary = result.faces[0]
        # In a selfie, candidate's face is foregrounded.
        # Filter secondary artifacts (e.g. background photos, textured noise, low confidence)
        genuine_faces: list[FaceDetection] = [primary]
        for face in result.faces[1:]:
            if face.confidence < 0.60:
                continue
            if primary.bbox.area > 4000 and face.bbox.area < 0.20 * primary.bbox.area:
                continue
            genuine_faces.append(face)

        return DetectionResult(
            faces=genuine_faces,
            count=len(genuine_faces),
            image_width=result.image_width,
            image_height=result.image_height,
        )

    def detect_from_bytes(self, image_bytes: bytes) -> DetectionResult:
        """Decodes raw image bytes and runs face detection."""
        image = decode_image_bytes(image_bytes)
        return self.detect(image)

    def detect_from_base64(self, base64_str: str) -> DetectionResult:
        """Decodes a Base64 image and runs face detection."""
        image = decode_base64_image(base64_str)
        return self.detect(image)
