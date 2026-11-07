import threading
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.core.config import get_settings
from app.core.exceptions import InvalidImageError, ModelLoadError, VisionError
from app.schemas.vision import (
    FaceDetection,
    FaceEmbedding,
    IdentityMatchResult,
    IdentityStatus,
)


class FaceRecognizer:
    """
    OpenCV FaceRecognizerSF wrapper for SFace ONNX face recognition model.
    Handles landmark-based face alignment (112x112 chip), 128-dimensional L2-normalized
    embedding extraction, and configurable multi-boundary cosine identity verification.
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        default_match_threshold: float | None = None,
        default_uncertain_threshold: float | None = None,
    ) -> None:
        settings = get_settings()
        resolved_path = (
            Path(model_path)
            if model_path is not None
            else settings.resolved_sface_path
        )

        if not resolved_path.exists():
            raise ModelLoadError(
                f"SFace model weights not found at path: {resolved_path}. "
                "Ensure weights have been downloaded via scripts/download_models.py."
            )

        self.model_path = str(resolved_path)
        self.default_match_threshold = (
            default_match_threshold
            if default_match_threshold is not None
            else settings.DEFAULT_FACE_MATCH_THRESHOLD
        )
        self.default_uncertain_threshold = (
            default_uncertain_threshold
            if default_uncertain_threshold is not None
            else settings.DEFAULT_FACE_UNCERTAIN_THRESHOLD
        )

        self._lock = threading.Lock()
        try:
            self._recognizer = cv2.FaceRecognizerSF.create(
                model=self.model_path,
                config="",
            )
        except Exception as e:
            raise ModelLoadError(f"Failed to initialize cv2.FaceRecognizerSF: {e}") from e

    def align_face(
        self,
        image: np.ndarray[Any, Any],
        face: FaceDetection,
    ) -> np.ndarray[Any, Any]:
        """
        Aligns and crops the detected face to standard 112x112 dimensions using
        detected 5-point facial landmarks.
        """
        if not face.raw_face or len(face.raw_face) < 14:
            raise VisionError(
                "Face detection lacks valid raw landmark coordinates required for alignment"
            )

        raw_array = np.array(face.raw_face, dtype=np.float32)
        with self._lock:
            aligned: np.ndarray[Any, Any] = self._recognizer.alignCrop(image, raw_array)

        if aligned is None or aligned.shape != (112, 112, 3):
            raise VisionError(f"Face alignment produced unexpected output shape: {getattr(aligned, 'shape', None)}")

        return aligned

    def extract_embedding(
        self,
        image: np.ndarray[Any, Any],
        face: FaceDetection,
    ) -> FaceEmbedding:
        """
        Extracts a 128-dimensional L2-normalized feature vector from an aligned face.
        """
        aligned = self.align_face(image, face)
        return self.extract_from_aligned(aligned)

    def extract_from_aligned(
        self,
        aligned_face: np.ndarray[Any, Any],
    ) -> FaceEmbedding:
        """
        Extracts embedding directly from a 112x112 aligned face chip.
        """
        if not isinstance(aligned_face, np.ndarray) or aligned_face.shape != (112, 112, 3):
            raise InvalidImageError(
                f"Aligned face image must be a 112x112x3 NumPy array, got {getattr(aligned_face, 'shape', None)}"
            )

        with self._lock:
            raw_feature: np.ndarray[Any, Any] = self._recognizer.feature(aligned_face)

        flat = raw_feature.flatten().astype(np.float32)
        norm = float(np.linalg.norm(flat))
        if norm > 0.0:
            flat = flat / norm

        return FaceEmbedding.from_numpy(flat)

    @staticmethod
    def _to_vector(
        embedding: FaceEmbedding | np.ndarray[Any, Any] | list[float],
    ) -> np.ndarray[Any, Any]:
        """Helper to cast input representation to a 1D float32 NumPy array."""
        if isinstance(embedding, FaceEmbedding):
            return embedding.to_numpy()
        elif isinstance(embedding, np.ndarray):
            return embedding.flatten().astype(np.float32)
        elif isinstance(embedding, list):
            return np.array(embedding, dtype=np.float32)
        raise ValueError(f"Unsupported embedding type: {type(embedding)}")

    def compute_similarity(
        self,
        emb1: FaceEmbedding | np.ndarray[Any, Any] | list[float],
        emb2: FaceEmbedding | np.ndarray[Any, Any] | list[float],
    ) -> float:
        """
        Computes the cosine similarity between two 128-d face embeddings.
        Returns a float bounded in [-1.0, 1.0].
        """
        v1 = self._to_vector(emb1)
        v2 = self._to_vector(emb2)

        if len(v1) != 128 or len(v2) != 128:
            raise ValueError(
                f"Embeddings must be 128-dimensional. Received: len(v1)={len(v1)}, len(v2)={len(v2)}"
            )

        norm1 = float(np.linalg.norm(v1))
        norm2 = float(np.linalg.norm(v2))

        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0

        dot_product = float(np.dot(v1, v2))
        cosine_sim = dot_product / (norm1 * norm2)

        # Clamp numerical edge cases to [-1.0, 1.0]
        return max(-1.0, min(1.0, cosine_sim))

    def verify(
        self,
        target_embedding: FaceEmbedding | np.ndarray[Any, Any] | list[float],
        reference_embedding: FaceEmbedding | np.ndarray[Any, Any] | list[float],
        match_threshold: float | None = None,
        uncertain_threshold: float | None = None,
    ) -> IdentityMatchResult:
        """
        Compares a target embedding against a reference embedding.
        Classifies the comparison into MATCH, UNCERTAIN, or MISMATCH based on thresholds.
        """
        m_thresh = (
            match_threshold
            if match_threshold is not None
            else self.default_match_threshold
        )
        u_thresh = (
            uncertain_threshold
            if uncertain_threshold is not None
            else self.default_uncertain_threshold
        )

        if u_thresh > m_thresh:
            raise ValueError(
                f"uncertain_threshold ({u_thresh}) cannot be greater than match_threshold ({m_thresh})"
            )

        score = self.compute_similarity(target_embedding, reference_embedding)

        if score >= m_thresh:
            status = IdentityStatus.MATCH
        elif score >= u_thresh:
            status = IdentityStatus.UNCERTAIN
        else:
            status = IdentityStatus.MISMATCH

        return IdentityMatchResult(
            status=status,
            similarity_score=score,
            match_threshold=m_thresh,
            uncertain_threshold=u_thresh,
        )
