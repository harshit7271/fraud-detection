from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.services.tenant_service import TenantProfile, TenantService, get_tenant_service


@dataclass
class TenantContext:
    tenant_id: str
    tenant_slug: str
    tenant_name: str
    profile: TenantProfile
    is_authenticated: bool = True


def get_current_tenant(
    x_tenant_key: str | None = Header(default=None, alias="X-Tenant-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
    tenant_service: Annotated[TenantService, Depends(get_tenant_service)] = None,  # type: ignore[assignment]
) -> TenantContext:
    """
    FastAPI dependency extracting and authenticating enterprise tenant identity.
    Accepts 'X-Tenant-Key' header or 'Authorization: Bearer <key>'.
    Enforces tenant authentication and isolation using constant-time hash comparisons.
    """
    api_key = x_tenant_key

    if not api_key and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            api_key = parts[1]

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required authentication credentials (provide X-Tenant-Key or Authorization Bearer header)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    service = tenant_service or get_tenant_service()
    profile = service.authenticate_key(api_key)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or unauthorized tenant credentials",
        )

    return TenantContext(
        tenant_id=profile.slug,
        tenant_slug=profile.slug,
        tenant_name=profile.name,
        profile=profile,
        is_authenticated=True,
    )


def verify_tenant_boundary(requested_tenant_id: str, context: TenantContext) -> None:
    """
    Ensures that an explicitly passed tenant_id (in URL path, request body, or form data)
    matches the authenticated tenant's identity, preventing cross-tenant spoofing.
    """
    valid_identifiers = {context.tenant_id, context.tenant_slug, context.profile.tenant_id}
    # Backward compatibility with legacy tenant names
    alias_map = {
        "enterprise-a": "alorica",
        "enterprise-b": "sagility",
        "enterprise-c": "mastek",
        "alorica": "enterprise-a",
        "sagility": "enterprise-b",
        "mastek": "enterprise-c",
    }
    if context.tenant_slug in alias_map:
        valid_identifiers.add(alias_map[context.tenant_slug])
    if requested_tenant_id not in valid_identifiers:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Cross-tenant access forbidden: requested tenant '{requested_tenant_id}' "
                f"does not match authenticated tenant '{context.tenant_id}'."
            ),
        )
