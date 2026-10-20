"""Fail-closed unmounted bridge orchestration with no live identity or DB."""

from contextlib import contextmanager
from datetime import datetime, timezone

import matchdesk.domain.producer_atomic_grant_bridge as bridge_module
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from matchdesk.domain.postgres_producer_grant_writer import PostgresProducerGrantWriter
from matchdesk.domain.producer_atomic_grant_bridge import ProducerAtomicGrantBridge
from matchdesk.domain.producer_commands import HostVerifiedActor, open_producer_case
from matchdesk.domain.producer_grant_preflight import ProducerGrantPreflight
from matchdesk.domain.producer_identity import ProducerIdentityPolicy
from matchdesk.domain.producer_preview import build_producer_desk_preview

TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ISSUER = "https://login.microsoftonline.com/" + TENANT + "/v2.0"
STAGER = "matchdesk_test_stager"
ISSUER_ROLE = "matchdesk_test_issuer"


class FakeDb:
    """Simulate only fixed SQL function calls and authenticated role receipts."""

    def __init__(self, role, *, allowed=True, result=True):
        """Configure the simulated authenticated role and function outcome."""
        self.role = role
        self.allowed = allowed
        self.result = result
        self.queries = []
        self.closed = False
        self.rollbacks = 0

    def __call__(self):
        """Return this fixture as a fake connection."""
        return self

    @contextmanager
    def transaction(self):
        """Record rollback if any stage is rejected."""
        try:
            yield
        except Exception:
            self.rollbacks += 1
            raise

    @contextmanager
    def cursor(self):
        """Provide a context-managed fake cursor."""
        yield self

    def execute(self, sql, params):
        """Capture a fixed SQL invocation with its parameters."""
        self.queries.append((sql, params))

    def fetchone(self):
        """Return the exact role or strict Boolean fixture receipt."""
        statement = self.queries[-1][0]
        if "current_user::text" in statement:
            return self.role, self.role, self.allowed
        return (self.result,)

    def close(self):
        """Flag connection cleanup after the transaction."""
        self.closed = True


class Confirmation:
    """Host-held intent fixture, never extracted from HTTP fields."""

    def __init__(self, value="signed-fixture"):
        """Store one synthetic, host-owned signed confirmation."""
        self.value = value
        self.calls = 0

    def resolve_signed_confirmation(self, **_kwargs):
        """Return the host-only fixture, never a browser confirmation."""
        self.calls += 1
        return self.value


class Resolver:
    """Fake trust dependency; no real keys or grants are provisioned."""

    def resolve(self, **_kwargs):
        """Remain inert because verifier calls are patched in the tests."""
        return None


class Digest:
    """Provide deterministic test-only case digests."""

    def digest_case_jsonb(self, _case_json):
        """Return a stand-in for canonical PostgreSQL hashing."""
        return "a" * 64


def fixture(
    monkeypatch,
    *,
    confirmation="signed-fixture",
    stager=None,
    issuer=None,
    actor_subject="ci-producer",
    preflight_actor=None,
):
    """Build isolated host authorization and database fixtures."""
    actor = HostVerifiedActor(
        subject=actor_subject,
        tenant_id=TENANT,
        issuer=ISSUER,
        roles=frozenset({"producer"}),
        permitted_sessions=frozenset({"demo-preview-only"}),
    )
    preview = build_producer_desk_preview()
    case = open_producer_case(
        actor=actor,
        tenant_id=TENANT,
        output=preview.output,
        claims=(preview.claim,),
        evidence=preview.evidence,
        accepted_events=preview.events,
    )
    fake_preflight = ProducerGrantPreflight(
        confirmation_id="a" * 32,
        actor_id=preflight_actor or actor.subject,
        token_issuer=ISSUER,
        tenant_id=TENANT,
        session_id=case.output.session_id,
        output_id=case.output.output_id,
        action="create",
        expected_generation=0,
        authorized_case_sha256="a" * 64,
        authorized_audit_digest="b" * 64,
        confirmation_expires_at=int(datetime.now(timezone.utc).timestamp()) + 60,
    )
    monkeypatch.setattr(
        bridge_module, "verify_producer_access_token", lambda *_args, **_kwargs: actor
    )
    monkeypatch.setattr(
        bridge_module, "qualify_producer_grant_preflight", lambda **_kwargs: fake_preflight
    )
    stager = stager or FakeDb(STAGER)
    issuer = issuer or FakeDb(ISSUER_ROLE)
    confirmation_source = Confirmation(confirmation)
    writes = []
    writer = PostgresProducerGrantWriter(lambda: None, expected_role="matchdesk_writer_ci")
    monkeypatch.setattr(writer, "commit", lambda **kwargs: writes.append(kwargs) or True)
    policy = ProducerIdentityPolicy(
        tenant_id=TENANT,
        issuer=ISSUER,
        audience="api://matchdesk-ci",
        client_ids=frozenset({"client-ci"}),
        required_auth_context="c1",
        max_token_age_seconds=300,
    )
    handler = ProducerAtomicGrantBridge(
        policy=policy,
        keys=Resolver(),
        entitlements=Resolver(),
        confirmations=confirmation_source,
        confirmation_public_key=Ed25519PrivateKey.generate().public_key(),
        case_hash=Digest(),
        stager_connections=stager,
        issuer_connections=issuer,
        stager_role=STAGER,
        issuer_role=ISSUER_ROLE,
        writer=writer,
    )
    return handler, case, stager, issuer, writes, confirmation_source


