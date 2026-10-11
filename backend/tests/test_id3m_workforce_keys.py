"""ID3M host-pinned workforce JWKS regressions; no network or tenant activation."""

import json
from datetime import datetime, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from matchdesk.domain.id3m_workforce_keys import (
    ExplicitWorkforceKeyResolver,
    PinnedEntraHttpsTransport,
    WorkforceMetadataPolicy,
)
from matchdesk.domain.producer_identity import (
    ProducerIdentityPolicy,
    verify_producer_access_token,
)

TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
POLICY = WorkforceMetadataPolicy(tenant_id=TENANT, max_cache_seconds=300)
NOW = datetime.fromtimestamp(1800000100, timezone.utc)


class Clock:
    """Deterministic monotonic host clock, never sourced from a JWT."""

    def __init__(self):
        """Begin with a positive monotonic instant."""
        self.value = 10000.0

    def __call__(self):
        """Expose a mutable, monotonic float."""
        return self.value


class FakeTransport:
    """Only a host's exact two preapproved document paths can be retrieved."""

    def __init__(self, metadata, jwks):
        """Store simulated trusted transport bytes."""
        self.metadata = metadata
        self.jwks = jwks
        self.calls = []
        self.error = None

    def get(self, path, max_bytes):
        """Return metadata/JWKS from the test fixture, never open a socket."""
        self.calls.append((path, max_bytes))
        if self.error is not None:
            raise self.error
        if path == POLICY.metadata_path:
            return self.metadata
        if path == POLICY.keys_path:
            return self.jwks
        raise AssertionError("Unexpected remote identity path")


def raw_json(data):
    """Encode bounded JSON exactly as a mock TLS transport would."""
    return json.dumps(data, separators=(",", ":")).encode("utf-8")


