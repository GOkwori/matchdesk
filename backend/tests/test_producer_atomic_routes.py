"""HTTP regressions for the unmounted, atomic-only producer route.

All signed actor/SQL integration is qualified independently on actual CI
PostgreSQL. These tests only verify transport, case provenance and the lack
of fallback to legacy Boolean or UUID grant paths.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.testclient import TestClient
from matchdesk.api.app import create_app
from matchdesk.api.producer_atomic_routes import create_atomic_producer_router
from matchdesk.domain.producer_atomic_grant_bridge import ProducerAtomicGrantBridge
from matchdesk.domain.producer_commands import (
    HostVerifiedActor,
    open_producer_case,
)
from matchdesk.domain.producer_preview import build_producer_desk_preview

TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
BASE = "/api/workforce/producer/sessions/demo-preview-only/cases/demo-story-output"
HEADERS = {"Authorization": "Bearer synthetic", "Content-Type": "application/json"}


def fixture(monkeypatch):
    """Create an explicitly injected router with a test-only atomic receipt."""
    actor = HostVerifiedActor(
        subject="ci-operator",
        tenant_id=TENANT,
        issuer="https://login.microsoftonline.com/" + TENANT + "/v2.0",
        roles=frozenset({"producer"}),
        permitted_sessions=frozenset({"demo-preview-only"}),
    )
    preview = build_producer_desk_preview()
    first = open_producer_case(
        actor=actor,
        tenant_id=TENANT,
        output=preview.output,
        claims=(preview.claim,),
        evidence=preview.evidence,
        accepted_events=preview.events,
    )

    class Source:
        """Trusted initial case source rather than request-controlled JSON."""

        def resolve(self, *, actor, session_id, output_id):
            """Return the only actor- and session-bound initial case."""
            if (
                actor.subject == "ci-operator"
                and session_id == first.output.session_id
                and output_id == first.output.output_id
            ):
                return first
            return None

    class Reader:
        """Read-only fixture: absolutely no save or DML methods."""

        def __init__(self):
            """Start with no persisted producer case."""
            self.case = None

        def load(self, tenant_id, session_id, output_id):
            """Read only an exact scoped case after successful prior commit."""
            if self.case is not None and (tenant_id, session_id, output_id) == (
                self.case.tenant_id,
                self.case.output.session_id,
                self.case.output.output_id,
            ):
                return self.case
            return None

    reader = Reader()
    bridge = object.__new__(ProducerAtomicGrantBridge)
    writes = []
    auths = []

    def authenticate(self, *, access_token, session_id):
        """Return a fixed actor for transport-only tests."""
        auths.append((access_token, session_id))
        if access_token != "synthetic":
            raise PermissionError("untrusted")
        return actor

    def execute(self, *, access_token, case, action, expected_generation):
        """Record the only mutation route; no legacy save operations exist."""
        writes.append((action, expected_generation, case))
        if reader.case is not None and reader.case.generation != expected_generation:
            return False
        if reader.case is None and expected_generation != 0:
            return False
        reader.case = case
        return True

    monkeypatch.setattr(ProducerAtomicGrantBridge, "authenticate", authenticate)
    monkeypatch.setattr(ProducerAtomicGrantBridge, "execute", execute)
    route = create_atomic_producer_router(bridge=bridge, source=Source(), reader=reader)
    client = TestClient(create_app(producer_atomic_router=route))
    return client, first, reader, writes, auths


def test_default_app_has_no_producer_mutation_endpoint():
    """No trusted host injection means no producer write HTTP endpoints."""
    app = TestClient(create_app())
    assert app.post(BASE + "/create", headers=HEADERS, json={}).status_code == 404


def test_atomic_factory_denies_mutating_or_legacy_reader(monkeypatch):
    """A case store exposing direct DML cannot be the atomic HTTP reader."""
    client, first, reader, writes, _ = fixture(monkeypatch)
    del client, writes

    class MutatingReader:
        """Simulated legacy case store must fail factory validation."""

        def load(self, *_args):
            """Return a stored case but expose a direct write method."""
            return first

        def replace_if_generation(self, *_args, **_kwargs):
            """Never allow the legacy writer into the atomic HTTP factory."""
            return True

    bridge = object.__new__(ProducerAtomicGrantBridge)

    class Source:
        """A source that exposes the required read contract."""

        def resolve(self, **_kwargs):
            """Return only initial source evidence."""
            return first

    try:
        create_atomic_producer_router(bridge=bridge, source=Source(), reader=MutatingReader())
    except ValueError:
        pass
    else:
        raise AssertionError("Legacy case mutation was accepted as atomic reader")
    assert reader.case is None


def test_app_denies_mixed_mutation_router_mounts(monkeypatch):
    """A host cannot combine old Boolean/UUID endpoints with the atomic path."""
    client, *_ = fixture(monkeypatch)
    del client
    for legacy in ("producer_command_router", "producer_reverification_router"):
        try:
            create_app(producer_atomic_router=APIRouter(), **{legacy: APIRouter()})
        except ValueError:
            pass
        else:
            raise AssertionError("Legacy producer router was allowed beside atomic router")


def test_atomic_create_then_reverify_has_no_publish_or_legacy_fallback(monkeypatch):
    """Only the host-held signed bridge receives a case, never the browser."""
    client, first, reader, writes, auths = fixture(monkeypatch)
    create = client.post(
        BASE + "/create",
        headers=HEADERS,
        json={"binding": first.output.binding.model_dump(mode="json")},
    )
    assert create.status_code == 201
    assert create.json()["mode"] == "signed_atomic_dev_only"
    assert create.json()["publication_enabled"] is False
    assert len(writes) == 1 and writes[0][:2] == ("create", 0)
    assert reader.case == first

    request = {
        "binding": first.output.binding.model_dump(mode="json"),
        "expected_generation": 1,
        "reason": "CI evidence checked",
    }
    reverify = client.post(BASE + "/reverify", headers=HEADERS, json=request)
    assert reverify.status_code == 200
    assert reverify.json()["review_status"] == "ready_for_decision"
    assert reverify.json()["publication_enabled"] is False
    assert len(writes) == 2 and writes[-1][:2] == ("reverify", 1)
    assert auths == [("synthetic", "demo-preview-only")] * 2
    assert client.post(BASE + "/reverify", headers=HEADERS, json=request).status_code == 409
    assert len(writes) == 2


def test_atomic_http_rejects_client_authority_fields_before_bridge(monkeypatch):
    """No HTTP-provided issuer grant, approval flag or forged role is trusted."""
    client, first, _, writes, _ = fixture(monkeypatch)
    original = {"binding": first.output.binding.model_dump(mode="json")}
    for injected in (
        {"grant_id": "client-grant"},
        {"mfa_completed": True},
        {"roles": ["producer"]},
        {"approved": True},
        {"tenant_id": "other-tenant"},
    ):
        response = client.post(BASE + "/create", headers=HEADERS, json=original | injected)
        assert response.status_code == 400
    assert not writes


def test_atomic_http_invalid_bearer_is_denied_before_source(monkeypatch):
    """No identity means no confirmation lookup, grant or source read."""
    client, first, reader, writes, auths = fixture(monkeypatch)
    result = client.post(
        BASE + "/create",
        headers={"Authorization": "Bearer forged", "Content-Type": "application/json"},
        json={"binding": first.output.binding.model_dump(mode="json")},
    )
    assert result.status_code == 403
    assert not writes and reader.case is None
    assert auths == [("forged", "demo-preview-only")]


def test_atomic_http_rejects_ambiguous_grant_outcome(monkeypatch):
    """Do not retry a failed grant commit or mark approval as successful."""
    client, first, reader, writes, _ = fixture(monkeypatch)

    def failed(self, **_kwargs):
        """Simulate an unreconciled PostgreSQL acknowledgement."""
        raise RuntimeError("private database details")

    monkeypatch.setattr(ProducerAtomicGrantBridge, "execute", failed)
    result = client.post(
        BASE + "/create",
        headers=HEADERS,
        json={"binding": first.output.binding.model_dump(mode="json")},
    )
    assert result.status_code == 503
    assert "private database" not in result.text
    assert not writes and reader.case is None

def test_atomic_http_rejects_nonproducer_and_other_session(monkeypatch):
    """Bridge mistakes cannot grant role or session permissions at HTTP."""
    from dataclasses import replace

    client, first, reader, writes, _ = fixture(monkeypatch)
    original = {"binding": first.output.binding.model_dump(mode="json")}
    actor = HostVerifiedActor(
        subject="ci-operator",
        tenant_id=TENANT,
        issuer="https://login.microsoftonline.com/" + TENANT + "/v2.0",
        roles=frozenset({"auditor"}),
        permitted_sessions=frozenset({"demo-preview-only"}),
    )

    def invalid_actor(self, *, access_token, session_id):
        """Simulate an incorrectly trusted host adapter returning auditor."""
        del self, access_token, session_id
        return actor

    monkeypatch.setattr(ProducerAtomicGrantBridge, "authenticate", invalid_actor)
    result = client.post(BASE + "/create", headers=HEADERS, json=original)
    assert result.status_code == 403
    assert not writes and reader.case is None

    def wrong_session(self, *, access_token, session_id):
        """Simulate a producer actor without the requested session grant."""
        del self, access_token, session_id
        return replace(
            actor, roles=frozenset({"producer"}), permitted_sessions=frozenset({"other-session"})
        )

    monkeypatch.setattr(ProducerAtomicGrantBridge, "authenticate", wrong_session)
    result = client.post(BASE + "/create", headers=HEADERS, json=original)
    assert result.status_code == 403
    assert not writes and reader.case is None


def test_atomic_http_conceals_cross_tenant_source(monkeypatch):
    """Wrong-tenant source must deny rather than disclose case/version details."""
    from dataclasses import replace

    client, first, reader, writes, _ = fixture(monkeypatch)

    class ForeignSource:
        """Return an out-of-tenant fixture despite a correct caller scope."""

        def resolve(self, *, actor, session_id, output_id):
            """Intentionally violate the trusted source contract."""
            del actor, session_id, output_id
            return replace(first, tenant_id="foreign-tenant")

    bridge = object.__new__(ProducerAtomicGrantBridge)
    route = create_atomic_producer_router(bridge=bridge, source=ForeignSource(), reader=reader)
    isolated = TestClient(create_app(producer_atomic_router=route))
    result = isolated.post(
        BASE + "/create",
        headers=HEADERS,
        json={"binding": first.output.binding.model_dump(mode="json")},
    )
    assert result.status_code == 403
    assert result.headers["Cache-Control"] == "no-store"
    assert not writes and reader.case is None


def test_atomic_http_revoked_grant_never_falls_back(monkeypatch):
    """A revoked decision is not transformed into legacy approval."""
    client, first, reader, writes, _ = fixture(monkeypatch)

    def revoked(self, **_kwargs):
        """Simulate a restricted SQL grant revocation at execution time."""
        raise PermissionError("revoked grant")

    monkeypatch.setattr(ProducerAtomicGrantBridge, "execute", revoked)
    result = client.post(
        BASE + "/create",
        headers=HEADERS,
        json={"binding": first.output.binding.model_dump(mode="json")},
    )
    assert result.status_code == 403
    assert "revoked grant" not in result.text
    assert not writes and reader.case is None


def test_atomic_http_failed_cas_does_not_report_approval(monkeypatch):
    """A competing version prevents a successful HTTP mutation receipt."""
    client, first, reader, writes, _ = fixture(monkeypatch)

    def conflict(self, **_kwargs):
        """Simulate one atomic database CAS losing its generation race."""
        return False

    monkeypatch.setattr(ProducerAtomicGrantBridge, "execute", conflict)
    result = client.post(
        BASE + "/create",
        headers=HEADERS,
        json={"binding": first.output.binding.model_dump(mode="json")},
    )
    assert result.status_code == 409
    assert result.json()["detail"] == "Producer command not committed; reload"
    assert result.headers["Cache-Control"] == "no-store"
    assert not writes and reader.case is None


def test_atomic_reverify_rejects_noncanonical_reason_before_grant(monkeypatch):
    """Whitespace-mutated human reasons cannot enter immutable audit."""
    client, first, reader, writes, _ = fixture(monkeypatch)
    created = client.post(
        BASE + "/create",
        headers=HEADERS,
        json={"binding": first.output.binding.model_dump(mode="json")},
    )
    assert created.status_code == 201 and len(writes) == 1
    for reason in (" ", " padded", "padded "):
        outcome = client.post(
            BASE + "/reverify",
            headers=HEADERS,
            json={
                "binding": first.output.binding.model_dump(mode="json"),
                "expected_generation": 1,
                "reason": reason,
            },
        )
        assert outcome.status_code == 400
    assert reader.case == first
    assert len(writes) == 1
