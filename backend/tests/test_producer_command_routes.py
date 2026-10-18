"""Offline HTTP regression tests for opt-in, nonpublishing producer commands.

These tests deliberately replace workforce token verification with synthetic actors.
They cannot establish a real Entra MFA, operator approval or production readiness.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient
from matchdesk.api.app import create_app
from matchdesk.api.producer_command_routes import create_producer_command_router
from matchdesk.domain.broadcast_outputs import ClaimLinkedText, CommentaryPayload
from matchdesk.domain.hashing import content_digest
from matchdesk.domain.producer_commands import (
    HostVerifiedActor,
    apply_producer_command,
    open_producer_case,
)
from matchdesk.domain.producer_identity import ProducerIdentityPolicy
from matchdesk.domain.producer_preview import build_producer_desk_preview

TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
POLICY = ProducerIdentityPolicy(
    issuer=f"https://login.microsoftonline.com/{TENANT}/v2.0",
    tenant_id=TENANT,
    audience="api://matchdesk-ci",
    client_ids=frozenset({"client-1"}),
)
BASE = "/api/workforce/producer/sessions/demo-preview-only/cases/demo-story-output"
HEADERS = {"Authorization": "Bearer offline-token", "Content-Type": "application/json"}


def actor(*, tenant: str = TENANT, sessions: frozenset[str] | None = None) -> HostVerifiedActor:
    """Create synthetic trusted context; never take these roles from HTTP."""
    return HostVerifiedActor(
        subject="workforce-person",
        tenant_id=tenant,
        issuer=POLICY.issuer,
        roles=frozenset({"producer"}),
        permitted_sessions=sessions or frozenset({"demo-preview-only"}),
    )


def sample():
    """Use the actual deterministic source evidence and initial audit entry."""
    preview = build_producer_desk_preview()
    return open_producer_case(
        actor=actor(),
        tenant_id=TENANT,
        output=preview.output,
        claims=(preview.claim,),
        evidence=preview.evidence,
        accepted_events=preview.events,
    )


class DenyResolver:
    """No live identity keys or grants are provisioned in offline tests."""

    def resolve(self, **kwargs):
        """Return no external identity material."""
        del kwargs
        return None


class Source:
    """Supply only an immutable host-controlled synthetic producer case."""

    def __init__(self) -> None:
        """Initialize host-derived evidence and track source lookups."""
        self.case = sample()
        self.calls = 0
        self.failure: Exception | None = None

    def resolve(self, *, actor, session_id, output_id):
        """Check exact actor and resource binding before returning a source."""
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        if (
            actor.tenant_id != TENANT
            or session_id != self.case.output.session_id
            or output_id != self.case.output.output_id
        ):
            return None
        return self.case


class Store:
    """Model a single atomic case with no implicit grants or retries."""

    def __init__(self) -> None:
        """Initialize an isolated compare-and-swap test store."""
        self.case = None
        self.reads = 0
        self.writes = 0
        self.conflict = False
        self.failure: Exception | None = None

    def load(self, tenant_id, session_id, output_id):
        """Return a case only when all trusted scope keys match."""
        self.reads += 1
        if self.failure is not None:
            raise self.failure
        if self.case is not None and (
            tenant_id,
            session_id,
            output_id,
        ) == (
            self.case.tenant_id,
            self.case.output.session_id,
            self.case.output.output_id,
        ):
            return self.case
        return None

    def create(self, case) -> bool:
        """Reject duplicate initial inserts without changing the audit."""
        if self.failure is not None:
            raise self.failure
        if self.conflict or self.case is not None:
            return False
        self.case = case
        self.writes += 1
        return True

    def replace_if_generation(self, case, *, expected_generation: int) -> bool:
        """Reject races, keeping the existing generation and audit unchanged."""
        if self.failure is not None:
            raise self.failure
        if self.conflict or self.case is None or self.case.generation != expected_generation:
            return False
        self.case = case
        self.writes += 1
        return True


class Grants:
    """Deny all commands unless a synthetic host grants an exact action."""

    def __init__(self) -> None:
        """Initialize default-deny host grants and error injection."""
        self.actions: set[str] = set()
        self.calls = 0
        self.failure: Exception | None = None

    def authorize(
        self, *, actor, action, session_id, output_id, binding, expected_generation
    ) -> bool:
        """Compare server-known actor, resource and complete binding."""
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        return (
            action in self.actions
            and actor.subject == "workforce-person"
            and actor.tenant_id == TENANT
            and session_id == "demo-preview-only"
            and output_id == "demo-story-output"
            and binding.item_id == "demo-first-half-story"
            and expected_generation >= 0
        )


def prepare(monkeypatch):
    """Mount only the opted-in router, with no real workforce credentials."""
    source, store, grants = Source(), Store(), Grants()
    router = create_producer_command_router(
        policy=POLICY,
        keys=DenyResolver(),
        entitlements=DenyResolver(),
        grants=grants,
        source=source,
        store=store,
    )
    import matchdesk.api.producer_command_routes as routes

    monkeypatch.setattr(routes, "verify_producer_access_token", lambda *_a, **_k: actor())
    return TestClient(create_app(producer_command_router=router)), source, store, grants


def create_body(source) -> dict:
    """Bind creation to the source's exact output, not client-supplied data."""
    return {"binding": source.case.output.binding.model_dump(mode="json")}


