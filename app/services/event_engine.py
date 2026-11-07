from app.schemas.fraud import FraudEvent, FraudEventType, FraudSeverity
from app.schemas.vision import IdentityStatus
from app.vision.liveness import LivenessResult, LivenessStatus
from app.vision.quality import ImageQualityAssessment
from app.vision.tracker import TrackedFace


class TemporalEventEngine:
    """
    Temporal Fraud Event Engine.
    Evaluates streaming or batched frame observations across time to confirm suspicious
    events based on configurable duration, persistence, and cooldown constraints.
    Eliminates false alarms from momentary head movements or transient occlusion.
    """

    def __init__(
        self,
        session_id: str,
        tenant_id: str,
        multiple_faces_debounce_ms: int = 2000,
        face_absent_debounce_ms: int = 3000,
        identity_mismatch_debounce_ms: int = 1500,
        cooldown_ms: int = 5000,
    ) -> None:
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.multiple_faces_debounce_ms = multiple_faces_debounce_ms
        self.face_absent_debounce_ms = face_absent_debounce_ms
        self.identity_mismatch_debounce_ms = identity_mismatch_debounce_ms
        self.cooldown_ms = cooldown_ms

        # Temporal State Machines
        self._absence_start_ms: int | None = None
        self._multiple_faces_start_ms: int | None = None
        self._mismatch_start_ms: int | None = None

        # Cooldown Tracker (last emitted timestamp per event type)
        self._last_emitted_ms: dict[FraudEventType, int] = {}

    def _is_cooling_down(self, event_type: FraudEventType, current_time_ms: int) -> bool:
        last_time = self._last_emitted_ms.get(event_type)
        if last_time is None:
            return False
        return (current_time_ms - last_time) < self.cooldown_ms

    def process_observation(
        self,
        timestamp_ms: int,
        tracked_faces: list[TrackedFace],
        quality: ImageQualityAssessment,
        primary_identity_status: IdentityStatus | None = None,
        identity_similarity_score: float | None = None,
        liveness: LivenessResult | None = None,
    ) -> list[FraudEvent]:
        """
        Processes a single frame observation and returns any temporally confirmed FraudEvents.
        """
        confirmed_events: list[FraudEvent] = []
        face_count = len(tracked_faces)

        # 1. Evaluate Image Quality
        if not quality.is_acceptable:
            if not self._is_cooling_down(FraudEventType.LOW_IMAGE_QUALITY, timestamp_ms):
                confirmed_events.append(
                    FraudEvent(
                        session_id=self.session_id,
                        tenant_id=self.tenant_id,
                        event_type=FraudEventType.LOW_IMAGE_QUALITY,
                        timestamp_ms=timestamp_ms,
                        duration_ms=0,
                        confidence=1.0,
                        severity=FraudSeverity.LOW,
                        evidence_metadata={
                            "blur_score": quality.blur_score,
                            "brightness_score": quality.brightness_score,
                            "contrast_score": quality.contrast_score,
                            "issues": quality.quality_issues,
                        },
                    )
                )
                self._last_emitted_ms[FraudEventType.LOW_IMAGE_QUALITY] = timestamp_ms

            # Section 5.D: Poor image quality must not become an identity fraud event
            # Suppress identity mismatch accumulation during poor quality frames
            self._mismatch_start_ms = None
            return confirmed_events

        # 2. Evaluate Face Absence / Zero Faces
        if face_count == 0:
            if self._absence_start_ms is None:
                self._absence_start_ms = timestamp_ms

            duration = timestamp_ms - self._absence_start_ms
            if duration >= self.face_absent_debounce_ms:
                if not self._is_cooling_down(FraudEventType.FACE_ABSENT, timestamp_ms):
                    confirmed_events.append(
                        FraudEvent(
                            session_id=self.session_id,
                            tenant_id=self.tenant_id,
                            event_type=FraudEventType.FACE_ABSENT,
                            timestamp_ms=timestamp_ms,
                            duration_ms=duration,
                            confidence=0.95,
                            severity=FraudSeverity.MEDIUM if duration < 6000 else FraudSeverity.HIGH,
                            evidence_metadata={
                                "absence_duration_ms": duration,
                                "threshold_ms": self.face_absent_debounce_ms,
                            },
                        )
                    )
                    self._last_emitted_ms[FraudEventType.FACE_ABSENT] = timestamp_ms
        else:
            self._absence_start_ms = None

        # 3. Evaluate Multiple Faces
        if face_count > 1:
            if self._multiple_faces_start_ms is None:
                self._multiple_faces_start_ms = timestamp_ms

            duration = timestamp_ms - self._multiple_faces_start_ms
            if duration >= self.multiple_faces_debounce_ms:
                if not self._is_cooling_down(FraudEventType.MULTIPLE_FACES, timestamp_ms):
                    avg_conf = float(sum(f.confidence for f in tracked_faces) / face_count)
                    confirmed_events.append(
                        FraudEvent(
                            session_id=self.session_id,
                            tenant_id=self.tenant_id,
                            event_type=FraudEventType.MULTIPLE_FACES,
                            timestamp_ms=timestamp_ms,
                            duration_ms=duration,
                            confidence=avg_conf,
                            severity=FraudSeverity.HIGH,
                            evidence_metadata={
                                "face_count": face_count,
                                "duration_ms": duration,
                                "track_ids": [f.track_id for f in tracked_faces],
                            },
                        )
                    )
                    self._last_emitted_ms[FraudEventType.MULTIPLE_FACES] = timestamp_ms
        else:
            self._multiple_faces_start_ms = None

        # 4. Evaluate Identity Mismatch (Only when exactly one face is present and quality is good)
        if face_count == 1:
            has_mismatch = primary_identity_status == IdentityStatus.MISMATCH

            # Also check if tracked face is confirmed mismatch
            if not has_mismatch and tracked_faces[0].verified_identity_status == IdentityStatus.MISMATCH:
                has_mismatch = True

            if has_mismatch:
                if self._mismatch_start_ms is None:
                    self._mismatch_start_ms = timestamp_ms

                duration = timestamp_ms - self._mismatch_start_ms
                if duration >= self.identity_mismatch_debounce_ms:
                    if not self._is_cooling_down(FraudEventType.IDENTITY_MISMATCH, timestamp_ms):
                        confirmed_events.append(
                            FraudEvent(
                                session_id=self.session_id,
                                tenant_id=self.tenant_id,
                                event_type=FraudEventType.IDENTITY_MISMATCH,
                                timestamp_ms=timestamp_ms,
                                duration_ms=duration,
                                confidence=tracked_faces[0].confidence,
                                severity=FraudSeverity.CRITICAL,
                                evidence_metadata={
                                    "similarity_score": identity_similarity_score,
                                    "mismatch_duration_ms": duration,
                                    "track_id": tracked_faces[0].track_id,
                                },
                            )
                        )
                        self._last_emitted_ms[FraudEventType.IDENTITY_MISMATCH] = timestamp_ms
            elif primary_identity_status == IdentityStatus.MATCH:
                self._mismatch_start_ms = None

        # 5. Evaluate Presentation Attack / Liveness Spoof
        if liveness and liveness.status == LivenessStatus.SPOOF:
            if not self._is_cooling_down(FraudEventType.PRESENTATION_ATTACK_SUSPECTED, timestamp_ms):
                confirmed_events.append(
                    FraudEvent(
                        session_id=self.session_id,
                        tenant_id=self.tenant_id,
                        event_type=FraudEventType.PRESENTATION_ATTACK_SUSPECTED,
                        timestamp_ms=timestamp_ms,
                        duration_ms=0,
                        confidence=liveness.confidence or 0.90,
                        severity=FraudSeverity.CRITICAL,
                        evidence_metadata={
                            "method": liveness.method,
                            "reason": liveness.reason,
                            "metrics": liveness.metrics,
                        },
                    )
                )
                self._last_emitted_ms[FraudEventType.PRESENTATION_ATTACK_SUSPECTED] = timestamp_ms

        return confirmed_events
