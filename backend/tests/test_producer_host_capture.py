"""Negative security tests for inert authenticated-host capture preflight."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from matchdesk.domain.producer_grant_preflight import ProducerGrantPreflight
from matchdesk.domain.producer_host_capture import (
    VerifiedOperatorDialogEvent,
    qualify_host_operator_confirmation,
)
from matchdesk.domain.producer_policy_assurance import ProducerPolicyEvidence

NOW = 1_782_000_000
TENANT = "ci-tenant"
SUBJECT = "ci-operator"
SESSION = "ci-session"
CONTEXT = "c1"
CLIENTS = frozenset({"ci-client"})


class Policy:
    """Synthetic host policy resolver; not real Entra policy enforcement."""

    def __init__(self):
        """Permit the expected CI scope until explicitly revoked."""
        self.allowed = True
        self.calls = 0

    def assess(self, *, tenant_id, subject, session_id, context_id, client_ids):
        """Bind synthetic evidence to the exact requested CA scope."""
        self.calls += 1
        if not self.allowed:
            return None
        return ProducerPolicyEvidence(
            tenant_id=tenant_id,
            subject=subject,
            session_id=session_id,
            context_id=context_id,
            client_ids=client_ids,
            policy_id="11111111-2222-3333-4444-555555555555",
            control="multifactor",
            enforced=True,
            actor_included=True,
            verified_at_seconds=NOW - 1,
        )


class Dialog:
    """One-time synthetic host event consumed at most once."""

    def __init__(self, event):
        """Hold one inert CI event and record consumption."""
        self.event = event
        self.calls = 0

    def consume_verified_dialog_event(self, *, confirmation_id, tenant_id):
        """Return only the initially matching event on the first attempt."""
        self.calls += 1
        if self.calls != 1:
            return None
        return self.event


def fixture():
    """Produce an aligned confirmation and authenticated-event test fixture."""
    preflight = ProducerGrantPreflight(
        confirmation_id="a" * 32,
        actor_id=SUBJECT,
        token_issuer="https://issuer.invalid",
        tenant_id=TENANT,
        session_id=SESSION,
        output_id="ci-output",
        action="approve",
        expected_generation=2,
        authorized_case_sha256="b" * 64,
        authorized_audit_digest="c" * 64,
        confirmation_expires_at=NOW + 50,
    )
    event = VerifiedOperatorDialogEvent(
        event_id="e" * 32,
        challenge_id="f" * 32,
        confirmation_id=preflight.confirmation_id,
        tenant_id=TENANT,
        actor_id=SUBJECT,
        token_issuer=preflight.token_issuer,
        session_id=SESSION,
        output_id="ci-output",
        action="approve",
        expected_generation=2,
        authorized_case_sha256=preflight.authorized_case_sha256,
        authorized_audit_digest=preflight.authorized_audit_digest,
        interaction_method="workforce_authenticated_custom_dialog",
        confirmed_at_seconds=NOW - 10,
        verified_at_seconds=NOW - 3,
    )
    return preflight, Dialog(event), Policy()


def verify(preflight, dialog, policy):
    """Apply identical test-only host parameters across negative cases."""
    return qualify_host_operator_confirmation(
        source=dialog,
        policy_assurance=policy,
        preflight=preflight,
        signed_envelope="ci-host-held-signature",
        context_id=CONTEXT,
        client_ids=CLIENTS,
        now=datetime.fromtimestamp(NOW, timezone.utc),
    )


def test_exact_host_event_matches_without_granting_execution():
    """Return an inert record; no issuer, database or signing API is invoked."""
    preflight, dialog, policy = fixture()
    result = verify(preflight, dialog, policy)
    assert result.actor_id == SUBJECT
    assert result.state == "confirmed"
    assert result.event_id == "e" * 32
    assert dialog.calls == 1 and policy.calls == 1


def test_one_time_host_challenge_cannot_be_replayed():
    """A consumed event cannot produce a second host confirmation record."""
    preflight, dialog, policy = fixture()
    verify(preflight, dialog, policy)
    with pytest.raises(PermissionError, match="authenticated confirmation denied"):
        verify(preflight, dialog, policy)
    assert dialog.calls == 2


def test_denied_policy_prevents_event_consumption():
    """A failed independent CA source stops the workflow before consumption."""
    preflight, dialog, policy = fixture()
    policy.allowed = False
    with pytest.raises(PermissionError, match="authenticated confirmation denied"):
        verify(preflight, dialog, policy)
    assert dialog.calls == 0


@pytest.mark.parametrize(
    "updates",
    [
        {"tenant_id": "wrong-tenant"},
        {"actor_id": "other-person"},
        {"session_id": "other-session"},
        {"output_id": "other-output"},
        {"action": "reject"},
        {"expected_generation": 3},
        {"authorized_case_sha256": "d" * 64},
        {"authorized_audit_digest": "d" * 64},
        {"confirmation_id": "b" * 32},
        {"event_id": "a" * 32},
        {"challenge_id": "e" * 32},
        {"interaction_method": "browser_self_report"},
        {"confirmed_at_seconds": NOW - 121},
        {"verified_at_seconds": NOW + 1},
    ],
)
def test_mismatched_or_stale_operator_events_deny(updates):
    """Client assertions, replay and changed generation never create evidence."""
    preflight, dialog, policy = fixture()
    dialog.event = replace(dialog.event, **updates)
    with pytest.raises(PermissionError, match="authenticated confirmation denied"):
        verify(preflight, dialog, policy)


def test_outage_or_missing_provenance_denies():
    """Missing host evidence cannot be replaced by a signed envelope alone."""
    preflight, dialog, policy = fixture()
    dialog.event = None
    with pytest.raises(PermissionError, match="authenticated confirmation denied"):
        verify(preflight, dialog, policy)


def test_expired_preflight_denies_without_touching_host():
    """Signed expired intent cannot consume the one-time host challenge."""
    preflight, dialog, policy = fixture()
    with pytest.raises(PermissionError, match="authenticated confirmation denied"):
        verify(replace(preflight, confirmation_expires_at=NOW), dialog, policy)
    assert policy.calls == 0 and dialog.calls == 0
