"""Customer-broker identity verification and provider-neutral account lookup.

Apple, Google, Facebook, Microsoft and local-email methods authenticate at the
configured Entra External ID broker. MatchDesk does not accept a raw social
provider token, use email as identity, self-provision privileged roles, or
activate customer login endpoints in this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from urllib.parse import urlsplit
from uuid import UUID

import jwt
from jwt import InvalidTokenError, PyJWK


@dataclass(frozen=True)
class CustomerBrokerPolicy:
    """Exact external-tenant issuer, API audience and delegated client allowlist."""

    issuer: str
    tenant_id: str
    audience: str
    client_ids: frozenset[str]
    required_scope: str = "MatchDesk.Customer.Access"
    max_token_age_seconds: int = 3600
    clock_leeway_seconds: int = 30

    def __post_init__(self) -> None:
        """Forbid generic Microsoft authorities and arbitrary social issuers."""
        try:
            tenant = str(UUID(self.tenant_id))
            address = urlsplit(self.issuer)
        except (ValueError, AttributeError) as exc:
            raise ValueError("Customer broker requires a concrete external tenant") from exc
        host = address.hostname or ""
        if (
            tenant != self.tenant_id
            or address.scheme != "https"
            or not host.endswith(".ciamlogin.com")
            or host.count(".") != 2
            or not host.split(".")[0].replace("-", "").isalnum()
            or address.netloc != host
            or address.path != f"/{self.tenant_id}/v2.0"
            or address.query
            or address.fragment
            or not self.audience.strip()
            or "*" in self.audience
            or not self.client_ids
            or any(not client.strip() or "*" in client for client in self.client_ids)
            or not self.required_scope.strip()
            or not 60 <= self.max_token_age_seconds <= 3600
            or not 0 <= self.clock_leeway_seconds <= 60
        ):
            raise ValueError("Customer broker requires exact External ID trust policy")


@dataclass(frozen=True)
class CustomerIdentityKey:
    """Opaque internal lookup key; no email/provider claim or privileged role."""

    issuer: str
    tenant_id: str
    subject: str

    def __post_init__(self) -> None:
        """Reject malformed identity components before any account lookup."""
        if (
            not self.issuer
            or not self.tenant_id
            or not isinstance(self.subject, str)
            or not 1 <= len(self.subject) <= 256
            or self.subject != self.subject.strip()
        ):
            raise ValueError("Customer identity requires an exact broker subject")

    @property
    def lookup_key(self) -> tuple[str, str, str]:
        """Keep broker issuer and tenant in the unique key across all providers."""
        return (self.issuer, self.tenant_id, self.subject)


class CustomerSigningKeys(Protocol):
    """Resolve public keys only from a host-configured External ID issuer."""

    def resolve(self, *, issuer: str, kid: str) -> PyJWK | None:
        """Return a trusted RSA JWK or None; never follow JWT-supplied key URLs."""


class CustomerAccountDirectory(Protocol):
    """Resolve a previously provisioned account from server-owned identity rows."""

    def lookup(self, *, issuer: str, tenant_id: str, subject: str) -> str | None:
        """Return an internal account ID, never search for a matching email."""


def verify_customer_access_token(
    token: str,
    *,
    policy: CustomerBrokerPolicy,
    keys: CustomerSigningKeys,
    now: datetime | None = None,
) -> CustomerIdentityKey:
    """Validate only broker-issued delegated RS256 API tokens.

    Provider name, email, email_verified, groups, roles and upstream access
    tokens are deliberately ignored: only the broker's authenticated subject
    establishes identity, not an application role or a linked account.
    """
    if not isinstance(token, str) or not token or len(token) > 16384 or token.count(".") != 2:
        raise PermissionError("Invalid customer access token")
    try:
        header = jwt.get_unverified_header(token)
        if (
            header.get("alg") != "RS256"
            or not isinstance(header.get("kid"), str)
            or not 1 <= len(header["kid"]) <= 128
            or any(header.get(field) for field in ("jku", "jwk", "x5u", "crit"))
        ):
            raise PermissionError("Untrusted customer signing header")
        key = keys.resolve(issuer=policy.issuer, kid=header["kid"])
        if key is None or key.key_type != "RSA" or key.algorithm_name != "RS256":
            raise PermissionError("Customer signing key is not trusted")
        claims = jwt.decode(
            token,
            key=key.key,
            algorithms=["RS256"],
            issuer=policy.issuer,
            audience=policy.audience,
            leeway=policy.clock_leeway_seconds,
            options={
                "require": ["iss", "aud", "exp", "nbf", "iat", "sub", "tid"],
                "strict_aud": True,
            },
        )
        current = now or datetime.now(timezone.utc)
        timestamp = current.timestamp()
        for field in ("exp", "nbf", "iat"):
            if type(claims.get(field)) is not int:
                raise PermissionError("Invalid customer token timestamps")
        if (
            claims["iat"] > timestamp + policy.clock_leeway_seconds
            or claims["nbf"] > timestamp + policy.clock_leeway_seconds
            or claims["exp"] <= timestamp - policy.clock_leeway_seconds
            or claims["exp"] - claims["iat"] > policy.max_token_age_seconds
            or timestamp - claims["iat"]
            > policy.max_token_age_seconds + policy.clock_leeway_seconds
            or claims.get("tid") != policy.tenant_id
            or claims.get("azp") not in policy.client_ids
            or not isinstance(claims.get("scp"), str)
            or policy.required_scope not in claims["scp"].split()
            or claims.get("idtyp") == "app"
        ):
            raise PermissionError("Customer access token violates broker policy")
        return CustomerIdentityKey(
            issuer=policy.issuer,
            tenant_id=policy.tenant_id,
            subject=claims["sub"],
        )
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise PermissionError("Customer access token verification failed") from exc


def resolve_customer_account(
    identity: CustomerIdentityKey, *, directory: CustomerAccountDirectory
) -> str:
    """Look up one already registered account, without automatic email linking.

    This read-only operation never provisions an account, adds a privileged role
    or grants match access. Account creation/linking requires separate controls.
    """
    account_id = directory.lookup(
        issuer=identity.issuer, tenant_id=identity.tenant_id, subject=identity.subject
    )
    if not isinstance(account_id, str) or not 1 <= len(account_id.strip()) <= 128:
        raise PermissionError("Customer account is not registered")
    return account_id
