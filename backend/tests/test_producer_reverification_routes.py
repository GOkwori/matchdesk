"""Negative and positive offline checks for opt-in workforce reverification HTTP."""

from __future__ import annotations

from dataclasses import replace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from matchdesk.api.app import create_app
from matchdesk.api.producer_reverification_routes import (
    create_grant_backed_producer_reverification_router,
    create_producer_reverification_router,
)
from matchdesk.domain.producer_commands import HostVerifiedActor, open_producer_case
from matchdesk.domain.producer_execution_grants import ProducerGrantAttempt
from matchdesk.domain.producer_identity import ProducerIdentityPolicy
from matchdesk.domain.producer_preview import build_producer_desk_preview

TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
POLICY = ProducerIdentityPolicy(
    issuer=f"https://login.microsoftonline.com/{TENANT}/v2.0",
    tenant_id=TENANT,
    audience="api://matchdesk-ci",
    client_ids=frozenset({"client-1"}),
)
URL = "/api/workforce/producer/sessions/demo-preview-only/cases/demo-story-output/reverify"
HEADERS = {"Authorization": "Bearer offline-token", "Content-Type": "application/json"}


def actor() -> HostVerifiedActor:
    """Provide a simulated trusted identity, not live MFA evidence."""
    return HostVerifiedActor(
        subject="workforce-person",
        tenant_id=TENANT,
        issuer=POLICY.issuer,
        roles=frozenset({"producer"}),
        permitted_sessions=frozenset({"demo-preview-only"}),
    )


def sample():
    """Prepare an evidence-bound synthetic case requiring re-verification."""
    preview = build_producer_desk_preview()
    return open_producer_case(
        actor=actor(),
        tenant_id=TENANT,
        output=preview.output,
        claims=(preview.claim,),
        evidence=preview.evidence,
        accepted_events=preview.events,
    )


class Resolver:
    """Deny-all trust dependency when the real token verifier is not overridden."""

    def resolve(self, **kwargs):
        """Do not provide fake signing keys or entitlements by default."""
        del kwargs
        return None


class Store:
    """Offline CAS stand-in that preserves the full resulting audit state."""

    def __init__(self):
        """Create a fresh case and an observable mutation count."""
        self.case = sample()
        self.writes = 0
        self.reads = 0
        self.conflict = False

    def load(self, tenant_id, session_id, output_id):
        """Select only the permitted tenant, session and output."""
        self.reads += 1
        if (tenant_id, session_id, output_id) == (
            self.case.tenant_id,
            self.case.output.session_id,
            self.case.output.output_id,
        ):
            return self.case
        return None

    def replace_if_generation(self, case, *, expected_generation):
        """Reject replayed and stale changes without writing."""
        if self.conflict or self.case.generation != expected_generation:
            return False
        self.case = case
        self.writes += 1
        return True


class Grants:
    """Simulated secondary host-owned step-up decision, initially deny-all."""

    def __init__(self):
        """Default to no permission for a privileged decision."""
        self.allowed = False
        self.calls = 0

    def authorize(self, *, actor, session_id, output_id, binding, expected_generation):
        """Grant only a test-specific exact target when explicitly enabled."""
        self.calls += 1
        return (
            self.allowed
            and actor.subject == "workforce-person"
            and session_id == "demo-preview-only"
            and output_id == "demo-story-output"
            and binding.item_version == 1
            and expected_generation == 1
        )


def setup(monkeypatch):
    """Build one explicitly mounted router; verifier mocked only for route tests."""
    store, grants = Store(), Grants()
    router = create_producer_reverification_router(
        policy=POLICY,
        keys=Resolver(),
        entitlements=Resolver(),
        grants=grants,
        store=store,
    )
    client = TestClient(create_app(producer_reverification_router=router))
    import matchdesk.api.producer_reverification_routes as routes

    monkeypatch.setattr(routes, "verify_producer_access_token", lambda *args, **kwargs: actor())
    return client, store, grants


def body(store):
    """Bind a client request to every current version and evidence field."""
    return {
        "expected_generation": store.case.generation,
        "binding": store.case.output.binding.model_dump(mode="json"),
        "reason": "Evidence checked",
    }


