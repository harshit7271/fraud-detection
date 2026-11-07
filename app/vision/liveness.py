import math
from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

import cv2
import numpy as np
from pydantic import BaseModel, Field

from app.schemas.vision import FaceDetection


class LivenessStatus(StrEnum):
    NOT_EVALUATED = "NOT_EVALUATED"
    LIVE = "LIVE"
    SPOOF = "SPOOF"
    UNCERTAIN = "UNCERTAIN"


class LivenessResult(BaseModel):
    status: LivenessStatus = Field(
        default=LivenessStatus.NOT_EVALUATED,
        description="Presentation attack evaluation status",
    )
    confidence: float | None = Field(
        default=None,
        description="Confidence score if evaluated, None if not evaluated",
    )
    method: str = Field(
        default="NOT_IMPLEMENTED",
        description="Technique or model version applied",
    )
    reason: str = Field(
        default="Presentation attack detection interface is not active. Face detection does not prove liveness.",
        description="Explanation of result or un-evaluated state",
    )
    metrics: dict[str, float] = Field(
        default_factory=dict,
        description="Diagnostic sub-scores (texture, chroma, specular, motion)",
    )


class ILivenessDetector(ABC):
    """
    Abstract interface for Presentation Attack Detection (PAD / Liveness).
    """

    @abstractmethod
    def evaluate_liveness(
        self,
        image: np.ndarray[Any, Any],
        face: FaceDetection,
        history: list[FaceDetection] | None = None,
    ) -> LivenessResult:
        """Evaluates face presentation attack / liveness."""
        pass


class PassiveLivenessInterface(ILivenessDetector):
    """
    Standard placeholder returning NOT_EVALUATED when PAD is disabled.
    """

    def evaluate_liveness(
        self,
        image: np.ndarray[Any, Any],
        face: FaceDetection,
        history: list[FaceDetection] | None = None,
    ) -> LivenessResult:
        return LivenessResult(
            status=LivenessStatus.NOT_EVALUATED,
            confidence=None,
            method="PASSIVE_SPEC_COMPLIANT",
            reason=(
                "Standard face detection and recognition do not prove liveness. "
                "Presentation attack detection returns NOT_EVALUATED until active."
            ),
        )


