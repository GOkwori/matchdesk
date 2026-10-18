"""Fail-closed OIDC access-token verification for human producer commands.

This is an offline-verifiable host boundary, not a network JWKS client or HTTP
authentication handler. Trusted signing keys and session grants are supplied by
the host; request-provided role, tenant and entitlement claims grant no authority.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Mapping, Protocol

import jwt
from jwt import InvalidTokenError, PyJWK
from jwt.exceptions import InvalidAlgorithmError

from matchdesk.domain.producer_commands import HostVerifiedActor, ProducerRole


@dataclass(frozen=True)
class ProducerIdentityPolicy:
    """Explicit single-tenant API access-token policy supplied by the server."""

    issuer: str
    audience: str
    tenant_id: str
    client_ids: frozenset[str]
    required_scope: str = "MatchDesk.Producer.Access"
    # Optional for read-only callers; privileged issuer MUST configure a
    # reviewed tenant Conditional Access context (c1-c99) independently.
    required_auth_context: str | None = None
    max_token_age_seconds: int = 3600
    clock_leeway_seconds: int = 30

    def __post_init__(self) -> None:
        """Refuse wildcard trust, missing allowlists and unbounded expiry grace."""
        # Privileged tokens require the exact configured workforce issuer;
        # customer External ID and common/organizations remain untrusted.
        if self.issuer != f"https://login.microsoftonline.com/{self.tenant_id}/v2.0":
            raise ValueError("Producer policy requires the exact workforce issuer")
        if self.required_auth_context is not None and (
            type(self.required_auth_context) is not str
            or re.fullmatch(r"c(?:[1-9]|[1-9][0-9])", self.required_auth_context) is None
        ):
            raise ValueError("Producer step-up requires a pinned Entra authentication context")
        if (
            not self.issuer.startswith("https://")
            or not self.issuer.endswith("/v2.0")
            or "{" in self.issuer
            or not self.audience.strip()
            or not self.tenant_id.strip()
            or not self.client_ids
            or any(not c.strip() for c in self.client_ids)
            or not self.required_scope.strip()
            or not 60 <= self.max_token_age_seconds <= 3600
            or not 0 <= self.clock_leeway_seconds <= 60
        ):
            raise ValueError("OIDC producer identity policy requires explicit bounded trust")


class TrustedKeyResolver(Protocol):
    """Resolve only a preconfigured issuer's public signing key by token key ID."""

    def resolve(self, *, issuer: str, kid: str) -> PyJWK | None:
        """Return an issuer-bound trusted public key; never fetch a token-provided URL."""


class EntitlementResolver(Protocol):
    """Query server-owned producer role and session membership for a verified subject."""

    def resolve(
        self, *, tenant_id: str, subject: str
    ) -> tuple[frozenset[ProducerRole], frozenset[str]] | None:
        """Return trusted grants, or None on absence or lookup failure."""


def verify_producer_access_token(
    token: str,
    *,
    policy: ProducerIdentityPolicy,
    keys: TrustedKeyResolver,
    entitlements: EntitlementResolver,
    now: datetime | None = None,
) -> HostVerifiedActor:
    """Validate delegated RS256 access tokens, then apply server-side producer grants.

    Scope/authorized-client claims gate *access to this API*, never grant producer
    role or session membership. JWT headers may identify a kid, but cannot set
    algorithms, keys, issuers or key-fetch URLs. Tokens are never logged or stored.
    """
    if not token or len(token) > 16384 or token.count(".") != 2:
        raise PermissionError("Invalid producer access token")
    try:
        header = jwt.get_unverified_header(token)
        if (
            header.get("alg") != "RS256"
            or not isinstance(header.get("kid"), str)
            or not 1 <= len(header["kid"]) <= 128
            or header.get("crit")
            or header.get("jku")
            or header.get("jwk")
            or header.get("x5u")
        ):
            raise PermissionError("Untrusted JWT signing header")
        key = keys.resolve(issuer=policy.issuer, kid=header["kid"])
        if key is None or key.algorithm_name != "RS256" or key.key_type != "RSA":
            raise PermissionError("Unknown producer signing key")

        current = now or datetime.now(timezone.utc)
        timestamp = current.timestamp()
        claims = jwt.decode(
            token,
            key=key.key,
            algorithms=["RS256"],
            issuer=policy.issuer,
            audience=policy.audience,
            leeway=policy.clock_leeway_seconds,
            options={"require": ["iss", "aud", "exp", "nbf", "iat", "sub", "tid"]},
        )
        # PyJWT checks signatures, clock claims, issuer and audience. Explicit
        # integer checks reject coercions and restrict token lifetime/age.
        for field in ("exp", "nbf", "iat"):
            if type(claims.get(field)) is not int:
                raise PermissionError("Invalid producer token time claims")
        if (
            claims["iat"] > timestamp + policy.clock_leeway_seconds
            or claims["nbf"] > timestamp + policy.clock_leeway_seconds
            or claims["exp"] <= timestamp - policy.clock_leeway_seconds
            or claims["exp"] - claims["iat"] > policy.max_token_age_seconds
            or timestamp - claims["iat"]
            > policy.max_token_age_seconds + policy.clock_leeway_seconds
        ):
            raise PermissionError("Producer token lifetime is outside policy")
        if (
            claims.get("tid") != policy.tenant_id
            or not isinstance(claims.get("sub"), str)
            or not claims["sub"].strip()
            or claims.get("azp") not in policy.client_ids
            or not isinstance(claims.get("scp"), str)
            or policy.required_scope not in claims["scp"].split()
            or "idtyp" in claims
            and claims["idtyp"] == "app"
        ):
            raise PermissionError("Producer token is outside delegated API policy")
        # Only the *signature-verified API access token's* array of Entra
        # authentication context IDs may satisfy this opt-in requirement.
        # A signed 'amr' label, unverified header or browser flag cannot replace
        # a tenant-pinned Conditional Access authentication context. Entra CA
        # policy must separately be verified to require MFA/step-up for this ID.
        if policy.required_auth_context is not None:
            contexts = claims.get("acrs")
            if (
                type(contexts) is not list
                or not all(type(value) is str for value in contexts)
                or policy.required_auth_context not in contexts
            ):
                raise PermissionError("Producer authentication context was not satisfied")
        grants = entitlements.resolve(tenant_id=policy.tenant_id, subject=claims["sub"])
        if grants is None:
            raise PermissionError("Producer has no current server-side grants")
        roles, sessions = grants
        if "producer" not in roles or not sessions:
            raise PermissionError("Producer lacks server-side role or session access")
        return HostVerifiedActor(
            subject=claims["sub"],
            tenant_id=policy.tenant_id,
            issuer=policy.issuer,
            roles=roles,
            permitted_sessions=sessions,
        )
    except (InvalidTokenError, InvalidAlgorithmError, KeyError, TypeError, ValueError) as exc:
        raise PermissionError("Producer access token validation failed") from exc


class StaticTrustedKeys:
    """Offline, issuer-scoped RSA JWKs for tests and reviewed host provisioning."""

    def __init__(self, issuer: str, keys: Mapping[str, PyJWK]) -> None:
        """Freeze an explicit key ID allowlist without fetching arbitrary endpoints."""
        if not issuer or not keys:
            raise ValueError("Trusted signing keys require issuer and key IDs")
        self._issuer = issuer
        self._keys = dict(keys)

    def resolve(self, *, issuer: str, kid: str) -> PyJWK | None:
        """Refuse key reuse across issuers and unknown rotations."""
        if issuer != self._issuer:
            return None
        return self._keys.get(kid)
