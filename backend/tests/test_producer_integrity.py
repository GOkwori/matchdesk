"""Security and recovery regressions for P3-05 producer commands.

All actors and repositories here are offline fakes. None of these tests establishes
live OIDC authentication, a production database, or authority to publish.
"""

from dataclasses import replace

import pytest
from matchdesk.domain import producer_commands
from matchdesk.domain.broadcast_outputs import (
    ClaimLinkedText,
    CommentaryPayload,
    ExplainerPayload,
)
from matchdesk.domain.hashing import content_digest
from matchdesk.domain.models import MatchWindow, VerificationResult
from matchdesk.domain.producer_commands import (
    HostVerifiedActor,
    ProducerCase,
    _validate_case,
    apply_producer_command,
    execute_producer_command,
    open_producer_case,
)
from matchdesk.domain.producer_preview import build_producer_desk_preview


def _actor(
    *,
    tenant: str = "team-1",
    roles: frozenset[str] = frozenset({"producer"}),
    sessions: frozenset[str] = frozenset({"demo-preview-only"}),
) -> HostVerifiedActor:
    """Build simulated trusted context without accepting request-supplied claims."""
    return HostVerifiedActor(
        subject="person-1",
        tenant_id=tenant,
        issuer="https://test-issuer.example",
        roles=roles,
        permitted_sessions=sessions,
    )


def _case() -> ProducerCase:
    """Start an independent unapproved case from deterministic evidence."""
    preview = build_producer_desk_preview()
    return open_producer_case(
        actor=_actor(),
        tenant_id="team-1",
        output=preview.output,
        claims=(preview.claim,),
        evidence=preview.evidence,
        accepted_events=preview.events,
    )


def _command(case: ProducerCase, command: str = "reverify") -> ProducerCase:
    """Exercise a command using the persisted generation and a fake producer."""
    return apply_producer_command(
        case,
        actor=_actor(),
        expected_generation=case.generation,
        command=command,  # type: ignore[arg-type]  # Deliberate invalid runtime commands are tested.
        reason="Reviewed synthetic evidence",
    )


def _revise(case: ProducerCase):
    """Create a well-formed next-version commentary draft with edited wording."""
    payload = CommentaryPayload(
        lines=(
            ClaimLinkedText(
                claim_id=case.claims[0].claim_id,
                text="Revised source-bound first-half commentary.",
            ),
        )
    )
    binding = case.output.binding.model_copy(
        update={
            "item_version": case.output.binding.item_version + 1,
            "content_digest": content_digest(payload),
        }
    )
    return case.output.model_copy(update={"binding": binding, "payload": payload})


@pytest.mark.parametrize(
    "invalid",
    [
        {"subject": " "},
        {"tenant_id": ""},
        {"issuer": "\t"},
        {"roles": frozenset()},
        {"roles": frozenset({"producer", "administrator"})},
        {"permitted_sessions": frozenset()},
        {"permitted_sessions": frozenset({" "})},
    ],
)
def test_actor_rejects_incomplete_or_unrecognised_identity(invalid: dict[str, object]) -> None:
    """An untrusted or incomplete principal must never acquire a default grant."""
    claims: dict[str, object] = {
        "subject": "person-1",
        "tenant_id": "team-1",
        "issuer": "https://test-issuer.example",
        "roles": frozenset({"producer"}),
        "permitted_sessions": frozenset({"demo-preview-only"}),
    }
    claims.update(invalid)
    with pytest.raises(ValueError):
        HostVerifiedActor(**claims)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "actor",
    [
        _actor(tenant="another-tenant"),
        _actor(sessions=frozenset({"another-session"})),
        _actor(roles=frozenset({"auditor"})),
        _actor(roles=frozenset({"publisher"})),
    ],
)
def test_mutation_requires_exact_tenant_session_and_role(actor: HostVerifiedActor) -> None:
    """Valid identities without the correct permissions are explicitly denied."""
    case = _case()
    with pytest.raises(PermissionError):
        apply_producer_command(
            case,
            actor=actor,
            expected_generation=1,
            command="reverify",
            reason="Attempted action",
        )


