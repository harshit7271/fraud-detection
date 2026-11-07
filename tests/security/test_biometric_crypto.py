import pytest

from app.core.crypto import BiometricCipher, EncryptedBiometricData
from app.core.exceptions import AppException
from app.schemas.vision import FaceEmbedding


@pytest.fixture
def cipher() -> BiometricCipher:
    return BiometricCipher()


@pytest.fixture
def sample_embedding_bytes() -> bytes:
    emb = FaceEmbedding(vector=[float(i) * 0.01 for i in range(128)])
    return emb.to_bytes()


@pytest.mark.security
def test_biometric_encrypt_decrypt_roundtrip(
    cipher: BiometricCipher,
    sample_embedding_bytes: bytes,
) -> None:
    encrypted = cipher.encrypt(sample_embedding_bytes)
    assert isinstance(encrypted, EncryptedBiometricData)
    assert len(encrypted.iv) == 12  # 96-bit IV
    assert encrypted.ciphertext != sample_embedding_bytes
    assert encrypted.key_version == "v1-2026"

    decrypted = cipher.decrypt(encrypted.ciphertext, encrypted.iv)
    assert decrypted == sample_embedding_bytes


@pytest.mark.security
def test_biometric_encryption_random_iv(
    cipher: BiometricCipher,
    sample_embedding_bytes: bytes,
) -> None:
    # Encrypting identical plaintext twice produces distinct ciphertexts and IVs
    enc1 = cipher.encrypt(sample_embedding_bytes)
    enc2 = cipher.encrypt(sample_embedding_bytes)

    assert enc1.iv != enc2.iv
    assert enc1.ciphertext != enc2.ciphertext


@pytest.mark.security
def test_biometric_tamper_detection(
    cipher: BiometricCipher,
    sample_embedding_bytes: bytes,
) -> None:
    encrypted = cipher.encrypt(sample_embedding_bytes)

    # Mutate a byte in the ciphertext
    tampered_bytes = bytearray(encrypted.ciphertext)
    tampered_bytes[0] ^= 0xFF

    with pytest.raises(AppException, match="authentication failed"):
        cipher.decrypt(bytes(tampered_bytes), encrypted.iv)


@pytest.mark.security
def test_biometric_invalid_key_length() -> None:
    # Key shorter than 32 bytes (256 bits)
    bad_key_b64 = "YWJjZGVmZw=="
    with pytest.raises(AppException, match="Key length must be exactly 32 bytes"):
        BiometricCipher(master_key_base64=bad_key_b64)
