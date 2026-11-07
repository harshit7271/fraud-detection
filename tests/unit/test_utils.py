import base64

import numpy as np
import pytest

from app.core.exceptions import InvalidImageError
from app.vision.utils import (
    decode_base64_image,
    decode_image_bytes,
    encode_image_to_jpeg,
    validate_image_header,
)


@pytest.fixture
def sample_image() -> np.ndarray:
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    img[20:80, 20:80] = (255, 128, 0)
    return img


@pytest.fixture
def sample_jpeg_bytes(sample_image: np.ndarray) -> bytes:
    return encode_image_to_jpeg(sample_image)


@pytest.mark.unit
def test_validate_image_header(sample_jpeg_bytes: bytes) -> None:
    fmt = validate_image_header(sample_jpeg_bytes)
    assert fmt == "jpeg"

    with pytest.raises(InvalidImageError, match="too small"):
        validate_image_header(b"abc")

    with pytest.raises(InvalidImageError, match="Unsupported or invalid"):
        validate_image_header(b"GIF89a1234567890")


@pytest.mark.unit
def test_decode_image_bytes(sample_jpeg_bytes: bytes) -> None:
    decoded = decode_image_bytes(sample_jpeg_bytes)
    assert isinstance(decoded, np.ndarray)
    assert decoded.dtype == np.uint8
    assert decoded.shape == (100, 100, 3)


@pytest.mark.unit
def test_decode_image_bytes_corrupted() -> None:
    fake_header = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 30
    with pytest.raises(InvalidImageError):
        decode_image_bytes(fake_header)


@pytest.mark.unit
def test_decode_image_max_dimension(sample_jpeg_bytes: bytes) -> None:
    with pytest.raises(InvalidImageError, match="exceed maximum"):
        decode_image_bytes(sample_jpeg_bytes, max_dimension=50)


@pytest.mark.unit
def test_decode_base64_image(sample_jpeg_bytes: bytes) -> None:
    b64_raw = base64.b64encode(sample_jpeg_bytes).decode("ascii")
    decoded = decode_base64_image(b64_raw)
    assert decoded.shape == (100, 100, 3)

    # Test with data URI prefix
    b64_data_uri = f"data:image/jpeg;base64,{b64_raw}"
    decoded_uri = decode_base64_image(b64_data_uri)
    assert decoded_uri.shape == (100, 100, 3)


@pytest.mark.unit
def test_decode_base64_invalid() -> None:
    with pytest.raises(InvalidImageError, match="Invalid Base64"):
        decode_base64_image("!!!not_base64!!!")
