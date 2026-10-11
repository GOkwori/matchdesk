"""ID3M host-owned, explicitly refreshed workforce JWKS trust for future sandbox use.

No identity tenant, login provider or HTTP route is activated by this module.
The only network location is the exact pinned public Entra tenant authority.
A trusted bootstrap/scheduler must explicitly refresh; token verification NEVER
initiates requests, reads request-supplied key URLs, or accepts stale keys.
"""

from __future__ import annotations

import base64
import json
import math
import re
import ssl
import time
from dataclasses import dataclass
from http.client import HTTPSConnection
from threading import RLock
from typing import Callable, Protocol, cast

from jwt import PyJWK

_DENIED = "ID3M workforce signing-key trust denied"
_TENANT_ID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z")
_KEY_ID = re.compile(r"[A-Za-z0-9._+\-/=]{1,128}\Z")
_RSA_MODULUS = re.compile(r"[A-Za-z0-9_-]{300,710}\Z")
_TEMPLATE_ISSUER = "https://login.microsoftonline.com/{tenantid}/v2.0"
_HOST = "login.microsoftonline.com"
_METADATA_LIMIT = 65536
_KEYS_LIMIT = 262144


@dataclass(frozen=True, slots=True)
class WorkforceMetadataPolicy:
    """Single-tenant host configuration, not a tenant selected from a JWT."""

    tenant_id: str
    max_cache_seconds: int = 3600

    def __post_init__(self) -> None:
        """Reject generic authorities and unbounded signing-key cache ages."""
        if (
            type(self.tenant_id) is not str
            or _TENANT_ID.fullmatch(self.tenant_id) is None
            or type(self.max_cache_seconds) is not int
            or not 300 <= self.max_cache_seconds <= 3600
        ):
            raise ValueError("ID3M requires a concrete pinned workforce tenant")

    @property
    def issuer(self) -> str:
        """Return the sole allowed issuer for downstream JWT validation."""
        return f"https://{_HOST}/{self.tenant_id}/v2.0"

    @property
    def metadata_path(self) -> str:
        """Provide the exact tenant-specific v2 discovery path."""
        return f"/{self.tenant_id}/v2.0/.well-known/openid-configuration"

    @property
    def keys_path(self) -> str:
        """Provide the exact tenant-specific JWKS path."""
        return f"/{self.tenant_id}/discovery/v2.0/keys"

    @property
    def keys_uri(self) -> str:
        """Pin the JWKS URL independently of any returned metadata."""
        return f"https://{_HOST}{self.keys_path}"


class WorkforceDocumentTransport(Protocol):
    """Only a trusted host can supply bounded public discovery documents."""

    def get(self, path: str, max_bytes: int) -> bytes:
        """Read exactly one host-allowlisted TLS document without redirects."""
        ...


