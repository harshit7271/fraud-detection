import pytest

from app.schemas.fraud import FraudEventType, FraudSeverity
from app.schemas.vision import (
    BoundingBox,
    IdentityStatus,
    Landmarks,
    Point,
)
from app.services.event_engine import TemporalEventEngine
from app.vision.quality import ImageQualityAssessment
from app.vision.tracker import TrackedFace


@pytest.fixture
def acceptable_quality() -> ImageQualityAssessment:
    return ImageQualityAssessment(
        blur_score=150.0,
        is_blurry=False,
        brightness_score=120.0,
        is_underexposed=False,
        is_overexposed=False,
        contrast_score=50.0,
        is_low_contrast=False,
        face_size_ratio=0.08,
        is_face_too_small=False,
        is_occluded=False,
        is_acceptable=True,
    )


@pytest.fixture
def poor_quality() -> ImageQualityAssessment:
    return ImageQualityAssessment(
        blur_score=20.0,
        is_blurry=True,
        brightness_score=20.0,
        is_underexposed=True,
        is_overexposed=False,
        contrast_score=10.0,
        is_low_contrast=True,
        face_size_ratio=0.08,
        is_face_too_small=False,
        is_occluded=False,
        is_acceptable=False,
        quality_issues=["Image is blurry", "Image is underexposed"],
    )


def make_tracked_face(track_id: int, status: IdentityStatus = IdentityStatus.MATCH) -> TrackedFace:
    return TrackedFace(
        track_id=track_id,
        bbox=BoundingBox(x=100, y=100, width=80, height=80),
        landmarks=Landmarks(
            right_eye=Point(x=120, y=120),
            left_eye=Point(x=160, y=120),
            nose_tip=Point(x=140, y=140),
            right_mouth_corner=Point(x=125, y=160),
            left_mouth_corner=Point(x=155, y=160),
        ),
        confidence=0.98,
        raw_face=[],
        first_seen_timestamp_ms=1000,
        last_seen_timestamp_ms=1000,
        verified_identity_status=status,
    )


@pytest.mark.unit
def test_absence_debouncing(acceptable_quality: ImageQualityAssessment) -> None:
    engine = TemporalEventEngine(
        session_id="sess_123",
        tenant_id="tenant_abc",
        face_absent_debounce_ms=3000,
        cooldown_ms=5000,
    )

    # t=1000ms: 0 faces
    events = engine.process_observation(1000, [], acceptable_quality)
    assert len(events) == 0

    # t=2500ms: duration 1500ms < 3000ms -> Still suppressed
    events = engine.process_observation(2500, [], acceptable_quality)
    assert len(events) == 0

    # t=4100ms: duration 3100ms >= 3000ms -> Emits confirmed event
    events = engine.process_observation(4100, [], acceptable_quality)
    assert len(events) == 1
    ev = events[0]
    assert ev.event_type == FraudEventType.FACE_ABSENT
    assert ev.duration_ms == 3100
    assert ev.session_id == "sess_123"

    # t=5000ms: still absent, but within 5000ms cooldown -> Suppressed
    events_cooldown = engine.process_observation(5000, [], acceptable_quality)
    assert len(events_cooldown) == 0


@pytest.mark.unit
def test_multiple_faces_debouncing(acceptable_quality: ImageQualityAssessment) -> None:
    engine = TemporalEventEngine(
        session_id="sess_123",
        tenant_id="tenant_abc",
        multiple_faces_debounce_ms=2000,
    )

    faces = [make_tracked_face(1), make_tracked_face(2)]

    # t=1000ms: 2 faces
    assert len(engine.process_observation(1000, faces, acceptable_quality)) == 0

    # t=2000ms: duration 1000ms < 2000ms
    assert len(engine.process_observation(2000, faces, acceptable_quality)) == 0

    # t=3100ms: duration 2100ms >= 2000ms -> Confirmed MULTIPLE_FACES
    events = engine.process_observation(3100, faces, acceptable_quality)
    assert len(events) == 1
    assert events[0].event_type == FraudEventType.MULTIPLE_FACES
    assert events[0].severity == FraudSeverity.HIGH


@pytest.mark.unit
def test_identity_mismatch_debouncing(acceptable_quality: ImageQualityAssessment) -> None:
    engine = TemporalEventEngine(
        session_id="sess_123",
        tenant_id="tenant_abc",
        identity_mismatch_debounce_ms=1500,
    )

    mismatched_face = [make_tracked_face(1, status=IdentityStatus.MISMATCH)]

    # t=1000ms
    assert (
        len(
            engine.process_observation(
                1000,
                mismatched_face,
                acceptable_quality,
                primary_identity_status=IdentityStatus.MISMATCH,
                identity_similarity_score=0.12,
            )
        )
        == 0
    )

    # t=2600ms: duration 1600ms >= 1500ms -> Confirmed IDENTITY_MISMATCH
    events = engine.process_observation(
        2600,
        mismatched_face,
        acceptable_quality,
        primary_identity_status=IdentityStatus.MISMATCH,
        identity_similarity_score=0.12,
    )
    assert len(events) == 1
    assert events[0].event_type == FraudEventType.IDENTITY_MISMATCH
    assert events[0].severity == FraudSeverity.CRITICAL


@pytest.mark.unit
def test_poor_quality_suppresses_identity_penalty(poor_quality: ImageQualityAssessment) -> None:
    engine = TemporalEventEngine(
        session_id="sess_123",
        tenant_id="tenant_abc",
        identity_mismatch_debounce_ms=1000,
    )

    mismatched_face = [make_tracked_face(1, status=IdentityStatus.MISMATCH)]

    # On poor quality, event engine must emit LOW_IMAGE_QUALITY and NOT accumulate identity mismatch
    events = engine.process_observation(
        1000,
        mismatched_face,
        poor_quality,
        primary_identity_status=IdentityStatus.MISMATCH,
        identity_similarity_score=0.10,
    )
    assert len(events) == 1
    assert events[0].event_type == FraudEventType.LOW_IMAGE_QUALITY

    # Next frame also poor quality: identity mismatch remains suppressed
    events_next = engine.process_observation(
        2500,
        mismatched_face,
        poor_quality,
        primary_identity_status=IdentityStatus.MISMATCH,
        identity_similarity_score=0.10,
    )
    assert not any(e.event_type == FraudEventType.IDENTITY_MISMATCH for e in events_next)