def rsa_keys():
    """Generate one 2048-bit disposable public/private signing-key pair."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = private.public_key().public_numbers()

    def b64(value):
        """Encode RSA public limbs as unpadded base64url."""
        size = (value.bit_length() + 7) // 8
        return jwt.utils.base64url_encode(value.to_bytes(size, "big")).decode()

    return private, {
        "kty": "RSA",
        "kid": "reviewed-ci-key",
        "use": "sig",
        "alg": "RS256",
        "n": b64(public.n),
        "e": b64(public.e),
        "issuer": POLICY.issuer,
    }


def metadata():
    """Describe only the exact tenant-specific issuer and key URL."""
    return {"issuer": POLICY.issuer, "jwks_uri": POLICY.keys_uri}


@pytest.fixture
def prepared():
    """Provide a valid host-owned fixture, with fresh test-only signing key."""
    private, key = rsa_keys()
    transport = FakeTransport(raw_json(metadata()), raw_json({"keys": [key]}))
    clock = Clock()
    resolver = ExplicitWorkforceKeyResolver(
        policy=POLICY, transport=transport, monotonic=clock
    )
    return private, key, transport, clock, resolver


def test_cold_cache_requires_explicit_refresh_and_never_fetches_from_kid(prepared):
    """Incoming token key IDs cannot trigger outbound key discovery."""
    _, key, transport, clock, resolver = prepared
    assert resolver.resolve(issuer=POLICY.issuer, kid=key["kid"]) is None
    assert transport.calls == []
    assert resolver.refresh() == 1
    assert resolver.resolve(issuer=POLICY.issuer, kid=key["kid"]) is not None
    assert resolver.resolve(issuer=POLICY.issuer, kid="unknown-ci-key") is None
    assert resolver.resolve(issuer="https://login.microsoftonline.com/common/v2.0", kid=key["kid"]) is None
    assert len(transport.calls) == 2
    clock.value += POLICY.max_cache_seconds
    assert resolver.resolve(issuer=POLICY.issuer, kid=key["kid"]) is None
    assert len(transport.calls) == 2


class Grants:
    """Current MatchDesk producer entitlements supplied independently of JWT."""

    def resolve(self, *, tenant_id, subject):
        """Grant one synthetic producer only when server-owned tuples match."""
        if (tenant_id, subject) == (TENANT, "ci-person"):
            return frozenset({"producer"}), frozenset({"fixture-match"})
        return None


def test_refresh_keys_validate_a_real_signed_producer_token(prepared):
    """The existing producer verifier consumes host-cached keys and grants."""
    private, _, transport, _, resolver = prepared
    assert resolver.refresh() == 1
    timestamp = int(NOW.timestamp())
    claims = {
        "iss": POLICY.issuer,
        "aud": "api://matchdesk-workforce-ci",
        "tid": TENANT,
        "sub": "ci-person",
        "azp": "trusted-ci-frontend",
        "scp": "MatchDesk.Producer.Access",
        "iat": timestamp - 30,
        "nbf": timestamp - 30,
        "exp": timestamp + 180,
    }
    token = jwt.encode(
        claims, private, algorithm="RS256", headers={"kid": "reviewed-ci-key"}
    )
    actor = verify_producer_access_token(
        token,
        policy=ProducerIdentityPolicy(
            issuer=POLICY.issuer,
            audience="api://matchdesk-workforce-ci",
            tenant_id=TENANT,
            client_ids=frozenset({"trusted-ci-frontend"}),
        ),
        keys=resolver,
        entitlements=Grants(),
        now=NOW,
    )
    assert actor.subject == "ci-person"
    assert actor.roles == frozenset({"producer"})
    assert len(transport.calls) == 2


def test_refresh_rotates_keys_atomically_and_cannot_reuse_old_kid(prepared):
    """Key rotation never falls back to a stale RSA public key."""
    _, key, transport, clock, resolver = prepared
    resolver.refresh()
    private2, new_key = rsa_keys()
    del private2
    new_key["kid"] = "rotated-ci-key"
    transport.jwks = raw_json({"keys": [new_key]})
    assert resolver.refresh() == 1
    assert resolver.resolve(issuer=POLICY.issuer, kid=key["kid"]) is None
    assert resolver.resolve(issuer=POLICY.issuer, kid=new_key["kid"]) is not None
    clock.value += POLICY.max_cache_seconds + 1
    assert resolver.resolve(issuer=POLICY.issuer, kid=new_key["kid"]) is None


@pytest.mark.parametrize(
    "change",
    [
        {"issuer": "https://login.microsoftonline.com/common/v2.0"},
        {"jwks_uri": "https://login.microsoftonline.com/common/discovery/v2.0/keys"},
        {"jwks_uri": "https://evil.example/keys"},
        {"jwks_uri": "http://login.microsoftonline.com/keys"},
        {"issuer": f"https://{TENANT}.ciamlogin.com/{TENANT}/v2.0"},
    ],
)
def test_untrusted_metadata_denied_before_jwks_fetch(prepared, change):
    """A JWT or OIDC discovery response cannot choose a new trust origin."""
    _, key, transport, _, resolver = prepared
    del key
    transport.metadata = raw_json({**metadata(), **change})
    with pytest.raises(PermissionError, match="ID3M workforce signing-key trust denied"):
        resolver.refresh()
    assert transport.calls == [(POLICY.metadata_path, 65536)]


@pytest.mark.parametrize(
    "broken",
    [
        b"",
        b"null",
        b'{"issuer":"a","issuer":"b"}',
        b'{"issuer":NaN}',
        b"\xff",
        b"x" * 65537,
    ],
)
def test_bad_discovery_json_denies_and_does_not_fetch_keys(prepared, broken):
    """Invalid UTF-8, ambiguous JSON and large data cannot become trust."""
    _, _, transport, _, resolver = prepared
    transport.metadata = broken
    with pytest.raises(PermissionError):
        resolver.refresh()
    assert len(transport.calls) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"e": "AQAC"},
        {"n": "AQAB"},
        {"use": "enc"},
        {"alg": "HS256"},
        {"key_ops": ["sign"]},
        {"issuer": "https://login.microsoftonline.com/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb/v2.0"},
    ],
)
def test_unsupported_key_material_does_not_enter_cache(prepared, change):
    """Weak RSA, wrong operation and foreign tenant signers must be denied."""
    _, key, transport, _, resolver = prepared
    transport.jwks = raw_json({"keys": [{**key, **change}]})
    with pytest.raises(PermissionError):
        resolver.refresh()
    assert resolver.resolve(issuer=POLICY.issuer, kid=key["kid"]) is None


def test_duplicate_jwks_kids_and_json_properties_fail_closed(prepared):
    """No parser or key-set order may decide which duplicate signing key wins."""
    _, key, transport, _, resolver = prepared
    transport.jwks = raw_json({"keys": [key, key]})
    with pytest.raises(PermissionError):
        resolver.refresh()
    transport.jwks = b'{"keys":[],"keys":[]}'
    with pytest.raises(PermissionError):
        resolver.refresh()


def test_transport_outage_revokes_previously_cached_keys(prepared):
    """Failed refresh cannot silently keep previously accepted public keys."""
    _, key, transport, _, resolver = prepared
    resolver.refresh()
    transport.error = OSError("connection unavailable")
    with pytest.raises(PermissionError):
        resolver.refresh()
    assert resolver.resolve(issuer=POLICY.issuer, kid=key["kid"]) is None


@pytest.mark.parametrize("tenant", ["common", "organizations", "consumers", TENANT.upper(), "aaaa/../evil", ""])
def test_generic_or_malformed_tenant_policy_is_never_accepted(tenant):
    """The cache is permanently scoped to one concrete workforce tenant."""
    with pytest.raises(ValueError):
        WorkforceMetadataPolicy(tenant_id=tenant)


@pytest.mark.parametrize("seconds", [0, 1, 299, 3601, 100000, True])
def test_cache_ttl_is_strictly_bounded(seconds):
    """A false boolean or unbounded expiry must not enable stale auth."""
    with pytest.raises(ValueError):
        WorkforceMetadataPolicy(tenant_id=TENANT, max_cache_seconds=seconds)


def test_pinned_https_transport_rejects_urls_and_unpinned_paths_without_network(monkeypatch):
    """No caller-provided host, query, path or size may reach HTTPSConnection."""
    constructed = []

    def forbid(*args, **kwargs):
        """Fail if a forbidden request opens a socket."""
        constructed.append((args, kwargs))
        raise AssertionError("Network was attempted")

    monkeypatch.setattr("matchdesk.domain.id3m_workforce_keys.HTTPSConnection", forbid)
    transport = PinnedEntraHttpsTransport(POLICY)
    for path in ("https://evil.example/keys", "//evil.example/", POLICY.keys_path + "?x=1", POLICY.metadata_path + "/"):
        with pytest.raises(PermissionError):
            transport.get(path, 262144)
    with pytest.raises(PermissionError):
        transport.get(POLICY.keys_path, 65536)
    assert constructed == []


def test_bounded_direct_https_transport_never_follows_redirect(monkeypatch):
    """A Location header must deny, not open another connection."""
    opened = []

    class Response:
        """Simulate a redirect from the otherwise trusted authority."""

        status = 302

        def getheaders(self):
            """Expose a redirect which cannot be followed."""
            return [("Content-Type", "application/json"), ("Location", "https://evil.example")]

        def read(self, count):
            """No body parsing should occur for the redirect."""
            raise AssertionError(f"Unexpected read: {count}")

    class Connection:
        """Count only the fixed-host connection and close attempt."""

        def __init__(self, host, *, timeout, context):
            """Check outbound authority is always pinned."""
            opened.append((host, timeout, context is not None))

        def request(self, method, path, *, headers):
            """Allow only the exact HTTPS discovery GET."""
            assert (method, path) == ("GET", POLICY.metadata_path)
            assert headers["Accept-Encoding"] == "identity"

        def getresponse(self):
            """Return the prohibited redirect."""
            return Response()

        def close(self):
            """Model explicit TLS connection cleanup."""
            pass

    monkeypatch.setattr("matchdesk.domain.id3m_workforce_keys.HTTPSConnection", Connection)
    with pytest.raises(PermissionError):
        PinnedEntraHttpsTransport(POLICY).get(POLICY.metadata_path, 65536)
    assert len(opened) == 1
    assert opened[0][:2] == ("login.microsoftonline.com", 5.0)


def test_cache_rejects_untrusted_clock_and_does_not_extend_expired_keys(prepared):
    """Unreliable monotonic clock values fail closed instead of extending TTL."""
    _, key, transport, clock, resolver = prepared
    resolver.refresh()
    clock.value = float("nan")
    assert resolver.resolve(issuer=POLICY.issuer, kid=key["kid"]) is None
    with pytest.raises(PermissionError):
        resolver.refresh()
    assert len(transport.calls) == 4
