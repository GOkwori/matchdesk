"""Offline broker-issued ID-token validation after an OIDC code exchange.

The code exchange and trust-store refresh are separate, host-owned operations.
This verifier never fetches a JWT-supplied key, exchanges a code, creates an
account, grants producer access, or activates live identity integration.
"""

from __future__ import annotations

import hmac
from datetime import datetime, timezone

import jwt
from jwt import InvalidTokenError

from matchdesk.domain.customer_identity import (
    CustomerIdentityKey,
    CustomerSigningKeys,
)
from matchdesk.domain.oidc_login import CustomerOidcPolicy, PendingOidcExchange


def verify_broker_id_token(
    token: str,
    *,
    pending: PendingOidcExchange,
    policy: CustomerOidcPolicy,
    keys: CustomerSigningKeys,
    now: datetime | None = None,
) -> CustomerIdentityKey:
    """Verify one exact RS256 broker ID token against the unredeemed OIDC nonce.

    The ID-token audience is the OIDC client ID, not the MatchDesk API scope.
    Never trust email, identity-provider hints, groups or role claims to
    associate accounts or authorize a producer.
    """
    if not isinstance(token, str) or not 1 <= len(token) <= 16384 or token.count(".") != 2:
        raise PermissionError("Invalid OIDC ID token")
    if (
        pending.issuer != policy.broker.issuer
        or pending.client_id != policy.client_id
        or pending.token_endpoint != policy.token_endpoint
        or pending.redirect_uri != policy.redirect_uri
    ):
        raise PermissionError("OIDC exchange is not bound to the configured broker")
    try:
        header = jwt.get_unverified_header(token)
        if (
            header.get("alg") != "RS256"
            or not isinstance(header.get("kid"), str)
            or not 1 <= len(header["kid"]) <= 128
            or any(field in header for field in ("jku", "jwk", "x5u", "crit"))
        ):
            raise PermissionError("OIDC signing header is untrusted")
        jwk = keys.resolve(issuer=policy.broker.issuer, kid=header["kid"])
        if jwk is None or jwk.key_type != "RSA" or jwk.algorithm_name != "RS256":
            raise PermissionError("OIDC signing key is not trusted")
        claims = jwt.decode(
            token,
            key=jwk.key,
            algorithms=["RS256"],
            issuer=policy.broker.issuer,
            audience=policy.client_id,
            leeway=policy.broker.clock_leeway_seconds,
            options={
                "require": ["iss", "aud", "sub", "tid", "nonce", "iat", "nbf", "exp"],
                "strict_aud": True,
            },
        )
        clock = now or datetime.now(timezone.utc)
        if clock.tzinfo is None or clock.utcoffset() is None:
            raise PermissionError("OIDC clock is invalid")
        current = clock.timestamp()
        for field in ("iat", "nbf", "exp"):
            if type(claims.get(field)) is not int:
                raise PermissionError("OIDC time claim is invalid")
        nonce = claims.get("nonce")
        if (
            not isinstance(nonce, str)
            or not hmac.compare_digest(nonce, pending.nonce)
            or claims["tid"] != policy.broker.tenant_id
            or claims["iat"] > current + policy.broker.clock_leeway_seconds
            or claims["nbf"] > current + policy.broker.clock_leeway_seconds
            or claims["exp"] <= current - policy.broker.clock_leeway_seconds
            or claims["exp"] - claims["iat"] > policy.broker.max_token_age_seconds
            or current - claims["iat"]
            > policy.broker.max_token_age_seconds + policy.broker.clock_leeway_seconds
            or claims.get("idtyp") == "app"
        ):
            raise PermissionError("OIDC ID token violates host trust")
        return CustomerIdentityKey(
            issuer=policy.broker.issuer,
            tenant_id=policy.broker.tenant_id,
            subject=claims["sub"],
        )
    except (InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise PermissionError("OIDC ID token verification failed") from exc
