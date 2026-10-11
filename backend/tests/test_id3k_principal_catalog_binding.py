"""ID3K disposable dual-signature catalog binding regressions, not live Entra UAT."""

from contextlib import contextmanager
from datetime import datetime, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt import PyJWK
from matchdesk.domain.id3h_release_approval import ReleaseDenied
from matchdesk.domain.id3k_principal_catalog_binding import (
    DisposablePrincipalPolicy,
    inspect_disposable_principal_binding,
)
from matchdesk.domain.producer_identity import StaticTrustedKeys

TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
HUMAN = "11111111-1111-1111-1111-111111111111"
WORKLOAD = "22222222-2222-2222-2222-222222222222"
NOW = datetime.fromtimestamp(1800000100, timezone.utc)
ISSUER = f"https://login.microsoftonline.com/{TENANT}/v2.0"
ROW = ("matchdesk_id3j_ci", "matchdesk_id3j_reader_ci", "matchdesk_id3j_reader_ci", True) + (
    False,
) * 13


class Cursor:
    """Fixed synthetic catalog cursor for unit tests only."""

    def __init__(self, owner):
        """Retain mutable fixture state to simulate role drift."""
        self.owner = owner

    def __enter__(self):
        """Support standard cursor context management."""
        return self

    def __exit__(self, *_):
        """Release synthetic cursor without suppressing errors."""
        return False

    def execute(self, query):
        """Record read-only SQL; there is no SQL executor in this fixture."""
        self.owner.sql.append(query)

    def fetchone(self):
        """Return the current observed role grants."""
        return self.owner.row


class Connection:
    """Mock only SQL results; real PostgreSQL is tested by existing ID3J CI."""

    def __init__(self):
        """Start in strictly unprivileged CI posture."""
        self.row = ROW
        self.sql = []

    @contextmanager
    def transaction(self):
        """Provide a bounded synthetic read-only transaction."""
        yield

    def cursor(self):
        """Return the current fake catalog reader."""
        return Cursor(self)


class Entitlements:
    """Host-owned human inspection entitlement, unrelated to JWT roles."""

    def __init__(self):
        """Start with a single permitted synthetic operator."""
        self.allowed = True
        self.calls = 0
        self.revoke_after_first = False

    def may_inspect(self, *, tenant_id, human_oid, database):
        """Optionally revoke human access between catalog observations."""
        self.calls += 1
        if self.revoke_after_first and self.calls > 1:
            return False
        return self.allowed and (tenant_id, human_oid, database) == (
            TENANT,
            HUMAN,
            "matchdesk_id3j_ci",
        )


