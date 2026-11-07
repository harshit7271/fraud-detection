import base64
from typing import Any

import cv2
import numpy as np

from app.core.exceptions import InvalidImageError

# Known image magic byte signatures
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
WEBP_MAGIC_RIFF = b"RIFF"
WEBP_MAGIC_TYPE = b"WEBP"


def validate_image_header(data: bytes) -> str:
    """Validates binary image headers against allowed formats (JPEG, PNG, WEBP)."""
    if len(data) < 12:
        raise InvalidImageError("Image payload is too small to be a valid image file")

    if data.startswith(JPEG_MAGIC):
        return "jpeg"
    if data.startswith(PNG_MAGIC):
        return "png"
    if data.startswith(WEBP_MAGIC_RIFF) and data[8:12] == WEBP_MAGIC_TYPE:
        return "webp"

    raise InvalidImageError(
        "Unsupported or invalid image format. Allowed formats are JPEG, PNG, and WebP"
    )


def decode_image_bytes(image_bytes: bytes, max_dimension: int = 4096) -> np.ndarray[Any, Any]:
    """
    Safely decodes raw image bytes into a BGR uint8 NumPy array.
    Validates magic bytes, checks for decompression bombs, and verifies 3-channel layout.
    """
    validate_image_header(image_bytes)

    np_buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    image: np.ndarray[Any, Any] | None = cv2.imdecode(np_buffer, cv2.IMREAD_COLOR)

    if image is None:
        raise InvalidImageError("Failed to decode image; file may be corrupt")

    h, w = image.shape[:2]
    if h == 0 or w == 0:
        raise InvalidImageError("Decoded image has zero dimensions")

    if h > max_dimension or w > max_dimension:
        raise InvalidImageError(
            f"Image dimensions ({w}x{h}) exceed maximum allowed dimension ({max_dimension}px)"
        )

    return image


def decode_base64_image(base64_str: str, max_dimension: int = 4096) -> np.ndarray[Any, Any]:
    """
    Decodes a Base64-encoded image string (with or without data URI prefix).
    """
    cleaned_str = base64_str.strip()
    if "," in cleaned_str and cleaned_str.startswith("data:image"):
        cleaned_str = cleaned_str.split(",", 1)[1]

    try:
        image_bytes = base64.b64decode(cleaned_str, validate=True)
    except Exception as e:
        raise InvalidImageError(f"Invalid Base64 payload: {e}") from e

    return decode_image_bytes(image_bytes, max_dimension=max_dimension)


def encode_image_to_jpeg(image: np.ndarray[Any, Any], quality: int = 85) -> bytes:
    """Encodes a BGR image array into JPEG bytes."""
    success, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not success:
        raise InvalidImageError("Failed to encode image array to JPEG format")
    return bytes(encoded.tobytes())