@pytest.mark.parametrize(
    "forgery",
    [
        "missing_audit",
        "wrong_first_action",
        "status_only_approval",
        "mismatched_review_binding",
        "blank_actor",
        "blank_reason",
        "duplicate_review_started",
        "invalid_revision",
        "wrong_generation",
    ],
)
def test_audit_history_must_reconstruct_exact_review_state(forgery: str) -> None:
    """Neither a mutable snapshot nor forged audit metadata may advance review."""
    case = _case()
    original = case.review.audit[0]
    if forgery == "missing_audit":
        case = replace(case, review=replace(case.review, audit=()))
    elif forgery == "wrong_first_action":
        case = replace(
            case,
            review=replace(case.review, audit=(replace(original, action="approved"),)),
        )
    elif forgery == "status_only_approval":
        case = replace(case, review=replace(case.review, status="approved"))
    elif forgery == "mismatched_review_binding":
        different = case.review.binding.model_copy(update={"content_digest": "a" * 64})
        case = replace(case, review=replace(case.review, binding=different))
    elif forgery in ("blank_actor", "blank_reason"):
        name = "actor_id" if forgery == "blank_actor" else "reason"
        case = replace(
            case,
            review=replace(case.review, audit=(replace(original, **{name: " "}),)),
        )
    elif forgery == "duplicate_review_started":
        case = replace(
            case,
            review=replace(case.review, audit=(original, original)),
            generation=2,
        )
    elif forgery == "invalid_revision":
        case = replace(
            case,
            review=replace(
                case.review,
                audit=(original, replace(original, action="revision_opened")),
            ),
            generation=2,
        )
    elif forgery == "wrong_generation":
        case = replace(case, generation=2)
    with pytest.raises(ValueError):
        _validate_case(case)


def test_genuine_multi_revision_review_replays_without_drift() -> None:
    """History reconstruction accepts actual approval, revision and reapproval."""
    case = _case()
    case = _command(case)
    case = _command(case, "approve")
    updated = apply_producer_command(
        case,
        actor=_actor(),
        expected_generation=3,
        command="edit",
        reason="Edit requires reapproval",
        revised_output=_revise(case),
    )
    assert updated.review.status == "pending_verification"
    _validate_case(updated)
    updated = _command(updated)
    updated = _command(updated, "approve")
    assert len(updated.review.audit) == updated.generation == 6
    _validate_case(updated)


@pytest.mark.parametrize(
    "tamper",
    [
        "blank_tenant",
        "wrong_match",
        "wrong_replay",
        "wrong_evidence_reference",
        "wrong_evidence_window",
        "duplicate_claim",
        "missing_claim",
        "no_events",
        "foreign_event",
        "missing_event",
        "unsupported_claim_event",
    ],
)
def test_case_scope_and_source_must_be_consistent(tamper: str) -> None:
    """Every source dimension is rechecked even when caller passes a typed case."""
    case = _case()
    if tamper == "blank_tenant":
        case = replace(case, tenant_id=" ")
    elif tamper in ("wrong_match", "wrong_replay", "wrong_evidence_window"):
        evidence = case.evidence
        if tamper == "wrong_match":
            evidence = evidence.model_copy(update={"match_id": "another-match"})
        elif tamper == "wrong_replay":
            evidence = evidence.model_copy(update={"replay_id": "another-replay"})
        else:
            evidence = evidence.model_copy(
                update={"window": MatchWindow(period=1, from_ms=1, to_ms=2_700_000)}
            )
        binding = case.output.binding.model_copy(
            update={"evidence_digest": content_digest(evidence)}
        )
        case = replace(
            case,
            evidence=evidence,
            output=case.output.model_copy(update={"binding": binding}),
            review=replace(
                case.review,
                binding=binding,
                audit=(replace(case.review.audit[0], binding=binding),),
            ),
        )
    elif tamper == "wrong_evidence_reference":
        case = replace(
            case,
            output=case.output.model_copy(update={"evidence_ids": ("another-evidence",)}),
        )
    elif tamper == "duplicate_claim":
        case = replace(case, claims=case.claims * 2)
    elif tamper == "missing_claim":
        case = replace(case, claims=())
    elif tamper == "no_events":
        case = replace(case, accepted_events=())
    elif tamper == "foreign_event":
        event = case.accepted_events[0].model_copy(update={"match_id": "foreign-match"})
        case = replace(case, accepted_events=(event, *case.accepted_events[1:]))
    elif tamper == "missing_event":
        case = replace(case, accepted_events=case.accepted_events[1:])
    elif tamper == "unsupported_claim_event":
        claim = case.claims[0].model_copy(update={"evidence_event_ids": ("not-in-evidence",)})
        case = replace(case, claims=(claim,))
    with pytest.raises(ValueError):
        _validate_case(case)