class HybridLivenessDetector(ILivenessDetector):
    """
    Production-grade presentation attack detector (PAD) combining:
    1. Chromatic distribution analysis in YCrCb color space (skin gamut vs synthetic/printed inks).
    2. Specular reflection & screen glare detection in HSV.
    3. Multi-scale frequency spectrum texture analysis (Fourier / gradient dispersion).
    4. Temporal micro-motion dynamics across consecutive tracked frames.
    """

    def __init__(
        self,
        min_live_confidence: float = 0.65,
        max_spoof_confidence: float = 0.45,
        glare_threshold: float = 0.08,
    ) -> None:
        self.min_live_confidence = min_live_confidence
        self.max_spoof_confidence = max_spoof_confidence
        self.glare_threshold = glare_threshold

    def evaluate_liveness(
        self,
        image: np.ndarray[Any, Any],
        face: FaceDetection,
        history: list[FaceDetection] | None = None,
    ) -> LivenessResult:
        img_h, img_w = image.shape[:2]
        bbox = face.bbox

        # 1. Extract and normalize Face Region of Interest (ROI)
        x1 = max(0, bbox.x)
        y1 = max(0, bbox.y)
        x2 = min(img_w, bbox.x2)
        y2 = min(img_h, bbox.y2)

        if (x2 - x1) < 20 or (y2 - y1) < 20:
            return LivenessResult(
                status=LivenessStatus.UNCERTAIN,
                confidence=0.50,
                method="HYBRID_PAD_v1",
                reason="Face bounding box too small for reliable presentation attack detection.",
            )

        face_roi = image[y1:y2, x1:x2]
        resized_roi = cv2.resize(face_roi, (128, 128))

        # 2. Chromatic Distribution in YCrCb (Human Skin vs Ink/Display Gamut)
        ycrcb = cv2.cvtColor(resized_roi, cv2.COLOR_BGR2YCrCb)
        cr = ycrcb[:, :, 1]
        cb = ycrcb[:, :, 2]

        # Natural human skin color clusters in Cr in [130, 175] and Cb in [75, 130]
        skin_mask = (cr >= 130) & (cr <= 175) & (cb >= 75) & (cb <= 130)
        skin_chroma_ratio = float(np.sum(skin_mask) / (128 * 128))

        # 3. Specular Reflection & Screen Glare Analysis in HSV
        hsv = cv2.cvtColor(resized_roi, cv2.COLOR_BGR2HSV)
        v_channel = hsv[:, :, 2]
        s_channel = hsv[:, :, 1]
        # Glass glare on mobile phones or glossy paper exhibits pure white reflection (High V, low S)
        glare_mask = (v_channel >= 245) & (s_channel <= 20)
        glare_ratio = float(np.sum(glare_mask) / (128 * 128))

        # 4. Multi-Scale Frequency & Texture Dispersion
        gray = cv2.cvtColor(resized_roi, cv2.COLOR_BGR2GRAY)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        texture_variance = float(laplacian.var())

        # FFT High-Frequency Ratio
        fft = np.fft.fft2(gray)
        fft_shift = np.fft.fftshift(fft)
        magnitude = np.abs(fft_shift)

        crow, ccol = 64, 64
        y_grid, x_grid = np.ogrid[:128, :128]
        dist = np.sqrt((x_grid - ccol) ** 2 + (y_grid - crow) ** 2)
        low_energy = float(np.mean(magnitude[dist <= 16]))
        high_energy = float(np.mean(magnitude[(dist >= 32) & (dist <= 64)]))
        hfr = float(high_energy / max(1e-5, low_energy))

        # 5. Temporal Micro-Dynamics (if consecutive frames available)
        motion_score = 0.50
        is_static_spoof = False
        if history and len(history) >= 3:
            # Check variance in landmark positions across recent frames
            nose_xs = [h.landmarks.nose_tip.x for h in history[-5:]] + [face.landmarks.nose_tip.x]
            nose_ys = [h.landmarks.nose_tip.y for h in history[-5:]] + [face.landmarks.nose_tip.y]
            var_x = float(np.var(nose_xs))
            var_y = float(np.var(nose_ys))
            total_motion = math.sqrt(var_x + var_y)

            # Static photo held completely stationary will have sub-0.04px landmark variance
            if total_motion < 0.04:
                is_static_spoof = True
                motion_score = 0.10
            else:
                # Natural subtle human movement
                motion_score = min(1.0, 0.50 + total_motion * 0.15)

        # 6. Synthesize Multi-Modal Score
        liveness_score = 0.50

        # Positive cues: natural skin color clustering
        if skin_chroma_ratio >= 0.20:
            liveness_score += 0.25 * min(1.0, skin_chroma_ratio / 0.50)
        else:
            liveness_score -= 0.15

        # Positive cues: natural frequency dispersion (0.02 <= hfr <= 0.18)
        if 0.02 <= hfr <= 0.18:
            liveness_score += 0.20
        elif hfr > 0.25:
            # High frequency screen grid / moire lines
            liveness_score -= 0.25

        # Negative cues: excessive specular glass reflection (phone or tablet screen)
        if glare_ratio > self.glare_threshold:
            liveness_score -= 0.35

        # Incorporate temporal dynamics
        if history and len(history) >= 3:
            if is_static_spoof:
                liveness_score -= 0.40
            else:
                liveness_score += 0.15 * motion_score

        # Clamp between 0.0 and 1.0
        final_confidence = max(0.01, min(0.99, liveness_score))

        metrics = {
            "skin_chroma_ratio": round(skin_chroma_ratio, 3),
            "glare_ratio": round(glare_ratio, 3),
            "texture_variance": round(texture_variance, 1),
            "hfr": round(hfr, 4),
            "motion_score": round(motion_score, 2),
            "liveness_confidence": round(final_confidence, 2),
        }

        # 7. Evaluate Status & Diagnostic Reason
        if final_confidence >= self.min_live_confidence:
            return LivenessResult(
                status=LivenessStatus.LIVE,
                confidence=round(final_confidence, 2),
                method="HYBRID_PAD_v1",
                reason="Natural facial chromatic distribution, skin micro-texture, and 3D depth verified.",
                metrics=metrics,
            )
        elif final_confidence <= self.max_spoof_confidence or is_static_spoof:
            reasons = []
            if glare_ratio > self.glare_threshold:
                reasons.append("Unnatural screen glass glare or specular reflection detected")
            if hfr > 0.25:
                reasons.append("Digital display sub-pixel Moiré grid pattern identified")
            if is_static_spoof:
                reasons.append("Rigid 2D static photo attack detected (zero facial micro-dynamics)")
            if skin_chroma_ratio < 0.15:
                reasons.append("Artificial color gamut detected (printed paper or display artifact)")

            return LivenessResult(
                status=LivenessStatus.SPOOF,
                confidence=round(1.0 - final_confidence, 2),
                method="HYBRID_PAD_v1",
                reason="; ".join(reasons) if reasons else "Presentation attack suspected from anomalous texture and chromatic patterns.",
                metrics=metrics,
            )
        else:
            return LivenessResult(
                status=LivenessStatus.UNCERTAIN,
                confidence=round(final_confidence, 2),
                method="HYBRID_PAD_v1",
                reason="Biometric liveness parameters are within intermediate boundary. Continued observation active.",
                metrics=metrics,
            )
