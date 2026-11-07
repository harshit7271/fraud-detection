from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_NAME: str = "FACEGUARD AI Face Fraud Detection Microservice"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 7860
    API_V1_PREFIX: str = "/api/v1"

    # Security & Biometrics
    SECRET_KEY: str = "default-insecure-secret-key-change-in-production"
    BIOMETRIC_MASTER_KEY: str = "MDEyMzQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDE="
    BIOMETRIC_KEY_VERSION: str = "v1-2026"
    ALLOWED_ORIGINS: list[str] = ["*"]

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres_password"
    POSTGRES_DB: str = "face_fraud_db"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres_password@localhost:5432/face_fraud_db"
    SYNC_DATABASE_URL: str = "postgresql://postgres:postgres_password@localhost:5432/face_fraud_db"

    # Redis & Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Computer Vision Models
    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
    YUNET_MODEL_PATH: str = "models/weights/face_detection_yunet_2023mar.onnx"
    SFACE_MODEL_PATH: str = "models/weights/face_recognition_sface_2021dec.onnx"
    CV_CONFIDENCE_THRESHOLD: float = 0.50
    CV_NMS_THRESHOLD: float = 0.30
    CV_MIN_FACE_SIZE: int = 40

    # Proctoring Fallback Defaults
    DEFAULT_FACE_MATCH_THRESHOLD: float = 0.38
    DEFAULT_FACE_UNCERTAIN_THRESHOLD: float = 0.25
    DEFAULT_MULTIPLE_FACES_DEBOUNCE_MS: int = 2000
    DEFAULT_FACE_ABSENT_DEBOUNCE_MS: int = 3000

    # Observability
    SENTRY_DSN: str = ""
    PROMETHEUS_METRICS_ENABLED: bool = True
    LOG_LEVEL: str = "INFO"

    @property
    def resolved_yunet_path(self) -> Path:
        p = Path(self.YUNET_MODEL_PATH)
        return p if p.is_absolute() else self.PROJECT_ROOT / p

    @property
    def resolved_sface_path(self) -> Path:
        p = Path(self.SFACE_MODEL_PATH)
        return p if p.is_absolute() else self.PROJECT_ROOT / p

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(item) for item in parsed]
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return [str(x) for x in v]
        return ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
