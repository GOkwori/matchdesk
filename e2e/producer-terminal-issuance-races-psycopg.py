"""Qualify transaction-serialized host revocation against grant issuance.

Run only inside disposable MatchDesk CI, with a real distinct SCRAM issuer role.
Synthetic host events come from the fixture owner, not a human approval system.
Both possible commit orders are exercised without guessing from sleep timing.
Unsupported isolation must fail closed before writes; a deliberately stale
terminal snapshot proves why the database boundary requires READ COMMITTED.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import psycopg

ISSUER = "matchdesk_issuer_executor_ci"
TENANT = "ci-terminal-serialization"
ACTOR = "ci-terminal-operator"
SESSION = "ci-terminal-session"
OUTPUT = "ci-terminal-output"
TOKEN_ISSUER = "https://ci-terminal-issuer.invalid"
ACTION = "create"
BINDING = json.dumps({"item_id": "ci-transactional-revocation"})
CASE_HASH = "a" * 64
AUDIT_HASH = "b" * 64
PROOF_HASH = "c" * 64
ISSUE_SQL = (
    "SELECT public.matchdesk_issue_confirmed_producer_grant("
    "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)"
)


def connect(
    role: str,
    password: str,
    *,
    label: str,
    isolation: psycopg.IsolationLevel = psycopg.IsolationLevel.READ_COMMITTED,
):
    """Pin isolation before any query on a physical, independently named login."""
    connection = psycopg.connect(
        host="postgres", dbname="matchdesk", user=role, password=password,
        application_name=label, connect_timeout=10, sslmode="prefer",
    )
    connection.isolation_level = isolation
    return connection


def stage(cur, confirmation: str) -> None:
    """Let only the disposable fixture owner insert a synthetic staged intent."""
    cur.execute(
        "INSERT INTO public.matchdesk_producer_confirmations "
        "(confirmation_id,tenant_id,session_id,output_id,actor_id,"
        "issuer,action,expected_generation,binding,authorized_case_sha256,"
        "authorized_audit_digest,proof_digest,confirmed_at,expires_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,0,%s::jsonb,%s,%s,%s,"
        "clock_timestamp(),clock_timestamp()+interval '90 seconds')",
        (
            confirmation, TENANT, SESSION, OUTPUT, ACTOR, TOKEN_ISSUER,
            ACTION, BINDING, CASE_HASH, AUDIT_HASH, PROOF_HASH,
        ),
    )


def seed(owner_password: str, *, staged: bool = True) -> str:
    """Insert a synthetic host event, optionally followed by its staged intent."""
    confirmation = secrets.token_hex(16)
    event = secrets.token_hex(16)
    with connect("matchdesk", owner_password, label="terminal-seed") as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.matchdesk_producer_host_confirmation_events "
                "(event_id,confirmation_id,tenant_id,actor_id,token_issuer,"
                "session_id,output_id,action,expected_generation,"
                "authorized_case_sha256,authorized_audit_digest,"
                "signed_envelope_sha256,event_channel,confirmed_at,recorded_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s, %s,0,%s,%s,%s,"
                "'workforce_authenticated_custom_dialog',"
                "clock_timestamp()-interval '2 seconds',clock_timestamp())",
                (
                    event, confirmation, TENANT, ACTOR, TOKEN_ISSUER,
                    SESSION, OUTPUT, ACTION, CASE_HASH, AUDIT_HASH, PROOF_HASH,
                ),
            )
            if staged:
                stage(cur, confirmation)
    return confirmation


def issue(cur, confirmation: str, grant: str) -> bool:
    """Run the same locked issuer function used by the real bridge."""
    cur.execute(
        ISSUE_SQL,
        (
            confirmation, grant, TENANT, SESSION, OUTPUT, ACTOR,
            TOKEN_ISSUER, ACTION, 0, BINDING, CASE_HASH, AUDIT_HASH,
        ),
    )
    return cur.fetchone()[0]


def terminal(cur, confirmation: str) -> None:
    """Insert a single immutable terminal; trigger revokes any unspent grant."""
    cur.execute(
        "INSERT INTO public.matchdesk_producer_host_confirmation_terminals "
        "(event_id,confirmation_id,tenant_id,terminal_state) "
        "VALUES (%s,%s,%s,'revoked')",
        (secrets.token_hex(16), confirmation, TENANT),
    )


def await_lock(owner_password: str, label: str) -> None:
    """Require a real PostgreSQL lock wait, not an assumed thread race."""
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        with connect("matchdesk", owner_password, label="lock-inspector") as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM pg_catalog.pg_stat_activity "
                    "WHERE application_name=%s AND wait_event_type='Lock'",
                    (label,),
                )
                if cur.fetchone()[0] == 1:
                    return
        time.sleep(0.08)
    raise AssertionError("Expected competing issuer/revoker to wait on event lock")


def reconcile(owner_password: str, confirmation: str, expected_issue: bool) -> None:
    """Read all durable rows independently of both competing transactions."""
    with connect("matchdesk", owner_password, label="terminal-reconcile") as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT consumed_at IS NOT NULL,revoked_at IS NOT NULL,"
                "issued_grant_id FROM public.matchdesk_producer_confirmations "
                "WHERE confirmation_id=%s", (confirmation,),
            )
            consumed, revoked, grant = cur.fetchone()
            assert consumed is expected_issue
            assert revoked is True
            assert (grant is not None) is expected_issue
            cur.execute(
                "SELECT revoked_at IS NOT NULL,consumed_at IS NOT NULL "
                "FROM public.matchdesk_producer_action_grants "
                "WHERE confirmation_id=%s", (confirmation,),
            )
            rows = cur.fetchall()
            assert rows == ([(True, False)] if expected_issue else [])
            cur.execute(
                "SELECT count(*) FROM public.matchdesk_producer_host_confirmation_terminals "
                "WHERE confirmation_id=%s AND tenant_id=%s",
                (confirmation, TENANT),
            )
            assert cur.fetchone()[0] == 1


def reconcile_open_grant(
    owner_password: str,
    confirmation: str,
    grant: str,
    *,
    expected_terminals: int = 0,
) -> None:
    """Independently inspect the exact unrevoked grant and terminal row count."""
    with connect("matchdesk", owner_password, label="isolation-readback") as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT consumed_at IS NOT NULL,revoked_at IS NOT NULL,"
                "issued_grant_id FROM public.matchdesk_producer_confirmations "
                "WHERE confirmation_id=%s", (confirmation,),
            )
            assert cur.fetchone() == (True, False, grant)
            cur.execute(
                "SELECT grant_id,revoked_at IS NOT NULL,consumed_at IS NOT NULL,"
                "expires_at > clock_timestamp() "
                "FROM public.matchdesk_producer_action_grants "
                "WHERE confirmation_id=%s", (confirmation,),
            )
            assert cur.fetchall() == [(grant, False, False, True)]
            cur.execute(
                "SELECT count(*) FROM public.matchdesk_producer_host_confirmation_terminals "
                "WHERE confirmation_id=%s AND tenant_id=%s",
                (confirmation, TENANT),
            )
            assert cur.fetchone()[0] == expected_terminals


def run_stale_terminal_snapshot(owner_password: str, issuer_password: str) -> None:
    """Reject a terminal snapshot taken before the staged row and grant existed."""
    confirmation = seed(owner_password, staged=False)
    grant = secrets.token_urlsafe(24)
    count_staged = (
        "SELECT count(*) FROM public.matchdesk_producer_confirmations "
        "WHERE confirmation_id=%s"
    )
    with connect(
        "matchdesk", owner_password, label="terminal-stale-snapshot",
        isolation=psycopg.IsolationLevel.REPEATABLE_READ,
    ) as stale:
        with stale.cursor() as cur:
            # This read pins an actual empty snapshot before two independent
            # committed transactions create the staged row and issue its grant.
            cur.execute(count_staged, (confirmation,))
            assert cur.fetchone()[0] == 0
            with connect("matchdesk", owner_password, label="later-stage") as conn:
                with conn.cursor() as stage_cur:
                    stage(stage_cur, confirmation)
            with connect(ISSUER, issuer_password, label="later-issue") as conn:
                with conn.cursor() as issue_cur:
                    assert issue(issue_cur, confirmation, grant) is True
            cur.execute(count_staged, (confirmation,))
            assert cur.fetchone()[0] == 0
            try:
                terminal(cur, confirmation)
            except psycopg.errors.FeatureNotSupported as error:
                assert error.sqlstate == "0A000"
                stale.rollback()
            else:
                # On the vulnerable baseline, commit rather than hiding the
                # defect with test rollback. This database is disposable only.
                stale.commit()
                reconcile_open_grant(
                    owner_password, confirmation, grant, expected_terminals=1
                )
                print(
                    "MATCHDESK_P4_TERMINAL_STALE_SNAPSHOT_DEFECT_REPRODUCED: "
                    "committed terminal left the later unspent grant unrevoked",
                    flush=True,
                )
                raise AssertionError(
                    "REPEATABLE READ terminal committed without revoking the issued grant"
                )
    # Rejection must be write-free. A caller must explicitly start a fresh
    # supported transaction; the database must never silently change isolation.
    reconcile_open_grant(owner_password, confirmation, grant)
    with connect("matchdesk", owner_password, label="terminal-fresh-snapshot") as conn:
        with conn.cursor() as cur:
            terminal(cur, confirmation)
    reconcile(owner_password, confirmation, expected_issue=True)


def run_unsupported_issuer(
    owner_password: str, issuer_password: str, isolation: psycopg.IsolationLevel
) -> None:
    """Deny a valid issuer request under unsupported isolation without mutation."""
    confirmation = seed(owner_password)
    grant = secrets.token_urlsafe(24)
    with connect(
        ISSUER, issuer_password, label="issuer-unsupported-isolation", isolation=isolation
    ) as conn:
        with conn.cursor() as cur:
            assert issue(cur, confirmation, grant) is False
    with connect("matchdesk", owner_password, label="issuer-denial-readback") as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT consumed_at IS NULL,revoked_at IS NULL,issued_grant_id "
                "FROM public.matchdesk_producer_confirmations WHERE confirmation_id=%s",
                (confirmation,),
            )
            assert cur.fetchone() == (True, True, None)
            cur.execute(
                "SELECT count(*) FROM public.matchdesk_producer_action_grants "
                "WHERE confirmation_id=%s", (confirmation,),
            )
            assert cur.fetchone()[0] == 0
    # The same still-valid fixture must succeed through the supported issuer,
    # proving that unsupported isolation, not broken fixture data, caused denial.
    with connect(ISSUER, issuer_password, label="issuer-supported-control") as conn:
        with conn.cursor() as cur:
            assert issue(cur, confirmation, grant) is True
    reconcile_open_grant(owner_password, confirmation, grant)
    with connect("matchdesk", owner_password, label="issuer-control-revoke") as conn:
        with conn.cursor() as cur:
            terminal(cur, confirmation)
    reconcile(owner_password, confirmation, expected_issue=True)


def run_unsupported_terminal(
    owner_password: str, issuer_password: str, isolation: psycopg.IsolationLevel
) -> None:
    """Prove the isolation policy, without asserting a Serializable exploit."""
    confirmation = seed(owner_password)
    grant = secrets.token_urlsafe(24)
    with connect(ISSUER, issuer_password, label="terminal-policy-issue") as conn:
        with conn.cursor() as cur:
            assert issue(cur, confirmation, grant) is True
    with connect(
        "matchdesk", owner_password, label="terminal-unsupported-isolation",
        isolation=isolation,
    ) as conn:
        with conn.cursor() as cur:
            try:
                terminal(cur, confirmation)
            except psycopg.errors.FeatureNotSupported as error:
                assert error.sqlstate == "0A000"
                conn.rollback()
            else:
                raise AssertionError("Terminal accepted unsupported transaction isolation")
    reconcile_open_grant(owner_password, confirmation, grant)
    with connect("matchdesk", owner_password, label="terminal-supported-control") as conn:
        with conn.cursor() as cur:
            terminal(cur, confirmation)
    reconcile(owner_password, confirmation, expected_issue=True)


def run_race(*, owner_password: str, issuer_password: str, revoke_first: bool) -> None:
    """Force both serial orders with an uncommitted first writer and lock wait."""
    confirmation = seed(owner_password)
    grant_id = secrets.token_urlsafe(24)
    first_is_terminal = revoke_first
    first_ready = Event()
    release = Event()
    first_label = "terminal-first" if first_is_terminal else "issuer-first"
    second_label = "issuer-waiting" if first_is_terminal else "terminal-waiting"

    def first() -> bool:
        """Hold the advisory transaction lock until the opposing writer waits."""
        role = "matchdesk" if first_is_terminal else ISSUER
        password = owner_password if first_is_terminal else issuer_password
        with connect(role, password, label=first_label) as conn:
            with conn.cursor() as cur:
                try:
                    if first_is_terminal:
                        terminal(cur, confirmation)
                        receipt = False
                    else:
                        receipt = issue(cur, confirmation, grant_id)
                    first_ready.set()
                    assert release.wait(timeout=20)
                    return receipt
                finally:
                    first_ready.set()

    def second() -> bool:
        """Attempt the opposing operation under an independent TCP login."""
        role = ISSUER if first_is_terminal else "matchdesk"
        password = issuer_password if first_is_terminal else owner_password
        with connect(role, password, label=second_label) as conn:
            with conn.cursor() as cur:
                if first_is_terminal:
                    return issue(cur, confirmation, grant_id)
                terminal(cur, confirmation)
                return True

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(first)
        assert first_ready.wait(timeout=15)
        assert not f1.done(), "First transaction failed before lock coordination"
        f2 = pool.submit(second)
        try:
            await_lock(owner_password, second_label)
        finally:
            release.set()
        first_result = f1.result(timeout=25)
        second_result = f2.result(timeout=25)
    assert (first_result, second_result) == (
        (False, False) if revoke_first else (True, True)
    )
    reconcile(owner_password, confirmation, expected_issue=not revoke_first)


def main() -> None:
    """Run deterministic real database concurrency and independent readback."""
    owner_password = os.getenv("PGPASSWORD", "")
    issuer_password = os.getenv("ISSUER_CI_PASSWORD", "")
    if (
        os.getenv("CI") != "true"
        or re.fullmatch(
            r"matchdesk-it-[0-9]+-[0-9]+", os.getenv("COMPOSE_PROJECT_NAME", "")
        ) is None
        or len(owner_password) < 16
        or len(issuer_password) < 32
        or owner_password == issuer_password
    ):
        raise RuntimeError("Terminal issuance race requires disposable distinct CI roles")
    # Run the absent-then-created-row regression first so a vulnerable source
    # produces durable defect evidence before any broader policy assertion fails.
    run_stale_terminal_snapshot(owner_password, issuer_password)
    for isolation in (
        psycopg.IsolationLevel.REPEATABLE_READ,
        psycopg.IsolationLevel.SERIALIZABLE,
        psycopg.IsolationLevel.READ_UNCOMMITTED,
    ):
        run_unsupported_issuer(owner_password, issuer_password, isolation)
    for isolation in (
        psycopg.IsolationLevel.SERIALIZABLE,
        psycopg.IsolationLevel.READ_UNCOMMITTED,
    ):
        run_unsupported_terminal(owner_password, issuer_password, isolation)
    run_race(
        owner_password=owner_password, issuer_password=issuer_password, revoke_first=True
    )
    run_race(
        owner_password=owner_password, issuer_password=issuer_password, revoke_first=False
    )
    print(
        "MATCHDESK_P4_TERMINAL_ISSUANCE_SERIALIZED_PASS: "
        "terminal-first denies, issuance-first revokes unspent grant"
    )
    print(
        "MATCHDESK_P4_TERMINAL_ISOLATION_GUARD_PASS: unsupported isolation "
        "refused without writes, fresh READ COMMITTED revokes"
    )


if __name__ == "__main__":
    main()
