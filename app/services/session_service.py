import json
import logging
import os
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import (
    AppException,
    FaceNotFoundError,
    MultipleFacesError,
    PoorImageQualityError,
    SessionNotFoundError,
)
from app.schemas.fraud import FraudEvent, FraudEventType, RiskAssessment
from app.schemas.session import (
    FraudReportResponse,
    ReferenceFaceMetadata,
    SessionDetailResponse,
    SessionRegisterResponse,
)
from app.schemas.vision import BoundingBox, FaceEmbedding
from app.services.event_engine import TemporalEventEngine
from app.services.scoring import RiskScoringEngine, TenantScoringPolicy
from app.services.tenant_service import get_tenant_service
from app.vision.detector import FaceDetector
from app.vision.quality import ImageQualityAssessment, QualityAssessor
from app.vision.recognizer import FaceRecognizer
from app.vision.tracker import FaceTracker
from app.vision.utils import decode_image_bytes


@dataclass
class SessionData:
    session_id: str
    tenant_id: str
    candidate_id: str
    interview_id: str
    consent_recorded: bool
    reference_embedding: FaceEmbedding
    reference_bbox: BoundingBox
    reference_quality: ImageQualityAssessment
    tracker: FaceTracker
    event_engine: TemporalEventEngine
    scoring_engine: RiskScoringEngine
    confirmed_events: list[FraudEvent] = field(default_factory=list)
    status: str = "INITIALIZED"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def latest_risk(self) -> RiskAssessment:
        return self.scoring_engine.calculate_risk(self.confirmed_events)


logger = logging.getLogger(__name__)


