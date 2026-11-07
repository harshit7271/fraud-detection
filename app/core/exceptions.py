class AppException(Exception):
    """Base exception for application errors."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class VisionError(AppException):
    """Base exception for vision and model inference failures."""

    def __init__(self, message: str, code: str = "VISION_ERROR") -> None:
        super().__init__(message, code=code)


class ModelLoadError(VisionError):
    """Raised when ONNX model weights fail to load or are missing."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="MODEL_LOAD_ERROR")


class InvalidImageError(VisionError):
    """Raised when an image payload cannot be decoded or is corrupted."""

    def __init__(self, message: str) -> None:
        super().__init__(message, code="INVALID_IMAGE_PAYLOAD")


class FaceNotFoundError(VisionError):
    """Raised when no face is found during selfie registration."""

    def __init__(self, message: str = "No face detected in the provided image") -> None:
        super().__init__(message, code="NO_FACE_DETECTED")


class MultipleFacesError(VisionError):
    """Raised when multiple faces are detected during registration."""

    def __init__(self, message: str = "Multiple faces detected; exactly one face required") -> None:
        super().__init__(message, code="MULTIPLE_FACES_DETECTED")


class PoorImageQualityError(VisionError):
    """Raised when an image fails quality checks during registration."""

    def __init__(self, message: str = "Image quality is insufficient for biometric verification") -> None:
        super().__init__(message, code="POOR_IMAGE_QUALITY")


class TenantError(AppException):
    """Base exception for tenant-related issues."""

    def __init__(self, message: str, code: str = "TENANT_ERROR") -> None:
        super().__init__(message, code=code)


class TenantNotFoundError(TenantError):
    def __init__(self, tenant_id: str) -> None:
        super().__init__(f"Tenant {tenant_id} not found", code="TENANT_NOT_FOUND")


class AuthenticationError(AppException):
    def __init__(self, message: str = "Invalid or missing authentication credentials") -> None:
        super().__init__(message, code="UNAUTHORIZED")


class SessionNotFoundError(AppException):
    def __init__(self, session_id: str) -> None:
        super().__init__(f"Interview session {session_id} not found", code="SESSION_NOT_FOUND")