def decision_body(store) -> dict:
    """Require the current generation and all evidence/content digests."""
    return {
        "binding": store.case.output.binding.model_dump(mode="json"),
        "expected_generation": store.case.generation,
        "reason": "Checked source evidence",
    }


def create_case(client, source, grants):
    """Create exactly once after a synthetic, action-scoped grant."""
    grants.actions.add("create")
    response = client.post(BASE + "/create", headers=HEADERS, json=create_body(source))
    assert response.status_code == 201
    assert response.json()["publication_enabled"] is False


def test_default_app_has_no_command_or_publication_routes():
    """Adding a module must not expose privileged operations by default."""
    client = TestClient(create_app())
    for action in ("create", "edit", "approve", "reject", "publish"):
        assert client.post(BASE + "/" + action, json={}, headers=HEADERS).status_code == 404


def test_token_alone_cannot_create_or_approve(monkeypatch):
    """Bearer possession is not a host decision or authorization to mutate."""
    client, source, store, grants = prepare(monkeypatch)
    assert (
        client.post(BASE + "/create", headers=HEADERS, json=create_body(source)).status_code == 403
    )
    assert store.writes == 0 and grants.calls == 1
    assert client.post(BASE + "/approve", headers=HEADERS, json={}).status_code == 400
    assert store.writes == 0


def test_exact_create_is_atomic_and_replay_is_denied(monkeypatch):
    """Only the first source-bound insert may produce an audit entry."""
    client, source, store, grants = prepare(monkeypatch)
    create_case(client, source, grants)
    assert store.case.generation == 1
    assert len(store.case.review.audit) == 1
    assert store.case.review.status == "pending_verification"
    assert (
        client.post(BASE + "/create", headers=HEADERS, json=create_body(source)).status_code == 409
    )
    assert store.writes == 1
    assert client.post(BASE + "/publish", headers=HEADERS, json={}).status_code == 404


@pytest.mark.parametrize(
    "headers",
    [
        {"Content-Type": "application/json"},
        {"Authorization": "Basic bad", "Content-Type": "application/json"},
        {**HEADERS, "Cookie": "session=forged"},
        {**HEADERS, "Origin": "https://attacker.example"},
        {**HEADERS, "X-Forwarded-For": "127.0.0.1"},
        {**HEADERS, "Referer": "https://attacker.example"},
        {**HEADERS, "Content-Type": "text/plain"},
    ],
)
def test_rejected_transport_never_reads_host_source(monkeypatch, headers):
    """Deny browser cookies, spoofed forwarding, missing bearer and untyped JSON."""
    client, source, store, grants = prepare(monkeypatch)
    response = client.post(BASE + "/create", json=create_body(source), headers=headers)
    assert response.status_code == 401
    assert source.calls == 0 and store.writes == 0 and grants.calls == 0


def test_cross_session_and_invalid_actor_denied(monkeypatch):
    """Token-verification output must still match the host-owned session scope."""
    client, source, store, grants = prepare(monkeypatch)
    import matchdesk.api.producer_command_routes as routes

    monkeypatch.setattr(
        routes,
        "verify_producer_access_token",
        lambda *_a, **_k: actor(sessions=frozenset({"another-session"})),
    )
    assert (
        client.post(BASE + "/create", headers=HEADERS, json=create_body(source)).status_code == 403
    )
    assert source.calls == 0 and store.writes == 0 and grants.calls == 0


def test_invalid_json_or_client_authority_cannot_create(monkeypatch):
    """Reject duplicate keys, unknown authority claims, malformed JSON and booleans."""
    client, source, store, grants = prepare(monkeypatch)
    grants.actions.add("create")
    body = create_body(source)
    for malformed in (
        {"binding": body["binding"], "role": "producer"},
        {"binding": {"item_version": True}},
    ):
        assert client.post(BASE + "/create", headers=HEADERS, json=malformed).status_code == 400
    duplicate = '{"binding":{},"binding":{}}'
    assert client.post(BASE + "/create", headers=HEADERS, content=duplicate).status_code == 400
    assert (
        client.post(BASE + "/create", headers=HEADERS, content='{"binding":NaN}').status_code == 400
    )
    assert store.writes == 0 and grants.calls == 0


