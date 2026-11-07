from typing import Any

import cv2
import numpy as np
from pydantic import BaseModel, Field

from app.schemas.vision import FaceDetection


class ImageQualityAssessment(BaseModel):
    blur_score: float = Field(..., description="Variance of Laplacian; higher is sharper")
    is_blurry: bool
    brightness_score: float = Field(..., description="Mean luminance [0, 255]")
    is_underexposed: bool
    is_overexposed: bool
    contrast_score: float = Field(..., description="Standard deviation of luminance; higher is better contrast")
    is_low_contrast: bool
    face_size_ratio: float = Field(default=0.0, description="Face area relative to total image area")
    is_face_too_small: bool
    is_occluded: bool = Field(default=False, description="Significant facial occlusion or extreme profile angle")
    is_acceptable: bool = Field(..., description="Whether image quality meets minimum biometric standards")
    quality_issues: list[str] = Field(default_factory=list)


class QualityAssessor:
    """
    Evaluates image quality metrics (blur, brightness, contrast, face sizing, occlusion)
    to prevent low-quality frames from triggering false identity penalties.
    """

    def __init__(
        self,
        blur_threshold: float = 25.0,
        min_brightness: float = 25.0,
        max_brightness: float = 240.0,
        min_contrast: float = 10.0,
        min_face_ratio: float = 0.008,
        max_landmark_asymmetry_ratio: float = 4.5,
    ) -> None:
        self.blur_threshold = blur_threshold
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness
        self.min_contrast = min_contrast
        self.min_face_ratio = min_face_ratio
        self.max_landmark_asymmetry_ratio = max_landmark_asymmetry_ratio

    def evaluate(
        self,
        image: np.ndarray[Any, Any],
        face: FaceDetection | None = None,
        is_selfie: bool = False,
    ) -> ImageQualityAssessment:
        img_h, img_w = image.shape[:2]
        total_pixels = max(1, img_h * img_w)

        # Convert to single-channel grayscale for luminance analysis
        if len(image.shape) == 3 and image.shape[2] == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # 1. Blur Detection via Variance of Laplacian
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        blur_score = float(laplacian.var())
        is_blurry = blur_score < self.blur_threshold

        # 2. Brightness Assessment (Mean Luminance)
        brightness_score = float(np.mean(gray))
        is_underexposed = brightness_score < self.min_brightness
        is_overexposed = brightness_score > self.max_brightness

        # 3. Contrast Assessment (Standard Deviation of Luminance)
        contrast_score = float(np.std(gray))
        is_low_contrast = contrast_score < self.min_contrast

        # 4. Face Sizing & Landmark Asymmetry / Occlusion (if face is present)
        face_size_ratio = 0.0
        is_face_too_small = False
        is_occluded = False
        occlusion_reasons: list[str] = []

        if face is not None:
            face_size_ratio = float(face.bbox.area / total_pixels)
            is_face_too_small = face_size_ratio < self.min_face_ratio

            # A. Confidence check (occluded faces exhibit degraded detector confidence)
            if face.confidence < 0.45:
                is_occluded = True
                occlusion_reasons.append(f"Face confidence is degraded ({face.confidence:.2f} < 0.45) - features partially obscured")

            # B. Evaluate landmark geometry for extreme yaw / asymmetry
            lm = face.landmarks
            dist_right = float(np.hypot(lm.nose_tip.x - lm.right_eye.x, lm.nose_tip.y - lm.right_eye.y))
            dist_left = float(np.hypot(lm.left_eye.x - lm.nose_tip.x, lm.left_eye.y - lm.nose_tip.y))

            min_dist = max(1e-4, min(dist_right, dist_left))
            max_dist = max(dist_right, dist_left)
            asymmetry = max_dist / min_dist
            if asymmetry > self.max_landmark_asymmetry_ratio:
                is_occluded = True
                occlusion_reasons.append("Facial landmarks show extreme head turn or profile angle")

            # C. Lower face / hands covering mouth or chin check
            eye_dist = float(np.hypot(lm.left_eye.x - lm.right_eye.x, lm.left_eye.y - lm.right_eye.y))
            mouth_dist = float(np.hypot(lm.left_mouth_corner.x - lm.right_mouth_corner.x, lm.left_mouth_corner.y - lm.right_mouth_corner.y))
            eyes_mid_y = (lm.left_eye.y + lm.right_eye.y) / 2.0
            mouth_mid_y = (lm.left_mouth_corner.y + lm.right_mouth_corner.y) / 2.0
            vert_dist = mouth_mid_y - eyes_mid_y

            if eye_dist > 5.0:
                if vert_dist < 0.22 * eye_dist:
                    is_occluded = True
                    occlusion_reasons.append("Lower face or mouth occluded (mouth-to-eye vertical distance abnormal)")
                if mouth_dist < 0.12 * eye_dist:
                    is_occluded = True
                    occlusion_reasons.append("Mouth occluded or covered by hands/objects")
                # Check for inverted landmarks (nose above eye line or mouth above nose)
                if lm.nose_tip.y < min(lm.left_eye.y, lm.right_eye.y):
                    is_occluded = True
                    occlusion_reasons.append("Nose landmark inverted above eye line")
                if mouth_mid_y < lm.nose_tip.y:
                    is_occluded = True
                    occlusion_reasons.append("Mouth landmark inverted above nose tip")

            # D. Landmark bounding box containment
            bbox = face.bbox
            margin_x = max(12.0, bbox.width * 0.15)
            margin_y = max(12.0, bbox.height * 0.15)
            pts = [lm.right_eye, lm.left_eye, lm.nose_tip, lm.right_mouth_corner, lm.left_mouth_corner]
            if any(not (bbox.x - margin_x <= p.x <= bbox.x2 + margin_x and bbox.y - margin_y <= p.y <= bbox.y2 + margin_y) for p in pts):
                is_occluded = True
                occlusion_reasons.append("Facial landmarks fall outside face boundary (partial occlusion)")

            # E. Specialized Full Front-Facing & Zero-Occlusion Rules for Onboarding Selfie
            if is_selfie:
                # 1. Enforce strict front-facing yaw: nose must be centrally aligned between eyes
                if asymmetry > 1.85:
                    is_occluded = True
                    occlusion_reasons.append("Side face / profile detected. Full front face looking straight at camera is required.")

                eye_span = abs(lm.left_eye.x - lm.right_eye.x)
                if eye_span > 10.0:
                    mid_eye_x = (lm.left_eye.x + lm.right_eye.x) / 2.0
                    nose_eye_offset_ratio = abs(lm.nose_tip.x - mid_eye_x) / eye_span
                    if nose_eye_offset_ratio > 0.22:
                        is_occluded = True
                        occlusion_reasons.append("Face is turned to the side. Full front-facing alignment required.")

                # 2. Strict confidence check: occluded or half-covered faces exhibit degraded confidence
                if face.confidence < 0.50:
                    is_occluded = True
                    occlusion_reasons.append(f"Face features partially covered or occluded (confidence {face.confidence:.2f} < 0.50). Uncover your entire face.")

                # 3. Half-face covered check: bilateral facial width ratio
                if face.bbox.width > 20:
                    if (eye_dist / face.bbox.width) < 0.25:
                        is_occluded = True
                        occlusion_reasons.append("Half of face or eye region is covered. Ensure full face is visible without obstructions.")

                # 4. Lower face / mouth covered check
                if eye_dist > 10.0 and mouth_dist < 0.20 * eye_dist:
                    is_occluded = True
                    occlusion_reasons.append("Lower face or mouth appears covered. Remove hands, mask, or covering.")

        # Compile Quality Deficiencies
        issues: list[str] = []
        if is_blurry:
            issues.append(f"Image is blurry (blur score {blur_score:.1f} < {self.blur_threshold})")
        if is_underexposed:
            issues.append(f"Image is underexposed/dark (brightness {brightness_score:.1f} < {self.min_brightness})")
        if is_overexposed:
            issues.append(f"Image is overexposed/washed out (brightness {brightness_score:.1f} > {self.max_brightness})")
        if is_low_contrast:
            issues.append(f"Image has low contrast (contrast score {contrast_score:.1f} < {self.min_contrast})")
        if is_face_too_small:
            issues.append(f"Face is too small in frame ({face_size_ratio * 100:.2f}% < {self.min_face_ratio * 100:.1f}%)")
        if is_occluded:
            if occlusion_reasons:
                issues.extend(occlusion_reasons)
            else:
                issues.append("Facial landmarks show extreme head turn or partial occlusion")

        is_acceptable = len(issues) == 0

        return ImageQualityAssessment(
            blur_score=blur_score,
            is_blurry=is_blurry,
            brightness_score=brightness_score,
            is_underexposed=is_underexposed,
            is_overexposed=is_overexposed,
            contrast_score=contrast_score,
            is_low_contrast=is_low_contrast,
            face_size_ratio=face_size_ratio,
            is_face_too_small=is_face_too_small,
            is_occluded=is_occluded,
            is_acceptable=is_acceptable,
            quality_issues=issues,
        )