def test_reverification_recomputes_measured_claims() -> None:
    """A numerically invalid stored claim cannot reach approval by retaining its ID."""
    case = _case()
    original = case.claims[0]
    assert original.assertion is not None
    inaccurate = original.model_copy(
        update={"assertion": original.assertion.model_copy(update={"value": 99.0})}
    )
    case = replace(case, claims=(inaccurate,))
    with pytest.raises(ValueError, match="passing deterministic"):
        _command(case)


def test_reverification_rejects_a_wrong_evidence_hash_from_checker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provider/checker provenance must match the current source evidence digest."""
    case = _case()

    def incorrect_verifier(*args: object) -> VerificationResult:
        """Simulate a checker returning a success for a different evidence version."""
        del args
        return VerificationResult(
            claim_id=case.claims[0].claim_id,
            status="verified",
            query_id="goals-v1",
            reason="deliberately forged provenance",
            evidence_digest="0" * 64,
        )

    monkeypatch.setattr(producer_commands, "verify_claim", incorrect_verifier)
    with pytest.raises(ValueError, match="drifted"):
        _command(case)


@pytest.mark.parametrize(
    "changed",
    [
        "output_id",
        "session_id",
        "match_id",
        "windows",
        "evidence_ids",
        "claim_ids",
        "kind",
        "evidence_digest",
        "item_version",
        "item_id",
        "replay_id",
        "language",
        "persona",
    ],
)
def test_edited_output_preserves_all_scope_and_exact_version(changed: str) -> None:
    """A draft edit cannot silently swap match, persona, identity or evidence."""
    case = _case()
    draft = _revise(case)
    if changed == "kind":
        payload = ExplainerPayload(
            headline=ClaimLinkedText(claim_id=case.claims[0].claim_id, text="Headline"),
            points=(ClaimLinkedText(claim_id=case.claims[0].claim_id, text="Explanation"),),
        )
        binding = draft.binding.model_copy(update={"content_digest": content_digest(payload)})
        draft = draft.model_copy(update={"payload": payload, "binding": binding})
    elif changed in (
        "evidence_digest",
        "item_version",
        "item_id",
        "replay_id",
        "language",
        "persona",
    ):
        modifications: dict[str, object] = {
            "evidence_digest": "b" * 64,
            "item_version": 3,
            "item_id": "different-item",
            "replay_id": "different-replay",
            "language": "fr",
            "persona": "casual_fan",
        }
        binding = draft.binding.model_copy(update={changed: modifications[changed]})
        draft = draft.model_copy(update={"binding": binding})
    else:
        changes: dict[str, object] = {
            "output_id": "other-output",
            "session_id": "other-session",
            "match_id": "other-match",
            "windows": (MatchWindow(period=1, from_ms=0, to_ms=2_000_000),),
            "evidence_ids": ("different-evidence",),
            "claim_ids": ("different-claim",),
        }
        draft = draft.model_copy(update={changed: changes[changed]})
    with pytest.raises(ValueError):
        apply_producer_command(
            case,
            actor=_actor(),
            expected_generation=1,
            command="edit",
            reason="Changed something outside the review scope",
            revised_output=draft,
        )


def test_edit_requires_validated_output_and_other_commands_disallow_it() -> None:
    """Only explicit edit accepts replacement draft content."""
    case = _case()
    with pytest.raises(ValueError, match="requires a new validated"):
        _command(case, "edit")
    with pytest.raises(ValueError, match="Only edit"):
        apply_producer_command(
            case,
            actor=_actor(),
            expected_generation=1,
            command="reverify",
            reason="Check",
            revised_output=_revise(case),
        )
    with pytest.raises(ValueError, match="Unsupported"):
        _command(case, "invalid-action")


def test_rejection_is_terminal_and_a_reason_is_required() -> None:
    """Reject is auditable before reverification and cannot repeat after terminal review."""
    case = _case()
    with pytest.raises(ValueError, match="reason"):
        apply_producer_command(
            case, actor=_actor(), expected_generation=1, command="reject", reason="  "
        )
    rejected = _command(case, "reject")
    assert rejected.review.status == "rejected"
    _validate_case(rejected)
    with pytest.raises(ValueError, match="already terminal"):
        _command(rejected, "reject")


class OfflineStore:
    """Minimal in-memory adapter for testing host-owned atomic command boundaries."""

    def __init__(self, case: ProducerCase | None) -> None:
        """Hold the loaded case; absent and out-of-scope snapshots can be simulated."""
        self.case = case
        self.loads = 0

    def load(self, tenant_id: str, session_id: str, output_id: str) -> ProducerCase | None:
        """Return the chosen fixture to exercise the caller's scope checks."""
        del tenant_id, session_id, output_id
        self.loads += 1
        return self.case

    def replace_if_generation(self, case: ProducerCase, *, expected_generation: int) -> bool:
        """Apply a successful in-memory generation compare-and-swap."""
        if self.case is None or self.case.generation != expected_generation:
            return False
        self.case = case
        return True


