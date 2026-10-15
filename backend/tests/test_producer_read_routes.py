"""Opt-in producer inspection: deny-by-default and no mutation regressions."""

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from matchdesk.api.app import create_app
from matchdesk.api.producer_read_routes import create_producer_read_router
from matchdesk.domain.producer_commands import (
    HostVerifiedActor,
    inspect_producer_case,
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
URL = "/api/workforce/producer/sessions/demo-preview-only/cases/demo-story-output"


class Reader:
    """Memory-only fixture: the HTTP route may call load but never write."""

    def __init__(self, case):
        """Retain one exact record and a read counter."""
        self.case = case
        self.reads = 0

    def load(self, tenant_id, session_id, output_id):
        """Load only when all three identity-bound keys match."""
        self.reads += 1
        if (tenant_id, session_id, output_id) == (
            self.case.tenant_id,
            self.case.output.session_id,
            self.case.output.output_id,
        ):
            return self.case
        return None


def actor(
    *, tenant=TENANT, sessions=frozenset({"demo-preview-only"}), roles=frozenset({"producer"})
):
    """Build a simulated trusted actor; HTTP tests mock only verification."""
    return HostVerifiedActor(
        subject="verified-workforce-actor",
        tenant_id=tenant,
        issuer=POLICY.issuer,
        roles=roles,
        permitted_sessions=sessions,
    )


def case():
    """Build one integrity-bound synthetic domain review for read tests."""
    preview = build_producer_desk_preview()
    return open_producer_case(
        actor=actor(),
        tenant_id=TENANT,
        output=preview.output,
        claims=(preview.claim,),
        evidence=preview.evidence,
        accepted_events=preview.events,
    )


def test_default_application_exposes_no_producer_read_or_write_routes():
    """An application without injected trust must not expose inspection."""
    client = TestClient(create_app())
    assert client.get(URL).status_code == 404
    assert "/api/workforce/producer/sessions/{session_id}/cases/{output_id}" not in (
        client.get("/openapi.json").json()["paths"]
    )
    for command in ("approve", "reject", "publish", "edit"):
        assert client.post(URL + "/" + command, json={}).status_code == 404


def test_read_only_domain_validates_scope_and_integrity():
    """No load on absent grants; corrupt stored records fail closed."""
    record = case()
    reader = Reader(record)
    assert inspect_producer_case(
        reader, actor=actor(), session_id="demo-preview-only", output_id="demo-story-output"
    ) == record
    for bad in (
        actor(tenant="foreign"),
        actor(sessions=frozenset({"foreign-session"})),
        actor(roles=frozenset({"auditor"})),
    ):
        with pytest.raises(PermissionError):
            inspect_producer_case(
                reader, actor=bad, session_id="demo-preview-only", output_id="demo-story-output"
            )
    assert reader.reads == 1
    reader.case = replace(record, generation=12)
    with pytest.raises(ValueError):
        inspect_producer_case(
            reader, actor=actor(), session_id="demo-preview-only", output_id="demo-story-output"
        )


def test_read_route_requires_explicit_dependencies_and_validated_bearer(monkeypatch):
    """Invalid claims and malformed requests never disclose producer cases."""
    reader = Reader(case())
    router = create_producer_read_router(
        policy=POLICY, keys=object_with_resolve(), entitlements=object_with_resolve(), reader=reader
    )
    client = TestClient(create_app(producer_read_router=router))
    assert client.get(URL).status_code == 401
    assert client.get(URL, headers={"Cookie": "session=forged"}).status_code == 401
    assert (
        client.get(URL + "?tenant=" + TENANT, headers={"Authorization": "Bearer demo"}).status_code
        == 401
    )
    assert client.get(URL, headers={"Authorization": "Bearer invalid"}).status_code == 403
    assert reader.reads == 0

    # Stub only the already-qualified token verifier so HTTP route contract,
    # data minimization, trust scopes and denial behavior can be checked.
    import matchdesk.api.producer_read_routes as routes

    monkeypatch.setattr(routes, "verify_producer_access_token", lambda *a, **k: actor())
    good = client.get(URL, headers={"Authorization": "Bearer test-only"})
    assert good.status_code == 200
    assert good.json() == {
        "output_id": "demo-story-output",
        "session_id": "demo-preview-only",
        "generation": 1,
        "review_status": "pending_verification",
        "item_version": 1,
        "mode": "authenticated_read_only",
        "publication_enabled": False,
    }
    assert good.headers["Cache-Control"] == "no-store"
    assert client.get(
        "/api/workforce/producer/sessions/foreign/cases/demo-story-output",
        headers={"Authorization": "Bearer test-only"},
    ).status_code == 403
    assert (
        client.post(URL, json={}, headers={"Authorization": "Bearer test-only"}).status_code
        == 405
    )
    # The forbidden session is denied before storage lookup, so only the
    # successful authorized inspection can ever reach this reader.
    assert reader.reads == 1


class Resolver:
    """Constructable dependency mock with no trustable keys or grants."""

    def resolve(self, **kwargs):
        """Return deny-all for key and entitlement lookups."""
        del kwargs
        return None


def object_with_resolve():
    """Return independent deny-all resolver instances for isolated HTTP tests."""
    return Resolver()