def test_default_application_exposes_no_privileged_command():
    """An unconfigured application has no workforce mutation endpoint."""
    client = TestClient(create_app())
    assert client.post(URL, json={}, headers=HEADERS).status_code == 404
    assert (
        URL.replace("demo-preview-only", "{session_id}").replace("demo-story-output", "{output_id}")
        not in client.get("/openapi.json").json()["paths"]
    )


def test_valid_token_alone_cannot_write(monkeypatch):
    """A delegated JWT cannot replace independent host action authorization."""
    client, store, grants = setup(monkeypatch)
    assert client.post(URL, json=body(store), headers=HEADERS).status_code == 403
    assert store.writes == 0
    assert grants.calls == 1


@pytest.mark.parametrize(
    "untrusted",
    [
        replace(actor(), roles=frozenset({"auditor"})),
        replace(actor(), tenant_id="11111111-2222-3333-4444-555555555555"),
        replace(actor(), issuer="https://untrusted.invalid/v2.0"),
        replace(actor(), permitted_sessions=frozenset({"other-session"})),
        object(),
    ],
    ids=[
        "non-producer",
        "foreign-tenant",
        "foreign-issuer",
        "foreign-session",
        "wrong-type",
    ],
)
def test_reverification_rechecks_workforce_actor_before_case_lookup(monkeypatch, untrusted):
    """Reject defective verifier output before storage and action-grant lookup."""
    client, store, grants = setup(monkeypatch)
    grants.allowed = True
    import matchdesk.api.producer_reverification_routes as routes

    monkeypatch.setattr(routes, "verify_producer_access_token", lambda *_a, **_k: untrusted)
    response = client.post(URL, json=body(store), headers=HEADERS)
    assert response.status_code == 403
    assert response.headers["Cache-Control"] == "no-store"
    assert store.reads == 0 and store.writes == 0 and grants.calls == 0


def test_exact_grant_saves_once_and_replay_fails(monkeypatch):
    """A scoped host decision permits one atomic update, never repeated writes."""
    client, store, grants = setup(monkeypatch)
    grants.allowed = True
    request = body(store)
    good = client.post(URL, json=request, headers=HEADERS)
    assert good.status_code == 200
    assert good.json()["review_status"] == "ready_for_decision"
    assert good.json()["generation"] == 2
    assert good.json()["approval_enabled"] is False
    assert good.json()["publication_enabled"] is False
    assert good.headers["Cache-Control"] == "no-store"
    assert store.writes == 1
    assert client.post(URL, json=request, headers=HEADERS).status_code == 409
    assert store.writes == 1
    assert len(store.case.review.audit) == 2
    for command in ("approve", "reject", "publish", "edit"):
        assert client.post(URL.rsplit("/", 1)[0] + "/" + command, json={}).status_code == 404


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Content-Type": "application/json"},
        {**HEADERS, "Cookie": "session=forged"},
        {**HEADERS, "Origin": "https://untrusted.example"},
        {**HEADERS, "Referer": "https://untrusted.example"},
        {**HEADERS, "X-Forwarded-For": "127.0.0.1"},
        {**HEADERS, "Authorization": "Basic unsupported"},
    ],
)
def test_invalid_transport_never_touches_storage(monkeypatch, headers):
    """Bad framing, browser-originated and spoofed requests fail before lookups."""
    client, store, grants = setup(monkeypatch)
    assert client.post(URL, json=body(store), headers=headers).status_code == 401
    assert store.reads == 0
    assert store.writes == 0
    assert grants.calls == 0


def test_missing_content_type_rejects_untyped_raw_body(monkeypatch):
    """An explicitly untyped raw JSON body is denied before storage access."""
    client, store, grants = setup(monkeypatch)
    response = client.post(
        URL,
        content=b"{}",
        headers={"Authorization": "Bearer offline-token"},
    )
    assert response.status_code == 401
    assert store.reads == 0
    assert store.writes == 0
    assert grants.calls == 0


def test_invalid_binding_or_generation_is_a_conflict(monkeypatch):
    """Changing content binding or generation prevents step-up and CAS."""
    client, store, grants = setup(monkeypatch)
    request = body(store)
    request["binding"]["item_version"] = 2
    assert client.post(URL, json=request, headers=HEADERS).status_code == 409
    request = body(store)
    request["expected_generation"] = 10
    assert client.post(URL, json=request, headers=HEADERS).status_code == 409
    assert grants.calls == 0 and store.writes == 0