def test_source_tampering_and_backend_faults_fail_closed(monkeypatch):
    """An inconsistent source or unavailable store cannot create a valid case."""
    client, source, store, grants = prepare(monkeypatch)
    grants.actions.add("create")
    source.case = replace(source.case, generation=2)
    assert (
        client.post(BASE + "/create", headers=HEADERS, json=create_body(source)).status_code == 409
    )
    assert store.writes == 0
    source.case = sample()
    store.failure = OSError("private store failure")
    response = client.post(BASE + "/create", headers=HEADERS, json=create_body(source))
    assert response.status_code == 503
    assert "private" not in response.text and store.writes == 0


def test_approval_requires_reverification_and_exact_generation(monkeypatch):
    """A host grant cannot bypass the review state machine or stale-version CAS."""
    client, source, store, grants = prepare(monkeypatch)
    create_case(client, source, grants)
    grants.actions.add("approve")
    pending = decision_body(store)
    assert client.post(BASE + "/approve", headers=HEADERS, json=pending).status_code == 409
    assert store.writes == 1
    store.case = apply_producer_command(
        store.case,
        actor=actor(),
        expected_generation=1,
        command="reverify",
        reason="Rechecked exact evidence",
    )
    approved = client.post(BASE + "/approve", headers=HEADERS, json=decision_body(store))
    assert approved.status_code == 200
    assert approved.json()["review_status"] == "approved"
    assert approved.json()["generation"] == 3
    assert approved.json()["publication_enabled"] is False
    assert approved.headers["Cache-Control"] == "no-store"
    assert len(store.case.review.audit) == 3
    assert client.post(BASE + "/approve", headers=HEADERS, json=pending).status_code == 409
    assert store.writes == 2


def test_exact_edit_revokes_previous_verification(monkeypatch):
    """Editing creates a new digest and returns the draft to pending review."""
    client, source, store, grants = prepare(monkeypatch)
    create_case(client, source, grants)
    grants.actions.add("edit")
    current = store.case.output
    payload = CommentaryPayload(
        lines=(
            ClaimLinkedText(
                claim_id=store.case.claims[0].claim_id, text="Revised synthetic narrative."
            ),
        )
    )
    new_binding = current.binding.model_copy(
        update={
            "item_version": current.binding.item_version + 1,
            "content_digest": content_digest(payload),
        }
    )
    revised = current.model_copy(update={"binding": new_binding, "payload": payload})
    request = decision_body(store)
    request["revised_output"] = revised.model_dump(mode="json")
    response = client.post(BASE + "/edit", json=request, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["review_status"] == "pending_verification"
    assert response.json()["item_version"] == current.binding.item_version + 1
    assert len(store.case.review.audit) == 2


def test_reject_and_concurrent_update_never_publish(monkeypatch):
    """Explicit review rejection cannot activate a broadcast or bypass races."""
    client, source, store, grants = prepare(monkeypatch)
    create_case(client, source, grants)
    grants.actions.add("reject")
    store.conflict = True
    response = client.post(BASE + "/reject", headers=HEADERS, json=decision_body(store))
    assert response.status_code == 409
    assert store.writes == 1 and len(store.case.review.audit) == 1
    store.conflict = False
    denied = client.post(BASE + "/reject", headers=HEADERS, json=decision_body(store))
    # Current review status may reject directly or require separate reverification.
    assert denied.status_code in (200, 409)
    assert denied.json().get("publication_enabled") is not True


def test_changed_binding_or_missing_generation_blocks_grants(monkeypatch):
    """A stale or tampered digest is rejected before secondary authorization."""
    client, source, store, grants = prepare(monkeypatch)
    create_case(client, source, grants)
    grants.actions.add("approve")
    request = decision_body(store)
    request["binding"]["content_digest"] = "b" * 64
    assert client.post(BASE + "/approve", headers=HEADERS, json=request).status_code == 409
    request = decision_body(store)
    request["expected_generation"] = True
    assert client.post(BASE + "/approve", headers=HEADERS, json=request).status_code == 400
    assert grants.calls == 1 and store.writes == 1


def test_body_limit_and_host_error_are_non_disclosing(monkeypatch):
    """Oversized requests and grant service failures do not change the audit."""
    client, source, store, grants = prepare(monkeypatch)
    large = b"x" * 65_537
    assert client.post(BASE + "/create", headers=HEADERS, content=large).status_code == 413
    grants.failure = RuntimeError("secret grant outage")
    assert (
        client.post(BASE + "/create", headers=HEADERS, json=create_body(source)).status_code == 503
    )
    assert store.writes == 0
