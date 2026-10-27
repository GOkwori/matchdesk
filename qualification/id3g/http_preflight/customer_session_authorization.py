"""Check live account authority before using a persisted customer session.

This policy is independent of cookie signing, routing, customer provisioning
and workforce identity. Call it at every customer HTTP authorization boundary.
"""

from __future__ import annotations

from datetime import datetime

from matchdesk.domain.customer_identity import (
    CustomerAccountDirectory,
    resolve_customer_account,
)
from matchdesk.domain.customer_sessions import (
    CustomerSession,
    CustomerSessionStore,
    resolve_customer_session,
)


def resolve_authorized_customer_session(
    opaque_session_id: str,
    *,
    store: CustomerSessionStore,
    directory: CustomerAccountDirectory,
    now: datetime | None = None,
) -> CustomerSession:
    """Reject revoked, expired, suspended or reassigned customer sessions.

    Verify the server-owned bearer before consulting the registry. Resolve an
    exact broker identity, never an email or provider claim; the registered
    account must still match the account bound to the persisted session.
    Outages propagate so HTTP callers can fail closed with a generic 503.
    """
    session = resolve_customer_session(opaque_session_id, store=store, now=now)
    account_id = resolve_customer_account(session.identity, directory=directory)
    if account_id != session.account_id:
        raise PermissionError("Customer account association has changed")
    return session