class PinnedEntraHttpsTransport:
    """Fixed-host direct HTTPS transport; no redirects, proxies or retries."""

    def __init__(self, policy: WorkforceMetadataPolicy) -> None:
        """Pin paths at host construction, never from an incoming token."""
        if type(policy) is not WorkforceMetadataPolicy:
            raise ValueError("An exact workforce metadata policy is required")
        self._paths = {
            policy.metadata_path: _METADATA_LIMIT,
            policy.keys_path: _KEYS_LIMIT,
        }

    def get(self, path: str, max_bytes: int) -> bytes:
        """Make one fixed-host verified-TLS request and cap response bytes."""
        if type(path) is not str or self._paths.get(path) != max_bytes:
            raise PermissionError(_DENIED)
        conn: HTTPSConnection | None = None
        try:
            conn = HTTPSConnection(_HOST, timeout=5.0, context=ssl.create_default_context())
            conn.request(
                "GET",
                path,
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                    "Cache-Control": "no-store",
                    "Connection": "close",
                },
            )
            response = conn.getresponse()
            headers = response.getheaders()
            content_types = [value for name, value in headers if name.lower() == "content-type"]
            encodings = [value for name, value in headers if name.lower() == "content-encoding"]
            if (
                response.status != 200
                or len(content_types) != 1
                or content_types[0].split(";", 1)[0].strip().lower() != "application/json"
                or len(encodings) > 1
                or any(value.strip().lower() != "identity" for value in encodings)
                or any(name.lower() == "location" for name, _ in headers)
            ):
                raise PermissionError(_DENIED)
            body = response.read(max_bytes + 1)
            if not 0 < len(body) <= max_bytes:
                raise PermissionError(_DENIED)
            return body
        except Exception:
            # A timeout, certificate failure, bad metadata or failed network
            # request cannot trigger a fallback to unsigned or stale keys.
            raise PermissionError(_DENIED) from None
        finally:
            if conn is not None:
                conn.close()


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject JSON duplicate keys, including nested key material."""
    result: dict[str, object] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("Ambiguous identity metadata")
        result[name] = value
    return result


def _reject_constant(value: str) -> object:
    """Exclude non-JSON NaN/Infinity values from trust material."""
    raise ValueError("Invalid identity metadata constant")


def _parse_document(body: bytes, limit: int) -> dict[str, object]:
    """Parse bounded strict UTF-8 JSON with no duplicate properties."""
    if type(body) is not bytes or not 0 < len(body) <= limit:
        raise ValueError("Invalid identity metadata size")
    result: object = json.loads(
        body.decode("utf-8"),
        object_pairs_hook=_unique_pairs,
        parse_constant=_reject_constant,
    )
    if type(result) is not dict:
        raise ValueError("Identity metadata must be an object")
    return cast(dict[str, object], result)


def _trusted_jwks(document: dict[str, object], issuer: str) -> dict[str, PyJWK]:
    """Import bounded RSA public keys only when issued for the pinned tenant.

    The tenant-specific JWKS can contain keys with a template issuer or keys
    outside this resource tenant. Foreign-issuer entries are never selected.
    """
    entries = document.get("keys")
    if type(entries) is not list or not 1 <= len(entries) <= 64:
        raise ValueError("Workforce JWKS has no bounded key set")
    approved: dict[str, PyJWK] = {}
    seen: set[str] = set()
    for entry in entries:
        if type(entry) is not dict:
            raise ValueError("Invalid workforce JWK entry")
        kid = entry.get("kid")
        if type(kid) is not str or _KEY_ID.fullmatch(kid) is None or kid in seen:
            raise ValueError("Missing or duplicate workforce key identifier")
        seen.add(kid)
        if entry.get("issuer") not in (None, issuer, _TEMPLATE_ISSUER):
            continue
        if (
            entry.get("kty") != "RSA"
            or entry.get("use") != "sig"
            or entry.get("alg") not in (None, "RS256")
            or entry.get("key_ops") not in (None, ["verify"])
        ):
            continue
        modulus = entry.get("n")
        exponent = entry.get("e")
        if (
            type(modulus) is not str
            or _RSA_MODULUS.fullmatch(modulus) is None
            or exponent != "AQAB"
        ):
            raise ValueError("Unsupported workforce RSA key")
        # Accept only canonical RSA public limbs; do not parse x5c supplied
        # certificates, private JWK fields, URLs or metadata overrides.
        decoded = base64.urlsafe_b64decode(modulus + "=" * (-len(modulus) % 4))
        if not 2048 <= int.from_bytes(decoded, "big").bit_length() <= 4096:
            raise ValueError("Workforce signing key has unsafe length")
        approved[kid] = PyJWK.from_dict(
            {"kty": "RSA", "use": "sig", "kid": kid, "alg": "RS256", "n": modulus, "e": exponent}
        )
    if not approved:
        raise ValueError("No matching workforce signing key")
    return approved


class ExplicitWorkforceKeyResolver:
    """TrustedKeyResolver-compatible cache with NO network on token lookup."""

    def __init__(
        self,
        *,
        policy: WorkforceMetadataPolicy,
        transport: WorkforceDocumentTransport,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        """Accept fixed host-owned dependencies; begin deny-all until primed."""
        if type(policy) is not WorkforceMetadataPolicy:
            raise ValueError("An exact workforce metadata policy is required")
        self._policy = policy
        self._transport = transport
        self._monotonic = monotonic
        self._keys: dict[str, PyJWK] = {}
        self._expires_at = 0.0
        self._lock = RLock()

    def refresh(self) -> int:
        """Explicitly bootstrap or rotate public keys; reject stale fallbacks.

        Only an authenticated host startup/refresh job may call this method.
        No token, HTTP request or agent event is allowed to trigger refresh.
        A failed refresh clears all previous trust, including on transport error.
        """
        with self._lock:
            self._keys = {}
            self._expires_at = 0.0
            try:
                metadata = _parse_document(
                    self._transport.get(self._policy.metadata_path, _METADATA_LIMIT),
                    _METADATA_LIMIT,
                )
                if (
                    metadata.get("issuer") != self._policy.issuer
                    or metadata.get("jwks_uri") != self._policy.keys_uri
                ):
                    raise ValueError("Workforce discovery authority differs from policy")
                jwks = _parse_document(
                    self._transport.get(self._policy.keys_path, _KEYS_LIMIT),
                    _KEYS_LIMIT,
                )
                keys = _trusted_jwks(jwks, self._policy.issuer)
                current = self._monotonic()
                if type(current) is not float or not math.isfinite(current):
                    raise ValueError("Invalid trusted refresh clock")
                self._keys = keys
                self._expires_at = current + self._policy.max_cache_seconds
                return len(keys)
            except Exception:
                self._keys = {}
                self._expires_at = 0.0
                raise PermissionError(_DENIED) from None

    def resolve(self, *, issuer: str, kid: str) -> PyJWK | None:
        """Resolve a valid unexpired key offline; never refresh from a JWT."""
        with self._lock:
            current = self._monotonic()
            if (
                issuer != self._policy.issuer
                or type(kid) is not str
                or _KEY_ID.fullmatch(kid) is None
                or type(current) is not float
                or not math.isfinite(current)
                or current >= self._expires_at
            ):
                return None
            return self._keys.get(kid)
