import logging
from typing import Any

from celery import Celery, signals

from app.core.config import get_settings
from app.vision.detector import FaceDetector
from app.vision.quality import QualityAssessor
from app.vision.recognizer import FaceRecognizer

logger = logging.getLogger("app.workers.celery")
settings = get_settings()

celery_app = Celery(
    "face_fraud_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_time_limit=120,
    task_soft_time_limit=90,
    task_default_queue="fraud_cv_tasks",
)

# Process-level CV singletons (loaded once per worker process)
_worker_detector: FaceDetector | None = None
_worker_recognizer: FaceRecognizer | None = None
_worker_quality_assessor: QualityAssessor | None = None


def get_worker_detector() -> FaceDetector:
    global _worker_detector
    if _worker_detector is None:
        _worker_detector = FaceDetector()
    return _worker_detector


def get_worker_recognizer() -> FaceRecognizer:
    global _worker_recognizer
    if _worker_recognizer is None:
        _worker_recognizer = FaceRecognizer()
    return _worker_recognizer


def get_worker_quality_assessor() -> QualityAssessor:
    global _worker_quality_assessor
    if _worker_quality_assessor is None:
        _worker_quality_assessor = QualityAssessor()
    return _worker_quality_assessor


@signals.worker_process_init.connect
def warmup_cv_models(**kwargs: Any) -> None:
    """
    Signal handler: Load YuNet and SFace models once into memory during
    worker process initialization. Prevents redundant disk I/O and ONNX model
    instantiation on incoming video frame batches.
    """
    logger.info("Initializing CV models in Celery worker process...")
    get_worker_detector()
    get_worker_recognizer()
    get_worker_quality_assessor()
    logger.info("Celery worker CV models initialized and warmed up.")


@signals.worker_shutdown.connect
def on_worker_shutdown(**kwargs: Any) -> None:
    """Signal handler for graceful Celery worker termination."""
    logger.info("Celery worker process shutting down gracefully.")