def _execute(store: OfflineStore, *, actor: HostVerifiedActor | None = None) -> ProducerCase:
    """Drive the host command using canonical tenant, session and output identifiers."""
    return execute_producer_command(
        store,
        actor=actor or _actor(),
        tenant_id="team-1",
        session_id="demo-preview-only",
        output_id="demo-story-output",
        expected_generation=1,
        command="reverify",
        reason="Checked source metric",
    )


def test_store_successful_cas_advances_one_generation_with_audit() -> None:
    """A successful compare-and-swap commits one state/audit transition."""
    store = OfflineStore(_case())
    updated = _execute(store)
    assert updated.generation == store.case.generation == 2
    assert len(updated.review.audit) == 2
    assert updated.review.audit[-1].action == "reverified"
    assert store.loads == 1


def test_store_authorises_before_loading_and_fails_closed_on_absence() -> None:
    """No out-of-tenant request may learn whether a case even exists."""
    store = OfflineStore(_case())
    with pytest.raises(PermissionError):
        _execute(store, actor=_actor(tenant="different-tenant"))
    assert store.loads == 0
    store.case = None
    with pytest.raises(LookupError, match="does not exist"):
        _execute(store)


@pytest.mark.parametrize("wrong", ["tenant", "session", "output"])
def test_store_rejects_out_of_scope_loaded_cases(wrong: str) -> None:
    """A buggy store cannot silently return a record from another security scope."""
    case = _case()
    if wrong == "tenant":
        case = replace(case, tenant_id="foreign-tenant")
    elif wrong == "session":
        case = replace(
            case, output=case.output.model_copy(update={"session_id": "foreign-session"})
        )
    else:
        case = replace(case, output=case.output.model_copy(update={"output_id": "foreign-output"}))
    store = OfflineStore(case)
    with pytest.raises(PermissionError, match="out-of-scope"):
        _execute(store)
