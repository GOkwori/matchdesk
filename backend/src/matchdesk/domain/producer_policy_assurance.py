"""Fail-closed, host-owned Entra policy enforcement evidence for producer work.

A signed acrs token claim is NOT proof that the configured Entra policy
actually enforced MFA for this person, client and authentication context.
This module validates a separately obtained, current policy assurance result.
It does NOT fetch Graph or accept evidence from the request or browser.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Protocol

ControlStrength = Literal["multifactor", "phishing_resistant"]
_GUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\\Z")
_MAX_ASSURANCE_AGE_SECONDS = 120


@dataclass(frozen=True, slots=True)
class ProducerPolicyEvidence:
    """Host-resolved current policy coverage for an exact operator and session.

    The trusted provider must independently verify the ENABLED Entra Conditional
    Access policy, authentication context and actor/client inclusion. This
    structure alone does not attest the source or enforce a real tenant policy.
    """

    tenant_id: str
    subject: str
    session_id: str
    context_id: str
    client_ids: frozenset[str]
    policy_id: str
    control: ControlStrength
    enforced: bool
    actor_included: bool
    verified_at_seconds: int


class ProducerPolicyAssuranceProvider(Protocol):
    """Privileged host adapter for independently verified Entra policy state.

    Implementations MUST query an independently trusted authoritative source,
    verify actual tenant policy enforcement and current actor inclusion,
    bind every approved client ID, and fail closed on outages/stale evidence.
    Never implement by decoding the caller's JWT or reading browser flags.
    """

    def assess(
        self,
        *,
        tenant_id: str,
        subject: str,
        session_id: str,
        context_id: str,
        client_ids: frozenset[str],
    ) -> ProducerPolicyEvidence | None:
        """Return fresh host-resolved enforcement evidence or None to deny."""


def qualify_producer_policy_assurance(
    *,
    provider: ProducerPolicyAssuranceProvider,
    tenant_id: str,
    subject: str,
    session_id: str,
    context_id: str,
    client_ids: frozenset[str],
    now: datetime,
) -> None:
    """Require a current enforced control before any producer SQL authority.

    The same check is applied at HTTP authentication and again immediately
    before grant staging. No proof, untrusted shape, missing policy coverage,
    stale result, downgraded control or provider outage can yield authority.
    """
    if (
        not callable(getattr(provider, "assess", None))
        or type(now) is not datetime
        or now.tzinfo is None
        or now.utcoffset() is None
        or type(client_ids) is not frozenset
        or not client_ids
        or type(context_id) is not str
        or re.fullmatch(r"c(?:[1-9]|[1-9][0-9])", context_id) is None
    ):
        raise PermissionError("Producer policy assurance is not configured")
    try:
        result = provider.assess(
            tenant_id=tenant_id,
            subject=subject,
            session_id=session_id,
            context_id=context_id,
            client_ids=client_ids,
        )
    except Exception:
        raise PermissionError("Producer policy assurance unavailable") from None
    timestamp = int(now.astimezone(timezone.utc).timestamp())
    if (
        type(result) is not ProducerPolicyEvidence
        or result.tenant_id != tenant_id
        or result.subject != subject
        or result.session_id != session_id
        or result.context_id != context_id
        or result.client_ids != client_ids
        or type(result.policy_id) is not str
        or _GUID.fullmatch(result.policy_id) is None
        or result.control not in ("multifactor", "phishing_resistant")
        or result.enforced is not True
        or result.actor_included is not True
        or type(result.verified_at_seconds) is not int
        or result.verified_at_seconds > timestamp
        or timestamp - result.verified_at_seconds > _MAX_ASSURANCE_AGE_SECONDS
    ):
        raise PermissionError("Producer policy assurance denied")