@pytest.fixture
def prepared():
    """Generate disposable RSA keys with a pinned issuer and signing ID."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    n = private.public_key().public_numbers()

    def b64(x):
        """Encode unsigned RSA limbs for a synthetic public JWK."""
        return jwt.utils.base64url_encode(x.to_bytes((x.bit_length() + 7) // 8, "big")).decode()

    jwk = PyJWK.from_dict(
        {
            "kty": "RSA",
            "alg": "RS256",
            "use": "sig",
            "kid": "ci-key",
            "n": b64(n.n),
            "e": b64(n.e),
        }
    )
    policy = DisposablePrincipalPolicy(
        tenant_id=TENANT,
        issuer=ISSUER,
        human_audience="api://id3k-human-ci",
        workload_audience="api://id3k-workload-ci",
        human_client_id="ci-human-client",
        workload_client_id="ci-workload-client",
        workload_oid=WORKLOAD,
    )
    return private, StaticTrustedKeys(ISSUER, {"ci-key": jwk}), policy


def make_tokens(private, policy, *, human_changes=None, workload_changes=None):
    """Sign distinct delegated and app-only CI scopes using fresh test keys."""
    common = dict(
        iss=ISSUER,
        tid=TENANT,
        iat=1800000000,
        nbf=1800000000,
        exp=1800000200,
        jti="ci-unique",
    )
    human = {
        **common,
        "aud": policy.human_audience,
        "sub": "ci-human",
        "oid": HUMAN,
        "azp": policy.human_client_id,
        "idtyp": "user",
        "scp": "MatchDesk.Catalog.Inspect",
        "amr": ["pwd", "mfa"],
    }
    workload = {
        **common,
        "aud": policy.workload_audience,
        "sub": "ci-workload",
        "oid": WORKLOAD,
        "azp": policy.workload_client_id,
        "idtyp": "app",
        "roles": ["MatchDesk.Catalog.ReadOnly"],
    }
    human.update(human_changes or {})
    workload.update(workload_changes or {})
    return (
        jwt.encode(human, private, algorithm="RS256", headers={"kid": "ci-key"}),
        jwt.encode(workload, private, algorithm="RS256", headers={"kid": "ci-key"}),
    )


def inspect(prepared, *, human_changes=None, workload_changes=None, grants=None, db=None):
    """Invoke the fail-closed non-executing boundary with independent fixtures."""
    private, keys, policy = prepared
    human, workload = make_tokens(
        private, policy, human_changes=human_changes, workload_changes=workload_changes
    )
    return inspect_disposable_principal_binding(
        db or Connection(),
        human_token=human,
        workload_token=workload,
        policy=policy,
        keys=keys,
        entitlements=grants or Entitlements(),
        clock=lambda: NOW,
    )


def test_valid_separate_signatures_and_catalog_deny_execution(prepared):
    """Two verified principals and real-scoped flags never grant mutations."""
    db = Connection()
    receipt = inspect(prepared, db=db)
    assert receipt.human_oid == HUMAN
    assert receipt.workload_oid == WORKLOAD
    assert receipt.execution_authorized is False
    assert receipt.database_writes_authorized is False
    assert db.sql.count("SET TRANSACTION READ ONLY") == 2


@pytest.mark.parametrize(
    "field,value",
    [
        ("aud", "api://id3k-workload-ci"),
        ("iss", "https://login.microsoftonline.com/common/v2.0"),
        ("tid", "ffffffff-ffff-ffff-ffff-ffffffffffff"),
        ("scp", "MatchDesk.Producer.Access"),
        ("amr", ["pwd"]),
        ("idtyp", "app"),
        ("exp", 1800000000),
        ("exp", 1800000900),
        ("iat", "1800000000"),
        ("oid", WORKLOAD),
        ("azp", "rogue-client"),
    ],
)
def test_wrong_human_claims_fail_closed(prepared, field, value):
    """Cross-realm, no MFA, expiry and wrong delegated scope must be denied."""
    with pytest.raises(ReleaseDenied):
        inspect(prepared, human_changes={field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("aud", "api://id3k-human-ci"),
        ("idtyp", "user"),
        ("azp", "rogue-app"),
        ("oid", HUMAN),
        ("roles", ["MatchDesk.Catalog.Admin"]),
        ("roles", ["MatchDesk.Catalog.ReadOnly", "Owner"]),
        ("scp", "MatchDesk.Catalog.Inspect"),
        ("exp", 1800000000),
    ],
)
def test_wrong_workload_claims_fail_closed(prepared, field, value):
    """An app-only workload cannot borrow human scopes or elevated roles."""
    with pytest.raises(ReleaseDenied):
        inspect(prepared, workload_changes={field: value})


def test_missing_or_revoked_server_entitlement_denied(prepared):
    """Signed actor claims are insufficient without current host-side grants."""
    grants = Entitlements()
    grants.allowed = False
    with pytest.raises(ReleaseDenied):
        inspect(prepared, grants=grants)
    grants.allowed = True
    grants.revoke_after_first = True
    with pytest.raises(ReleaseDenied):
        inspect(prepared, grants=grants)


def test_database_grant_drift_denied(prepared):
    """The bound catalog cannot gain CREATE while a read is revalidated."""
    db = Connection()
    db.row = ROW[:11] + (True,) + ROW[12:]
    with pytest.raises(ReleaseDenied):
        inspect(prepared, db=db)


def test_untrusted_signature_and_unavailable_key_denied(prepared):
    """Tokens must validate using the exact pinned signing key, not a claim."""
    private, _, policy = prepared
    human, workload = make_tokens(private, policy)
    rogue = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rogue_token = jwt.encode(
        jwt.decode(human, options={"verify_signature": False}),
        rogue,
        algorithm="RS256",
        headers={"kid": "ci-key"},
    )
    _, keys, _ = prepared
    with pytest.raises(ReleaseDenied):
        inspect_disposable_principal_binding(
            Connection(),
            human_token=rogue_token,
            workload_token=workload,
            policy=policy,
            keys=keys,
            entitlements=Entitlements(),
            clock=lambda: NOW,
        )


def test_identity_policy_denies_confused_audiences(prepared):
    """Do not allow the same API audience to represent both actor types."""
    _, _, policy = prepared
    with pytest.raises(ValueError):
        DisposablePrincipalPolicy(
            tenant_id=policy.tenant_id,
            issuer=policy.issuer,
            human_audience="same",
            workload_audience="same",
            human_client_id="human",
            workload_client_id="app",
            workload_oid=WORKLOAD,
        )
