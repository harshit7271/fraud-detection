import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    AppException,
    FaceNotFoundError,
    InvalidImageError,
    ModelLoadError,
    MultipleFacesError,
    PoorImageQualityError,
    SessionNotFoundError,
    TenantNotFoundError,
)

logger = logging.getLogger("app.security.error_handler")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(FaceNotFoundError)
    async def face_not_found_handler(request: Request, exc: FaceNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "detail": "Exactly one face is required for interview registration. No face was detected.",
                }
            },
        )

    @app.exception_handler(MultipleFacesError)
    async def multiple_faces_handler(request: Request, exc: MultipleFacesError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "detail": "Multiple faces detected in selfie. Exactly one face must be present.",
                }
            },
        )

    @app.exception_handler(PoorImageQualityError)
    async def poor_quality_handler(request: Request, exc: PoorImageQualityError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "detail": "Selfie image quality is insufficient for biometric registration.",
                }
            },
        )

    @app.exception_handler(InvalidImageError)
    async def invalid_image_handler(request: Request, exc: InvalidImageError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "detail": "The image payload could not be decoded or violates format/size rules.",
                }
            },
        )

    @app.exception_handler(SessionNotFoundError)
    async def session_not_found_handler(request: Request, exc: SessionNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )

    @app.exception_handler(TenantNotFoundError)
    async def tenant_not_found_handler(request: Request, exc: TenantNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )

    @app.exception_handler(ModelLoadError)
    async def model_load_handler(request: Request, exc: ModelLoadError) -> JSONResponse:
        logger.critical(f"Critical CV model load failure: {exc}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": {
                    "code": exc.code,
                    "message": "Computer vision models are currently unavailable.",
                }
            },
        )

    @app.exception_handler(AppException)
    async def general_app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        logger.error(f"Application error [{exc.code}]: {exc.message}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Sanitize internal tracebacks from API consumers
        logger.exception(f"Unhandled exception during request processing: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An internal error occurred while processing the request.",
                }
            },
        )