def test_unknown_fields_and_ambiguous_json_fail_closed(monkeypatch):
    """No body-supplied role, tenant, actor or duplicate key can grant authority."""
    client, store, grants = setup(monkeypatch)
    request = body(store)
    request["roles"] = ["producer"]
    assert client.post(URL, json=request, headers=HEADERS).status_code == 400
    duplicate = '{"expected_generation":1,"expected_generation":1,"binding":{},"reason":"x"}'
    assert client.post(URL, content=duplicate, headers=HEADERS).status_code == 400
    assert grants.calls == 0 and store.writes == 0


def test_concurrent_race_does_not_record_success(monkeypatch):
    """Compare-and-swap rejection cannot be represented as a successful action."""
    client, store, grants = setup(monkeypatch)
    grants.allowed = True
    store.conflict = True
    assert client.post(URL, json=body(store), headers=HEADERS).status_code == 409
    assert store.writes == 0


def test_integrity_corruption_blocks_command(monkeypatch):
    """A corrupt persisted generation cannot be used for a producer command."""
    client, store, grants = setup(monkeypatch)
    grants.allowed = True
    request = body(store)
    store.case = replace(store.case, generation=3)
    assert client.post(URL, json=request, headers=HEADERS).status_code == 503
    assert store.writes == 0


class GrantBackedStore(Store):
    """A fake atomic CAS store that rejects every legacy non-grant mutation."""

    def __init__(self):
        """Track whether an exact typed grant reaches the intended storage path."""
        super().__init__()
        self.atomic_calls = 0
        self.revoked = False

    def replace_if_generation(self, case, *, expected_generation):
        """Fail loudly on any downgrade from transaction-backed reverification."""
        raise AssertionError("Legacy unguarded CAS must not be called")

    def replace_with_execution_grant(self, case, *, expected_generation, grant):
        """Simulate a grant-checked CAS without claiming to be real PostgreSQL."""
        if type(grant) is not ProducerGrantAttempt or grant.action != "reverify":
            raise AssertionError("Expected the exact host-selected reverify grant")
        self.atomic_calls += 1
        if self.revoked:
            return False
        return Store.replace_if_generation(self, case, expected_generation=expected_generation)


class GrantSelector:
    """A synthetic host-held grant selector, initially deny-all."""

    def __init__(self):
        """Do not issue a grant until a test explicitly enables selection."""
        self.enabled = False
        self.calls = 0
        self.override = None
        self.failure: Exception | None = None

    def select(self, *, actor, action, session_id, output_id, binding, expected_generation):
        """Select only server-created test grants, never a request-supplied UUID."""
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        if not self.enabled:
            return None
        selected = ProducerGrantAttempt(
            grant_id=UUID("11111111-2222-4333-8444-555555555555"),
            actor=actor,
            action=action,
            session_id=session_id,
            output_id=output_id,
            binding=binding,
            expected_generation=expected_generation,
        )
        return self.override(selected) if self.override is not None else selected


def setup_grant_backed(monkeypatch):
    """Mount only the opt-in atomic factory with a synthetic verifier."""
    store, grants = GrantBackedStore(), GrantSelector()
    router = create_grant_backed_producer_reverification_router(
        policy=POLICY,
        keys=Resolver(),
        entitlements=Resolver(),
        grants=grants,
        store=store,
    )
    client = TestClient(create_app(producer_reverification_router=router))
    import matchdesk.api.producer_reverification_routes as routes

    monkeypatch.setattr(routes, "verify_producer_access_token", lambda *_a, **_k: actor())
    return client, store, grants


def test_grant_backed_factory_requires_atomic_case_writer():
    """A legacy store cannot be misconfigured as the transactional route."""
    with pytest.raises(ValueError, match="trusted host-owned dependencies"):
        create_grant_backed_producer_reverification_router(
            policy=POLICY,
            keys=Resolver(),
            entitlements=Resolver(),
            grants=GrantSelector(),
            store=Store(),
        )


def test_grant_backed_reverification_denies_without_host_grant(monkeypatch):
    """A delegated token alone must not reach the case mutation boundary."""
    client, store, grants = setup_grant_backed(monkeypatch)
    denied = client.post(URL, headers=HEADERS, json=body(store))
    assert denied.status_code == 403
    assert denied.headers["Cache-Control"] == "no-store"
    assert grants.calls == 1
    assert store.atomic_calls == 0 and store.writes == 0
    assert len(store.case.review.audit) == 1


