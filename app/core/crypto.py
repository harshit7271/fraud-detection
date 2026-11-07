import base64
import os
from typing import NamedTuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings
from app.core.exceptions import AppException


class EncryptedBiometricData(NamedTuple):
    ciphertext: bytes
    iv: bytes
    key_version: str


class BiometricCipher:
    """
    AES-256-GCM Biometric Encryption Engine.
    Ensures biometric feature vectors and representations are encrypted at rest with
    authenticated encryption, random per-record initialization vectors (IV), and key versioning.
    """

    def __init__(
        self,
        master_key_base64: str | None = None,
        key_version: str | None = None,
    ) -> None:
        settings = get_settings()
        b64_key = master_key_base64 or settings.BIOMETRIC_MASTER_KEY
        self.key_version = key_version or settings.BIOMETRIC_KEY_VERSION

        try:
            self._key = base64.b64decode(b64_key)
            if len(self._key) != 32:  # 256 bits
                raise ValueError(f"Key length must be exactly 32 bytes (256 bits), got {len(self._key)}")
            self._aesgcm = AESGCM(self._key)
        except Exception as e:
            raise AppException(f"Failed to initialize BiometricCipher: {e}", code="CRYPTO_INIT_ERROR") from e

    def encrypt(self, plaintext_bytes: bytes, associated_data: bytes | None = None) -> EncryptedBiometricData:
        """
        Encrypts plaintext biometric bytes using AES-256-GCM.
        Generates a secure 96-bit (12-byte) random IV.
        """
        iv = os.urandom(12)  # Recommended 96-bit IV for AES-GCM
        ciphertext = self._aesgcm.encrypt(iv, plaintext_bytes, associated_data)
        return EncryptedBiometricData(
            ciphertext=ciphertext,
            iv=iv,
            key_version=self.key_version,
        )

    def decrypt(
        self,
        ciphertext: bytes,
        iv: bytes,
        associated_data: bytes | None = None,
    ) -> bytes:
        """
        Decrypts AES-256-GCM ciphertext and authenticates the integrity tag.
        Raises AppException if ciphertext is corrupted or tampered with.
        """
        try:
            return self._aesgcm.decrypt(iv, ciphertext, associated_data)
        except Exception as e:
            raise AppException(f"Biometric decryption authentication failed: {e}", code="DECRYPTION_FAILED") from e


biometric_cipher = BiometricCipher()


def get_biometric_cipher() -> BiometricCipher:
    return biometric_cipher