def test_restricted_host_sequence_binds_exact_case_and_never_uses_direct_dml(monkeypatch):
    """One successful intent calls STAGE, ISSUE and atomic COMMIT in order."""
    handler, case, stager, issuer, writes, _ = fixture(monkeypatch)
    assert (
        handler.execute(
            access_token="signed-test-jwt", case=case, action="create", expected_generation=0
        )
        is True
    )
    assert len(writes) == 1
    assert writes[0]["action"] == "create" and writes[0]["expected_generation"] == 0
    assert len(writes[0]["grant_id"]) >= 16
    assert len(writes[0]["command_id"]) >= 16
    assert writes[0]["grant_id"] != writes[0]["command_id"]
    assert stager.closed and issuer.closed
    assert any(
        "SELECT public.matchdesk_stage_producer_confirmation" in sql for sql, _ in stager.queries
    )
    assert any(
        "SELECT public.matchdesk_issue_confirmed_producer_grant" in sql for sql, _ in issuer.queries
    )
    assert not any(
        "INSERT INTO" in sql or "UPDATE " in sql for db in (stager, issuer) for sql, _ in db.queries
    )


@pytest.mark.parametrize("value", ["", None])
def test_missing_server_confirmation_denies_before_database(monkeypatch, value):
    """Missing signed human intent stops before opening PostgreSQL."""
    handler, case, stager, issuer, writes, _ = fixture(monkeypatch, confirmation=value)
    with pytest.raises(PermissionError, match="Producer execution denied"):
        handler.execute(
            access_token="verified-test", case=case, action="create", expected_generation=0
        )
    assert not stager.queries and not issuer.queries and not writes


def test_signed_scope_mismatch_denies_before_database(monkeypatch):
    """Another actor cannot borrow a validly shaped signed intent."""
    handler, case, stager, issuer, writes, _ = fixture(
        monkeypatch, preflight_actor="forged-subject"
    )
    with pytest.raises(PermissionError):
        handler.execute(
            access_token="verified-test", case=case, action="create", expected_generation=0
        )
    assert not stager.queries and not issuer.queries and not writes


@pytest.mark.parametrize("phase", ["stage", "issue"])
def test_false_receipt_never_reaches_writer(monkeypatch, phase):
    """False stager/issuer receipts do not authorize the atomic writer."""
    stager = FakeDb(STAGER, result=phase != "stage")
    issuer = FakeDb(ISSUER_ROLE, result=phase != "issue")
    handler, case, _, _, writes, _ = fixture(monkeypatch, stager=stager, issuer=issuer)
    assert (
        handler.execute(
            access_token="verified-test", case=case, action="create", expected_generation=0
        )
        is False
    )
    assert not writes
    assert (len(issuer.queries) == 0) is (phase == "stage")


@pytest.mark.parametrize("where", ["stager", "issuer"])
def test_privileged_or_impersonated_role_denies_and_rolls_back(monkeypatch, where):
    """Role drift rejects the function call and rolls back."""
    stager = FakeDb(STAGER, allowed=where != "stager")
    issuer = FakeDb(ISSUER_ROLE, allowed=where != "issuer")
    handler, case, _, _, writes, _ = fixture(monkeypatch, stager=stager, issuer=issuer)
    with pytest.raises(PermissionError, match="Producer database authority denied"):
        handler.execute(
            access_token="verified-test", case=case, action="create", expected_generation=0
        )
    assert not writes
    assert (stager.rollbacks if where == "stager" else issuer.rollbacks) == 1


def test_unexpected_grant_receipt_is_unreconciled_not_approved(monkeypatch):
    """A truthy non-boolean receipt cannot mean grant authorization."""
    stager = FakeDb(STAGER, result=1)
    handler, case, _, _, writes, _ = fixture(monkeypatch, stager=stager)
    with pytest.raises(RuntimeError, match="unreconciled"):
        handler.execute(
            access_token="verified-test", case=case, action="create", expected_generation=0
        )
    assert not writes and stager.rollbacks == 1


def test_no_preflight_without_delegated_access_token(monkeypatch):
    """No access token means no verification or database invocation."""
    handler, case, stager, issuer, writes, confirmation = fixture(monkeypatch)
    with pytest.raises(PermissionError):
        handler.execute(access_token="", case=case, action="create", expected_generation=0)
    assert confirmation.calls == 0
    assert not stager.queries and not issuer.queries and not writes
