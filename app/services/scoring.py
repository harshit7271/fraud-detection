from collections import Counter

from pydantic import BaseModel, Field

from app.schemas.fraud import (
    FraudEvent,
    FraudEventType,
    FraudStatus,
    Recommendation,
    RiskAssessment,
    RiskLevel,
)

DEFAULT_EVENT_WEIGHTS: dict[FraudEventType, float] = {
    FraudEventType.IDENTITY_MISMATCH: 50.0,
    FraudEventType.MULTIPLE_FACES: 30.0,
    FraudEventType.FACE_ABSENT: 20.0,
    FraudEventType.PRESENTATION_ATTACK_SUSPECTED: 60.0,
    FraudEventType.FACE_OCCLUSION: 15.0,
    FraudEventType.VIDEO_FEED_INTERRUPTED: 20.0,
    FraudEventType.NO_FACE_DETECTED: 10.0,
    FraudEventType.LOW_IMAGE_QUALITY: 0.0,  # Image quality deficiencies do not directly trigger fraud score
}


class TenantScoringPolicy(BaseModel):
    event_weights: dict[FraudEventType, float] = Field(default_factory=lambda: dict(DEFAULT_EVENT_WEIGHTS))
    critical_threshold: float = Field(default=75.0)
    high_threshold: float = Field(default=50.0)
    medium_threshold: float = Field(default=25.0)


class RiskScoringEngine:
    """
    Configurable Risk Scoring Engine.
    Aggregates confirmed fraud events using tenant-defined weight matrices
    into an auditable 0-100 score, categorized risk band, and recommendation.
    """

    def __init__(self, policy: TenantScoringPolicy | None = None) -> None:
        self.policy = policy or TenantScoringPolicy()

    def calculate_risk(
        self,
        events: list[FraudEvent],
    ) -> RiskAssessment:
        if not events:
            return RiskAssessment(
                risk_score=0.0,
                risk_level=RiskLevel.LOW,
                fraud_status=FraudStatus.CLEARED,
                recommendation=Recommendation.NO_ACTION,
                total_events=0,
                event_breakdown={},
                scoring_explanation=["No suspicious events recorded in this session."],
            )

        # Count occurrences per event type
        type_counts = Counter(e.event_type for e in events)
        event_breakdown = {k.value: v for k, v in type_counts.items()}

        raw_score = 0.0
        explanations: list[str] = []

        # Accumulate weighted score with diminishing returns for repeated events
        for event_type, count in type_counts.items():
            base_weight = self.policy.event_weights.get(event_type, 0.0)
            if base_weight == 0.0:
                continue

            # First event contributes 100% of weight, subsequent events add 50%
            effective_contribution = base_weight + (count - 1) * (base_weight * 0.5)
            raw_score += effective_contribution
            explanations.append(
                f"{event_type.value}: {count} event(s) contributed {effective_contribution:.1f} points "
                f"(base weight: {base_weight:.1f})"
            )

        # Bounded between 0.0 and 100.0
        normalized_score = min(100.0, max(0.0, raw_score))

        # Determine Risk Band & Fraud Status
        if normalized_score >= self.policy.critical_threshold:
            risk_level = RiskLevel.CRITICAL
            fraud_status = FraudStatus.CONFIRMED_FRAUD
            recommendation = Recommendation.ESCALATE
        elif normalized_score >= self.policy.high_threshold:
            risk_level = RiskLevel.HIGH
            fraud_status = FraudStatus.SUSPICIOUS
            recommendation = Recommendation.REVIEW_REQUIRED
        elif normalized_score >= self.policy.medium_threshold:
            risk_level = RiskLevel.MEDIUM
            fraud_status = FraudStatus.SUSPICIOUS
            recommendation = Recommendation.CONTINUE_MONITORING
        else:
            risk_level = RiskLevel.LOW
            fraud_status = FraudStatus.CLEARED
            recommendation = Recommendation.NO_ACTION

        return RiskAssessment(
            risk_score=round(normalized_score, 1),
            risk_level=risk_level,
            fraud_status=fraud_status,
            recommendation=recommendation,
            total_events=len(events),
            event_breakdown=event_breakdown,
            scoring_explanation=explanations,
        )
