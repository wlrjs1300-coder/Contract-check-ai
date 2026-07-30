from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SecretLifecycleState(StrEnum):
    PROVISIONED = "provisioned"
    ACTIVE = "active"
    ROTATION_PENDING = "rotation_pending"
    DECRYPT_ONLY = "decrypt_only"
    COMPATIBILITY = "compatibility"
    RETIRED = "retired"
    REVOKED = "revoked"


@dataclass(frozen=True)
class SecretDefinition:
    name: str
    purpose: str
    services: tuple[str, ...]
    lifecycle_states: tuple[SecretLifecycleState, ...]
    rotation_impact: str
    frontend_allowed: bool = False
    currently_configured: bool = True


_STANDARD_STATES = (
    SecretLifecycleState.PROVISIONED,
    SecretLifecycleState.ACTIVE,
    SecretLifecycleState.ROTATION_PENDING,
    SecretLifecycleState.RETIRED,
    SecretLifecycleState.REVOKED,
)
_KEYRING_STATES = (
    SecretLifecycleState.PROVISIONED,
    SecretLifecycleState.ACTIVE,
    SecretLifecycleState.ROTATION_PENDING,
    SecretLifecycleState.DECRYPT_ONLY,
    SecretLifecycleState.RETIRED,
    SecretLifecycleState.REVOKED,
)
_COMPATIBILITY_STATES = (
    SecretLifecycleState.PROVISIONED,
    SecretLifecycleState.ACTIVE,
    SecretLifecycleState.ROTATION_PENDING,
    SecretLifecycleState.COMPATIBILITY,
    SecretLifecycleState.RETIRED,
    SecretLifecycleState.REVOKED,
)


SECRET_INVENTORY = (
    SecretDefinition(
        name="DATABASE_URL",
        purpose="Backend database connection; may embed application credentials.",
        services=("api", "worker", "migrate"),
        lifecycle_states=_COMPATIBILITY_STATES,
        rotation_impact="Coordinated credential change, connection drain, restart, and rollback.",
    ),
    SecretDefinition(
        name="MYSQL_PASSWORD",
        purpose="MySQL application-user initialization credential.",
        services=("contract-db",),
        lifecycle_states=_COMPATIBILITY_STATES,
        rotation_impact="Coordinate with DATABASE_URL; Compose initialization does not rotate an existing DB.",
    ),
    SecretDefinition(
        name="MYSQL_ROOT_PASSWORD",
        purpose="MySQL root initialization credential.",
        services=("contract-db",),
        lifecycle_states=_STANDARD_STATES,
        rotation_impact="Database-administration procedure; never inject into Backend services.",
    ),
    SecretDefinition(
        name="JWT_SECRET",
        purpose="HS256 access-token signing and verification.",
        services=("api",),
        lifecycle_states=_STANDARD_STATES,
        rotation_impact="Existing access tokens become invalid; users must sign in again.",
    ),
    SecretDefinition(
        name="EMAIL_LOOKUP_HMAC_KEY",
        purpose="Deterministic account email lookup hash.",
        services=("api",),
        lifecycle_states=_COMPATIBILITY_STATES,
        rotation_impact="Requires a separately designed dual-lookup or hash migration; no simple replacement.",
    ),
    SecretDefinition(
        name="DATA_ENCRYPTION_KEYS_JSON",
        purpose="AES-256-GCM keyring material for stored application data.",
        services=("api", "worker"),
        lifecycle_states=_KEYRING_STATES,
        rotation_impact="Add active key, retain old decrypt-only key, inventory and re-encrypt before retirement.",
    ),
    SecretDefinition(
        name="DATA_ENCRYPTION_ACTIVE_KEY_ID",
        purpose="Non-secret identifier selecting the active encryption key.",
        services=("api", "worker"),
        lifecycle_states=_KEYRING_STATES,
        rotation_impact="Change only with a matching active keyring entry; key ID is metadata, not key material.",
    ),
    SecretDefinition(
        name="PROVIDER_API_KEY",
        purpose="Reserved contract for a future external Provider credential.",
        services=("api", "worker"),
        lifecycle_states=_STANDARD_STATES,
        rotation_impact="Adapter-specific replacement and rollback; external calls remain disabled today.",
        currently_configured=False,
    ),
)

BACKEND_SECRET_NAMES = frozenset(
    definition.name
    for definition in SECRET_INVENTORY
    if any(service in {"api", "worker", "migrate"} for service in definition.services)
    and definition.name != "DATA_ENCRYPTION_ACTIVE_KEY_ID"
)
PUBLIC_FRONTEND_CONFIGURATION = frozenset({"VITE_API_BASE_URL"})


def secret_names_for_service(service: str) -> frozenset[str]:
    return frozenset(
        definition.name
        for definition in SECRET_INVENTORY
        if service in definition.services and definition.currently_configured
    )


def inventory_metadata() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "name": definition.name,
            "purpose": definition.purpose,
            "services": definition.services,
            "lifecycle_states": tuple(definition.lifecycle_states),
            "rotation_impact": definition.rotation_impact,
            "frontend_allowed": definition.frontend_allowed,
            "currently_configured": definition.currently_configured,
        }
        for definition in SECRET_INVENTORY
    )
