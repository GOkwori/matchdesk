"""Offline authorization and compare-and-swap checks for producer commands."""

from dataclasses import replace

import pytest
from matchdesk.domain.broadcast_outputs import ClaimLinkedText, CommentaryPayload
from matchdesk.domain.hashing import content_digest
from matchdesk.domain.producer_commands import (
    HostVerifiedActor,
    apply_producer_command,
    execute_producer_command,
    open_producer_case,
)
from matchdesk.domain.producer_preview import build_producer_desk_preview


def _actor(*, roles: frozenset[str] = frozenset({"producer"}), tenant: str = "team-1"):
    """Supply simulated host-verified context; never treat as live OIDC evidence."""
    return HostVerifiedActor(
        subject="actor-1",
        tenant_id=tenant,
        issuer="https://issuer.example",
        roles=roles,
        permitted_sessions=frozenset({"demo-preview-only"}),
    )


def _case():
    """Open the known source-verified synthetic preview for offline mutation tests."""
    preview = build_producer_desk_preview()
    return open_producer_case(
        actor=_actor(),
        tenant_id="team-1",
        output=preview.output,
        claims=(preview.claim,),
        evidence=preview.evidence,
        accepted_events=preview.events,
    )


def test_missing_scope_or_role_prevents_mutation() -> None:
    """An auditor cannot act as producer and tenants cannot impersonate each other."""
    case = _case()
    for actor in (_actor(roles=frozenset({"auditor"})), _actor(tenant="team-2")):
        with pytest.raises(PermissionError):
            apply_producer_command(
                case,
                actor=actor,
                expected_generation=1,
                command="reverify",
                reason="Checked",
            )


def test_producer_approval_requires_reverification_and_exact_generation() -> None:
    """Approval is separate from verification and stale snapshots are not accepted."""
    case = _case()
    with pytest.raises(ValueError, match="requires reverification"):
        apply_producer_command(
            case, actor=_actor(), expected_generation=1, command="approve", reason="Approved"
        )
    reviewed = apply_producer_command(
        case, actor=_actor(), expected_generation=1, command="reverify", reason="Checked"
    )
    approved = apply_producer_command(
        reviewed, actor=_actor(), expected_generation=2, command="approve", reason="Approved"
    )
    assert approved.review.status == "approved"
    assert approved.generation == 3
    with pytest.raises(RuntimeError, match="generation conflict"):
        apply_producer_command(
            approved, actor=_actor(), expected_generation=2, command="reject", reason="Stale"
        )


def test_edit_reopens_review_and_requires_fresh_decision() -> None:
    """Changing wording creates new digest and invalidates prior approval."""
    case = _case()
    case = apply_producer_command(
        case, actor=_actor(), expected_generation=1, command="reverify", reason="Checked"
    )
    case = apply_producer_command(
        case, actor=_actor(), expected_generation=2, command="approve", reason="Approved"
    )
    payload = CommentaryPayload(
        lines=(ClaimLinkedText(claim_id=case.claims[0].claim_id, text="First-half home goal."),)
    )
    new_binding = case.output.binding.model_copy(
        update={"item_version": 2, "content_digest": content_digest(payload)}
    )
    revised = case.output.model_copy(update={"binding": new_binding, "payload": payload})
    edited = apply_producer_command(
        case,
        actor=_actor(),
        expected_generation=3,
        command="edit",
        revised_output=revised,
        reason="Improve wording",
    )
    assert edited.review.status == "pending_verification"
    assert edited.generation == 4
    assert edited.review.binding.content_digest == content_digest(payload)


def test_reject_stale_hash_and_evidence_mismatch() -> None:
    """Tampered bindings do not get a valid producer transition."""
    case = _case()
    stale = replace(
        case,
        output=case.output.model_copy(
            update={"binding": case.output.binding.model_copy(update={"content_digest": "b" * 64})}
        ),
    )
    with pytest.raises(ValueError, match="stale or inconsistent"):
        apply_producer_command(
            stale, actor=_actor(), expected_generation=1, command="reverify", reason="Checked"
        )


class OfflineAtomicStore:
    """Deterministic fake of a durable optimistic-concurrency repository."""

    def __init__(self, case, *, race: bool = False) -> None:
        """Remember one case and optionally simulate an intervening concurrent update."""
        self.case = case
        self.race = race

    def load(self, tenant_id: str, session_id: str, output_id: str):
        """Return a case scoped to the trusted tenant/session arguments."""
        if (tenant_id, session_id, output_id) == (
            self.case.tenant_id,
            self.case.output.session_id,
            self.case.output.output_id,
        ):
            return self.case
        return None

    def replace_if_generation(self, case, *, expected_generation: int) -> bool:
        """Implement fake atomic-generation conflict detection."""
        if self.race or self.case.generation != expected_generation:
            return False
        self.case = case
        return True


def test_store_cas_blocks_concurrent_review() -> None:
    """A simulated database race prevents the review from being committed."""
    store = OfflineAtomicStore(_case(), race=True)
    with pytest.raises(RuntimeError, match="Concurrent"):
        execute_producer_command(
            store,
            actor=_actor(),
            tenant_id="team-1",
            session_id="demo-preview-only",
            output_id="demo-story-output",
            expected_generation=1,
            command="reverify",
            reason="Checked",
        )
    assert store.case.generation == 1


def test_no_command_endpoint_is_exposed() -> None:
    """Domain commands are not public without trusted identity and durable storage."""
    from fastapi.testclient import TestClient
    from matchdesk.api.app import create_app

    client = TestClient(create_app())
    assert (
        client.post("/api/producer/preview/reverify", json={"role": "producer"}).status_code == 404
    )
    assert (
        client.post("/api/producer/preview/approve", json={"role": "producer"}).status_code == 404
    )
    assert (
        client.post("/api/producer/preview/publish", json={"role": "producer"}).status_code == 404
    )