class SessionService:
    """
    Manages session registration, reference face representation lifecycle,
    persistent storage, and cross-tenant isolation boundaries.
    """

    def __init__(
        self,
        detector: FaceDetector | None = None,
        recognizer: FaceRecognizer | None = None,
        quality_assessor: QualityAssessor | None = None,
        storage_path: Path | None = None,
    ) -> None:
        self.detector = detector or FaceDetector()
        self.recognizer = recognizer or FaceRecognizer()
        self.quality_assessor = quality_assessor or QualityAssessor()

        self._lock = threading.Lock()
        self._sessions: dict[str, SessionData] = {}
        settings = get_settings()

        # Isolate testing data from live production data
        is_test_env = "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ
        if storage_path is not None:
            self.storage_path = storage_path
        elif is_test_env:
            self.storage_path = settings.PROJECT_ROOT / "data" / "test_sessions_store.json"
        else:
            self.storage_path = settings.PROJECT_ROOT / "data" / "sessions_store.json"

        self._load_from_disk()

    def reload_from_disk(self) -> int:
        """Forces a reload of sessions from disk, returning total sessions count."""
        with self._lock:
            self._load_from_disk()
            return len(self._sessions)

    def _save_to_disk(self) -> None:
        if self.storage_path is None:
            return
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            serialized = {}
            for sid, s in self._sessions.items():
                serialized[sid] = {
                    "session_id": s.session_id,
                    "tenant_id": s.tenant_id,
                    "candidate_id": s.candidate_id,
                    "interview_id": s.interview_id,
                    "consent_recorded": s.consent_recorded,
                    "status": s.status,
                    "created_at": s.created_at.isoformat(),
                    "reference_bbox": s.reference_bbox.model_dump(mode="json"),
                    "reference_embedding": s.reference_embedding.model_dump(mode="json"),
                    "reference_quality": s.reference_quality.model_dump(mode="json"),
                    "confirmed_events": [e.model_dump(mode="json") for e in s.confirmed_events],
                }
            temp_path = self.storage_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(serialized, f, indent=2)
            temp_path.replace(self.storage_path)
        except Exception as e:
            logger.warning(f"Failed to persist sessions to disk: {e}")

    def _load_from_disk(self) -> None:
        if not self.storage_path or not self.storage_path.exists():
            return
        try:
            with open(self.storage_path, encoding="utf-8") as f:
                raw_data = json.load(f)

            ts = get_tenant_service()
            for sid, item in raw_data.items():
                tenant_id = item["tenant_id"]
                profile = ts.get_tenant_by_id_or_slug(tenant_id)
                if profile:
                    face_absence_debounce = profile.face_absence_debounce_ms
                    multiple_faces_debounce = profile.multiple_faces_debounce_ms
                    weights_dict = {
                        FraudEventType.FACE_ABSENT: profile.event_weights.face_absent,
                        FraudEventType.MULTIPLE_FACES: profile.event_weights.multiple_faces,
                        FraudEventType.IDENTITY_MISMATCH: profile.event_weights.identity_mismatch,
                        FraudEventType.PRESENTATION_ATTACK_SUSPECTED: profile.event_weights.suspicious_liveness,
                    }
                    crit_band = profile.risk_bands.get("CRITICAL")
                    high_band = profile.risk_bands.get("HIGH")
                    med_band = profile.risk_bands.get("MEDIUM")
                    scoring_policy = TenantScoringPolicy(
                        event_weights=weights_dict,
                        critical_threshold=crit_band.min_score if crit_band else 75.0,
                        high_threshold=high_band.min_score if high_band else 50.0,
                        medium_threshold=med_band.min_score if med_band else 25.0,
                    )
                else:
                    face_absence_debounce = 3000
                    multiple_faces_debounce = 2000
                    scoring_policy = TenantScoringPolicy()

                scoring_engine = RiskScoringEngine(policy=scoring_policy)
                confirmed_events = [FraudEvent(**e) for e in item.get("confirmed_events", [])]

                self._sessions[sid] = SessionData(
                    session_id=item["session_id"],
                    tenant_id=tenant_id,
                    candidate_id=item["candidate_id"],
                    interview_id=item["interview_id"],
                    consent_recorded=item["consent_recorded"],
                    reference_embedding=FaceEmbedding(**item["reference_embedding"]),
                    reference_bbox=BoundingBox(**item["reference_bbox"]),
                    reference_quality=ImageQualityAssessment(**item["reference_quality"]),
                    tracker=FaceTracker(),
                    event_engine=TemporalEventEngine(
                        session_id=sid,
                        tenant_id=tenant_id,
                        face_absent_debounce_ms=face_absence_debounce,
                        multiple_faces_debounce_ms=multiple_faces_debounce,
                    ),
                    scoring_engine=scoring_engine,
                    confirmed_events=confirmed_events,
                    status=item.get("status", "ACTIVE"),
                    created_at=datetime.fromisoformat(item["created_at"]),
                )
        except Exception as e:
            logger.warning(f"Failed to load sessions from disk: {e}")

    def save_session_state(self, session_id: str) -> None:
        """Persists updated state (fraud events, risk scores) of a session."""
        with self._lock:
            if session_id in self._sessions:
                self._save_to_disk()

    def register_session(
        self,
        tenant_id: str,
        candidate_id: str,
        interview_id: str,
        consent: bool,
        selfie_bytes: bytes,
        max_upload_size: int = 5 * 1024 * 1024,  # 5 MB
    ) -> SessionRegisterResponse:
        if not consent:
            raise AppException("Candidate consent is required for biometric fraud detection", code="CONSENT_REQUIRED")

        if len(selfie_bytes) > max_upload_size:
            raise AppException(
                f"Selfie image exceeds maximum upload size of {max_upload_size // (1024 * 1024)}MB",
                code="PAYLOAD_TOO_LARGE",
            )

        # 1. Decode image payload safely
        image = decode_image_bytes(selfie_bytes)

        # 2. Run Face Detection
        detection_result = self.detector.detect_selfie(image)
        if detection_result.count == 0:
            raise FaceNotFoundError("No face detected in the provided selfie")
        if detection_result.count > 1:
            raise MultipleFacesError(
                f"Multiple faces ({detection_result.count}) detected in selfie; exactly one face required"
            )

        primary_face = detection_result.faces[0]
        if primary_face.confidence < 0.50:
            raise PoorImageQualityError(
                f"Selfie face confidence too low ({primary_face.confidence:.2f} < 0.50). "
                "Ensure your face is clearly visible, remove hands/objects, and face the camera directly."
            )

        # 3. Evaluate Image Quality
        quality = self.quality_assessor.evaluate(image, primary_face, is_selfie=True)
        if not quality.is_acceptable:
            raise PoorImageQualityError(
                f"Selfie quality check failed: {'; '.join(quality.quality_issues)}"
            )

        # 4. Generate Reference Biometric Embedding
        reference_embedding = self.recognizer.extract_embedding(image, primary_face)

        session_id = str(uuid.uuid4())

        # Retrieve tenant-specific proctoring profile
        tenant_service = get_tenant_service()
        profile = tenant_service.get_tenant_by_id_or_slug(tenant_id)

        if profile:
            face_absence_debounce = profile.face_absence_debounce_ms
            multiple_faces_debounce = profile.multiple_faces_debounce_ms
            weights_dict = {
                FraudEventType.FACE_ABSENT: profile.event_weights.face_absent,
                FraudEventType.MULTIPLE_FACES: profile.event_weights.multiple_faces,
                FraudEventType.IDENTITY_MISMATCH: profile.event_weights.identity_mismatch,
                FraudEventType.PRESENTATION_ATTACK_SUSPECTED: profile.event_weights.suspicious_liveness,
            }
            crit_band = profile.risk_bands.get("CRITICAL")
            high_band = profile.risk_bands.get("HIGH")
            med_band = profile.risk_bands.get("MEDIUM")
            scoring_policy = TenantScoringPolicy(
                event_weights=weights_dict,
                critical_threshold=crit_band.min_score if crit_band else 75.0,
                high_threshold=high_band.min_score if high_band else 50.0,
                medium_threshold=med_band.min_score if med_band else 25.0,
            )
        else:
            face_absence_debounce = 3000
            multiple_faces_debounce = 2000
            scoring_policy = TenantScoringPolicy()

        session_data = SessionData(
            session_id=session_id,
            tenant_id=tenant_id,
            candidate_id=candidate_id,
            interview_id=interview_id,
            consent_recorded=consent,
            reference_embedding=reference_embedding,
            reference_bbox=primary_face.bbox,
            reference_quality=quality,
            tracker=FaceTracker(),
            event_engine=TemporalEventEngine(
                session_id=session_id,
                tenant_id=tenant_id,
                face_absent_debounce_ms=face_absence_debounce,
                multiple_faces_debounce_ms=multiple_faces_debounce,
            ),
            scoring_engine=RiskScoringEngine(policy=scoring_policy),
            status="INITIALIZED",
        )

        with self._lock:
            self._sessions[session_id] = session_data
            self._save_to_disk()

        return SessionRegisterResponse(
            session_id=session_id,
            tenant_id=tenant_id,
            candidate_id=candidate_id,
            interview_id=interview_id,
            status=session_data.status,
            reference_face=ReferenceFaceMetadata(
                face_detected=True,
                confidence=primary_face.confidence,
                bounding_box=primary_face.bbox,
                quality=quality,
            ),
            created_at=session_data.created_at,
        )

    def get_session(self, session_id: str, tenant_id: str) -> SessionData:
        """Retrieves session data with strict tenant-isolation validation."""
        with self._lock:
            session = self._sessions.get(session_id)

        if session is None:
            raise SessionNotFoundError(session_id)

        # Enforce multi-tenant segregation: compare direct identifiers or resolved profiles
        is_same_tenant = session.tenant_id == tenant_id
        if not is_same_tenant:
            ts = get_tenant_service()
            p1 = ts.get_tenant_by_id_or_slug(session.tenant_id)
            p2 = ts.get_tenant_by_id_or_slug(tenant_id)
            if p1 and p2 and p1.slug == p2.slug:
                is_same_tenant = True

        if not is_same_tenant:
            # Prevent cross-tenant discovery by returning 404
            raise SessionNotFoundError(session_id)

        return session

    def get_session_detail(self, session_id: str, tenant_id: str) -> SessionDetailResponse:
        session = self.get_session(session_id, tenant_id)
        return SessionDetailResponse(
            session_id=session.session_id,
            tenant_id=session.tenant_id,
            candidate_id=session.candidate_id,
            interview_id=session.interview_id,
            status=session.status,
            consent_recorded=session.consent_recorded,
            current_risk=session.latest_risk,
            total_events=len(session.confirmed_events),
            created_at=session.created_at,
        )

    def get_fraud_report(self, session_id: str, tenant_id: str) -> FraudReportResponse:
        session = self.get_session(session_id, tenant_id)
        risk = session.latest_risk

        return FraudReportResponse(
            session_id=session.session_id,
            tenant_id=session.tenant_id,
            candidate_id=session.candidate_id,
            interview_id=session.interview_id,
            status=session.status,
            risk_assessment=risk,
            total_events=len(session.confirmed_events),
            confirmed_events=[e.model_dump() for e in session.confirmed_events],
        )

    def list_sessions(self, tenant_id: str) -> list[SessionDetailResponse]:
        """Lists all interview sessions belonging to the given tenant."""
        results: list[SessionDetailResponse] = []
        ts = get_tenant_service()
        tenant_profile = ts.get_tenant_by_id_or_slug(tenant_id)
        tenant_slug = tenant_profile.slug if tenant_profile else tenant_id

        with self._lock:
            for s in self._sessions.values():
                s_profile = ts.get_tenant_by_id_or_slug(s.tenant_id)
                s_slug = s_profile.slug if s_profile else s.tenant_id
                if s.tenant_id == tenant_id or s_slug == tenant_slug:
                    results.append(
                        SessionDetailResponse(
                            session_id=s.session_id,
                            tenant_id=s.tenant_id,
                            candidate_id=s.candidate_id,
                            interview_id=s.interview_id,
                            status=s.status,
                            consent_recorded=s.consent_recorded,
                            current_risk=s.latest_risk,
                            total_events=len(s.confirmed_events),
                            created_at=s.created_at,
                        )
                    )
        results.sort(key=lambda x: x.created_at, reverse=True)
        return results

    def get_session_events(self, session_id: str, tenant_id: str) -> list[FraudEvent]:
        """Returns the list of confirmed fraud events for a session."""
        session = self.get_session(session_id, tenant_id)
        return list(session.confirmed_events)

    def reset(self) -> None:
        """Clears all sessions (useful for tests)."""
        with self._lock:
            self._sessions.clear()
            if self.storage_path and self.storage_path.exists():
                try:
                    self.storage_path.unlink()
                except OSError:
                    pass


# Global Singleton for in-memory session coordination
session_service = SessionService()


def get_session_service() -> SessionService:
    return session_service
