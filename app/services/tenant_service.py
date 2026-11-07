import hashlib
import hmac
from dataclasses import dataclass, field


@dataclass
class EventWeights:
    face_absent: float = 25.0
    multiple_faces: float = 35.0
    identity_mismatch: float = 40.0
    suspicious_liveness: float = 30.0


@dataclass
class RiskBandRange:
    min_score: float
    max_score: float


def hash_api_key(api_key: str, salt: str = "faceguard_tenant_salt_2026") -> str:
    """Computes a cryptographically salted SHA-256 digest of an API key."""
    return hashlib.sha256(f"{salt}:{api_key}".encode()).hexdigest()


@dataclass
class TenantProfile:
    tenant_id: str
    slug: str
    name: str
    api_key_hash: str
    face_match_threshold: float = 0.38
    face_uncertain_threshold: float = 0.25
    multiple_faces_debounce_ms: int = 2000
    face_absence_debounce_ms: int = 3000
    event_weights: EventWeights = field(
        default_factory=lambda: EventWeights(
            face_absent=25.0,
            multiple_faces=35.0,
            identity_mismatch=40.0,
            suspicious_liveness=30.0,
        )
    )
    risk_bands: dict[str, RiskBandRange] = field(
        default_factory=lambda: {
            "LOW": RiskBandRange(min_score=0.0, max_score=25.0),
            "MEDIUM": RiskBandRange(min_score=25.0, max_score=50.0),
            "HIGH": RiskBandRange(min_score=50.0, max_score=75.0),
            "CRITICAL": RiskBandRange(min_score=75.0, max_score=100.0),
        }
    )


# Seed enterprise tenant configurations with hashed credentials
_PREDEFINED_TENANTS: dict[str, TenantProfile] = {
    "alorica": TenantProfile(
        tenant_id="00000000-0000-0000-0000-000000000001",
        slug="alorica",
        name="Alorica Global Services",
        api_key_hash=hash_api_key("alorica-live-key-2026"),
        face_match_threshold=0.40,
        face_uncertain_threshold=0.28,
        multiple_faces_debounce_ms=2000,
        face_absence_debounce_ms=3000,
        event_weights=EventWeights(
            face_absent=20.0,
            multiple_faces=35.0,
            identity_mismatch=45.0,
            suspicious_liveness=30.0,
        ),
    ),
    "sagility": TenantProfile(
        tenant_id="00000000-0000-0000-0000-000000000002",
        slug="sagility",
        name="Sagility Health BPO",
        api_key_hash=hash_api_key("sagility-live-key-2026"),
        face_match_threshold=0.38,
        face_uncertain_threshold=0.25,
        multiple_faces_debounce_ms=1500,  # Stricter multiple-face debounce for healthcare
        face_absence_debounce_ms=3000,
        event_weights=EventWeights(
            face_absent=25.0,
            multiple_faces=40.0,
            identity_mismatch=35.0,
            suspicious_liveness=30.0,
        ),
    ),
    "mastek": TenantProfile(
        tenant_id="00000000-0000-0000-0000-000000000003",
        slug="mastek",
        name="Mastek Enterprise IT",
        api_key_hash=hash_api_key("mastek-live-key-2026"),
        face_match_threshold=0.38,
        face_uncertain_threshold=0.25,
        multiple_faces_debounce_ms=2000,
        face_absence_debounce_ms=2500,  # Stricter absence debounce for engineering
        event_weights=EventWeights(
            face_absent=30.0,
            multiple_faces=30.0,
            identity_mismatch=40.0,
            suspicious_liveness=30.0,
        ),
    ),
    "test-tenant": TenantProfile(
        tenant_id="00000000-0000-0000-0000-000000000099",
        slug="test-tenant",
        name="Test Development Tenant",
        api_key_hash=hash_api_key("test-tenant-key-dev"),
    ),
}


class TenantService:
    """
    Manages tenant authentication, credential verification, and dynamic configuration
    retrieval ensuring strict multi-tenant boundary isolation.
    """

    def __init__(self) -> None:
        self._tenants: dict[str, TenantProfile] = dict(_PREDEFINED_TENANTS)

    def authenticate_key(self, raw_api_key: str) -> TenantProfile | None:
        """
        Validates raw API key using constant-time hash comparison against known tenants.
        """
        calculated_hash = hash_api_key(raw_api_key)
        for tenant in self._tenants.values():
            if hmac.compare_digest(tenant.api_key_hash, calculated_hash):
                return tenant
        return None

    def get_tenant_by_id_or_slug(self, identifier: str) -> TenantProfile | None:
        # Check by slug
        if identifier in self._tenants:
            return self._tenants[identifier]
        clean_slug = identifier.replace("-test", "").replace("-live", "")
        if clean_slug in self._tenants:
            return self._tenants[clean_slug]
        # Check by tenant_id UUID
        for tenant in self._tenants.values():
            if tenant.tenant_id == identifier:
                return tenant
        return None

    def register_custom_tenant(self, profile: TenantProfile) -> None:
        self._tenants[profile.slug] = profile


_tenant_service = TenantService()


def get_tenant_service() -> TenantService:
    return _tenant_service