def test_grant_backed_reverify_calls_only_atomic_method(monkeypatch):
    """One exact grant-backed reverification leaves approval and publication off."""
    client, store, grants = setup_grant_backed(monkeypatch)
    grants.enabled = True
    request = body(store)
    accepted = client.post(URL, headers=HEADERS, json=request)
    assert accepted.status_code == 200
    assert accepted.json()["generation"] == 2
    assert accepted.json()["review_status"] == "ready_for_decision"
    assert accepted.json()["mode"] == "grant_backed_development_only"
    assert accepted.json()["approval_enabled"] is False
    assert accepted.json()["publication_enabled"] is False
    assert store.atomic_calls == 1 and store.writes == 1
    assert grants.calls == 1
    assert client.post(URL, headers=HEADERS, json=request).status_code == 409
    assert store.atomic_calls == 1 and len(store.case.review.audit) == 2


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "boolean",
        "foreign-subject",
        "foreign-tenant",
        "foreign-issuer",
        "wrong-action",
        "wrong-generation",
        "wrong-output",
        "wrong-binding",
    ],
)
def test_grant_backed_selector_must_match_verified_actor_and_binding(monkeypatch, fault):
    """Never infer authority from a wrong type, actor, action, target or version."""
    client, store, grants = setup_grant_backed(monkeypatch)
    grants.enabled = True
    if fault == "missing":
        grants.override = lambda _grant: None
    elif fault == "boolean":
        grants.override = lambda _grant: True
    elif fault == "foreign-subject":
        grants.override = lambda grant: replace(
            grant, actor=replace(grant.actor, subject="foreign-person")
        )
    elif fault == "foreign-tenant":
        grants.override = lambda grant: replace(
            grant, actor=replace(grant.actor, tenant_id="other-tenant")
        )
    elif fault == "foreign-issuer":
        grants.override = lambda grant: replace(
            grant, actor=replace(grant.actor, issuer="https://foreign.invalid/v2.0")
        )
    elif fault == "wrong-action":
        grants.override = lambda grant: replace(grant, action="approve")
    elif fault == "wrong-generation":
        grants.override = lambda grant: replace(grant, expected_generation=2)
    elif fault == "wrong-output":
        grants.override = lambda grant: replace(grant, output_id="other-output")
    else:
        grants.override = lambda grant: replace(
            grant,
            binding=grant.binding.model_copy(update={"item_version": 999}),
        )
    denied = client.post(URL, headers=HEADERS, json=body(store))
    assert denied.status_code == 403
    assert store.atomic_calls == 0 and store.writes == 0


def test_grant_backed_cannot_take_client_grant_uuid_or_role(monkeypatch):
    """Request JSON cannot inject a grant handle or a spoofed MFA role."""
    client, store, grants = setup_grant_backed(monkeypatch)
    grants.enabled = True
    forged = body(store)
    forged["grant_id"] = "11111111-2222-4333-8444-555555555555"
    assert client.post(URL, headers=HEADERS, json=forged).status_code == 400
    forged = body(store)
    forged["mfa_completed"] = True
    assert client.post(URL, headers=HEADERS, json=forged).status_code == 400
    assert grants.calls == 0 and store.atomic_calls == 0


def test_grant_backed_revocation_during_save_stays_denied(monkeypatch):
    """Simulated database refusal must not produce a successful HTTP receipt."""
    client, store, grants = setup_grant_backed(monkeypatch)
    grants.enabled = True
    store.revoked = True
    response = client.post(URL, headers=HEADERS, json=body(store))
    assert response.status_code == 409
    assert response.headers["Cache-Control"] == "no-store"
    assert store.atomic_calls == 1 and store.writes == 0
    assert len(store.case.review.audit) == 1


def test_grant_backed_selector_outage_fails_closed_without_details(monkeypatch):
    """An internal issuer fault cannot downgrade to a separate boolean grant."""
    client, store, grants = setup_grant_backed(monkeypatch)
    grants.failure = OSError("private issuer details")
    response = client.post(URL, headers=HEADERS, json=body(store))
    assert response.status_code == 503
    assert "private issuer details" not in response.text
    assert store.atomic_calls == 0 and store.writes == 0
