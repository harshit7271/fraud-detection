import struct
from enum import StrEnum
from typing import Any

import numpy as np
from pydantic import BaseModel, Field


class IdentityStatus(StrEnum):
    MATCH = "MATCH"
    UNCERTAIN = "UNCERTAIN"
    MISMATCH = "MISMATCH"


class Point(BaseModel):
    x: float = Field(..., description="X coordinate")
    y: float = Field(..., description="Y coordinate")


class BoundingBox(BaseModel):
    x: int = Field(..., description="Top-left X coordinate")
    y: int = Field(..., description="Top-left Y coordinate")
    width: int = Field(..., description="Bounding box width")
    height: int = Field(..., description="Bounding box height")

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height

    def iou(self, other: "BoundingBox") -> float:
        """Computes Intersection-over-Union (IoU) with another bounding box."""
        inter_x1 = max(self.x, other.x)
        inter_y1 = max(self.y, other.y)
        inter_x2 = min(self.x2, other.x2)
        inter_y2 = min(self.y2, other.y2)

        inter_w = max(0, inter_x2 - inter_x1)
        inter_h = max(0, inter_y2 - inter_y1)
        inter_area = inter_w * inter_h

        union_area = self.area + other.area - inter_area
        if union_area <= 0:
            return 0.0
        return float(inter_area / union_area)


class Landmarks(BaseModel):
    right_eye: Point = Field(..., description="Right eye coordinate")
    left_eye: Point = Field(..., description="Left eye coordinate")
    nose_tip: Point = Field(..., description="Nose tip coordinate")
    right_mouth_corner: Point = Field(..., description="Right mouth corner coordinate")
    left_mouth_corner: Point = Field(..., description="Left mouth corner coordinate")

    def to_list(self) -> list[list[float]]:
        return [
            [self.right_eye.x, self.right_eye.y],
            [self.left_eye.x, self.left_eye.y],
            [self.nose_tip.x, self.nose_tip.y],
            [self.right_mouth_corner.x, self.right_mouth_corner.y],
            [self.left_mouth_corner.x, self.left_mouth_corner.y],
        ]


class FaceDetection(BaseModel):
    bbox: BoundingBox
    landmarks: Landmarks
    confidence: float = Field(..., ge=0.0, le=1.0)
    # 15-float raw vector as expected by OpenCV FaceRecognizerSF (x, y, w, h, x1, y1, ...)
    raw_face: list[float] = Field(default_factory=list, exclude=True)

    @property
    def area(self) -> int:
        return self.bbox.area


class DetectionResult(BaseModel):
    faces: list[FaceDetection] = Field(default_factory=list)
    count: int = Field(default=0)
    image_width: int
    image_height: int

    @property
    def has_faces(self) -> bool:
        return self.count > 0

    @property
    def primary_face(self) -> FaceDetection | None:
        """Returns the face with the largest area, or None if no faces detected."""
        if not self.faces:
            return None
        return max(self.faces, key=lambda f: f.bbox.area)


class FaceEmbedding(BaseModel):
    """128-dimensional L2-normalized biometric representation extracted by SFace."""
    vector: list[float] = Field(..., description="128 float values")
    dimension: int = Field(default=128)

    def to_numpy(self) -> np.ndarray[Any, Any]:
        """Converts vector to a 1D float32 NumPy array."""
        return np.array(self.vector, dtype=np.float32)

    @classmethod
    def from_numpy(cls, arr: np.ndarray[Any, Any]) -> "FaceEmbedding":
        flat = arr.flatten().astype(np.float32)
        if len(flat) != 128:
            raise ValueError(f"Expected 128-dimensional embedding, received dimension {len(flat)}")
        return cls(vector=[float(val) for val in flat], dimension=128)

    def to_bytes(self) -> bytes:
        """Packs the 128 float32 values into 512 raw bytes for binary persistence/encryption."""
        return struct.pack(f"{len(self.vector)}f", *self.vector)

    @classmethod
    def from_bytes(cls, data: bytes) -> "FaceEmbedding":
        """Unpacks 512 bytes into a 128-float FaceEmbedding."""
        if len(data) != 512:
            raise ValueError(f"Expected exactly 512 bytes for 128 float32s, received {len(data)} bytes")
        floats = struct.unpack("128f", data)
        return cls(vector=list(floats), dimension=128)


class IdentityMatchResult(BaseModel):
    """Result of an identity verification comparison between two face embeddings."""
    status: IdentityStatus
    similarity_score: float = Field(..., description="Cosine similarity score in range [-1.0, 1.0]")
    match_threshold: float = Field(..., description="Threshold for MATCH classification")
    uncertain_threshold: float = Field(..., description="Threshold below which is MISMATCH")

    @property
    def is_match(self) -> bool:
        return self.status == IdentityStatus.MATCH

    @property
    def is_uncertain(self) -> bool:
        return self.status == IdentityStatus.UNCERTAIN

    @property
    def is_mismatch(self) -> bool:
        return self.status == IdentityStatus.MISMATCH
