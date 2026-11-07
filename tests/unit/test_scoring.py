import pytest

from app.schemas.fraud import (
    FraudEvent,
    FraudEventType,
    FraudSeverity,
    FraudStatus,
    Recommendation,
    RiskLevel,
)
from app.services.scoring import RiskScoringEngine, TenantScoringPolicy


def make_event(event_type: FraudEventType, severity: FraudSeverity = FraudSeverity.MEDIUM) -> FraudEvent:
    return FraudEvent(
        session_id="sess_123",
        tenant_id="tenant_abc",
        event_type=event_type,
        timestamp_ms=1000,
        duration_ms=2500,
        confidence=0.95,
        severity=severity,
    )


@pytest.mark.unit
def test_scoring_zero_events() -> None:
    engine = RiskScoringEngine()
    assessment = engine.calculate_risk([])

    assert assessment.risk_score == 0.0
    assert assessment.risk_level == RiskLevel.LOW
    assert assessment.fraud_status == FraudStatus.CLEARED
    assert assessment.recommendation == Recommendation.NO_ACTION
    assert assessment.total_events == 0


@pytest.mark.unit
def test_scoring_single_absence_event() -> None:
    engine = RiskScoringEngine()
    ev = make_event(FraudEventType.FACE_ABSENT)
    assessment = engine.calculate_risk([ev])

    # FACE_ABSENT base weight = 20.0 -> Score = 20.0
    assert assessment.risk_score == 20.0
    assert assessment.risk_level == RiskLevel.LOW
    assert assessment.recommendation == Recommendation.NO_ACTION


@pytest.mark.unit
def test_scoring_identity_mismatch_event() -> None:
    engine = RiskScoringEngine()
    ev = make_event(FraudEventType.IDENTITY_MISMATCH, severity=FraudSeverity.HIGH)
    assessment = engine.calculate_risk([ev])

    # IDENTITY_MISMATCH base weight = 50.0 -> Score = 50.0 -> HIGH -> REVIEW_REQUIRED
    assert assessment.risk_score == 50.0
    assert assessment.risk_level == RiskLevel.HIGH
    assert assessment.fraud_status == FraudStatus.SUSPICIOUS
    assert assessment.recommendation == Recommendation.REVIEW_REQUIRED


@pytest.mark.unit
def test_scoring_critical_composite_events() -> None:
    engine = RiskScoringEngine()
    ev1 = make_event(FraudEventType.IDENTITY_MISMATCH)  # 50 pts
    ev2 = make_event(FraudEventType.MULTIPLE_FACES)     # 30 pts
    assessment = engine.calculate_risk([ev1, ev2])

    # 50 + 30 = 80 pts -> CRITICAL -> CONFIRMED_FRAUD -> ESCALATE
    assert assessment.risk_score == 80.0
    assert assessment.risk_level == RiskLevel.CRITICAL
    assert assessment.fraud_status == FraudStatus.CONFIRMED_FRAUD
    assert assessment.recommendation == Recommendation.ESCALATE


@pytest.mark.unit
def test_scoring_image_quality_zero_weight() -> None:
    engine = RiskScoringEngine()
    ev = make_event(FraudEventType.LOW_IMAGE_QUALITY, severity=FraudSeverity.LOW)
    assessment = engine.calculate_risk([ev])

    # Low image quality should not add fraud points
    assert assessment.risk_score == 0.0
    assert assessment.risk_level == RiskLevel.LOW
    assert assessment.recommendation == Recommendation.NO_ACTION


@pytest.mark.unit
def test_custom_tenant_policy() -> None:
    # Custom strict tenant policy (e.g., Alorica)
    custom_policy = TenantScoringPolicy(
        event_weights={
            FraudEventType.IDENTITY_MISMATCH: 75.0,
            FraudEventType.MULTIPLE_FACES: 40.0,
        },
        critical_threshold=70.0,
    )
    engine = RiskScoringEngine(policy=custom_policy)
    ev = make_event(FraudEventType.IDENTITY_MISMATCH)
    assessment = engine.calculate_risk([ev])

    # 75.0 points exceeds critical_threshold of 70.0 -> CRITICAL
    assert assessment.risk_score == 75.0
    assert assessment.risk_level == RiskLevel.CRITICAL
    assert assessment.recommendation == Recommendation.ESCALATE
