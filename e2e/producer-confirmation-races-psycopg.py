"""Disposable PostgreSQL race and mid-transaction expiry qualification.

This is synthetic CI evidence, not human approval, delegated Entra MFA, a
trusted confirmation stager, or permission to activate the producer API.
The issuer/revoker connect using separate physical SCRAM workload logins.
"""

from __future__ import annotations

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import psycopg

_ISSUER = "matchdesk_issuer_executor_ci"
_REVOKER = "matchdesk_revoker_executor_ci"
_ISSUER_PASSWORD = os.environ.get("ISSUER_CI_PASSWORD", "")
_REVOKER_PASSWORD = os.environ.get("REVOKER_CI_PASSWORD", "")
_ISSUE_RACE = "1" * 32
_REVOKE_RACE = "2" * 32
_EXPIRY_RACE = "3" * 32
_RACE_GRANTS = tuple(f"ci-issuer-race-grant-{n:02d}" for n in range(3))
_REVOKE_GRANT = "ci-issuer-race-revoke-grant"
_EXPIRY_GRANT = "ci-issuer-expiry-during-grant"
_BINDING = '{"ci":"confirmed"}'
_CASE_DIGEST = "a" * 64
_AUDIT_DIGEST = "d" * 64
_ACTOR = "ci-issuer-human"
_TOKEN_ISSUER = "https://issuer-ci.example.invalid"
_TENANT = "ci-issuer-tenant"
_SESSION = "ci-issuer-session"
_OUTPUT = "ci-issuer-output"


def _connection(role: str, password: str):
    """Require real physical login, never a connection that uses SET ROLE."""
    if os.getenv("CI") != "true" or len(password) < 32:
        raise RuntimeError("Disposable CI physical credentials are mandatory")
    return psycopg.connect(
        host="postgres",
        dbname="matchdesk",
        user=role,
        password=password,
        sslmode="prefer",
        connect_timeout=10,
        autocommit=True,
    )


def _owner():
    """Owner access is used only to stage and independently inspect CI fixtures."""
    password = os.environ.get("PGPASSWORD", "")
    return _connection("matchdesk", password)


def _stage(cursor, confirmation: str, duration: str = "115 seconds") -> None:
    """Create a fresh synthetic scope record with an explicit finite expiry."""
    cursor.execute(
        "INSERT INTO public.matchdesk_producer_confirmations "
        "(confirmation_id, tenant_id, session_id, output_id, actor_id, "
        "issuer, action, expected_generation, binding, "
        "authorized_case_sha256, authorized_audit_digest, proof_digest, "
        "confirmed_at, expires_at) VALUES "
        "(%s,%s,%s,%s,%s,%s,'create',0,%s::jsonb,%s,%s,%s,"
        "clock_timestamp(),clock_timestamp() + %s::interval)",
        (
            confirmation, _TENANT, _SESSION, _OUTPUT, _ACTOR, _TOKEN_ISSUER,
            _BINDING, _CASE_DIGEST, _AUDIT_DIGEST, "b" * 64, duration,
        ),
    )


def _issue(cursor, confirmation: str, grant: str) -> bool:
    """Call the grant issuer with fully parameterized exact-scope inputs."""
    cursor.execute(
        "SELECT public.matchdesk_issue_confirmed_producer_grant("
        "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)",
        (
            confirmation, grant, _TENANT, _SESSION, _OUTPUT, _ACTOR,
            _TOKEN_ISSUER, "create", 0, _BINDING, _CASE_DIGEST, _AUDIT_DIGEST,
        ),
    )
    receipt = cursor.fetchone()
    assert receipt is not None and type(receipt[0]) is bool
    return receipt[0]


def _revoke(cursor, confirmation: str) -> bool:
    """Invoke only the separately privileged revocation function."""
    cursor.execute(
        "SELECT public.matchdesk_revoke_confirmed_producer_grant(%s)",
        (confirmation,),
    )
    receipt = cursor.fetchone()
    assert receipt is not None and type(receipt[0]) is bool
    return receipt[0]


def _issue_race() -> None:
    """Three physically distinct issuers cannot consume one confirmation twice."""
    gate = Barrier(len(_RACE_GRANTS))

    def contender(grant: str) -> bool:
        """Open independent physical credentials and synchronize execution."""
        with _connection(_ISSUER, _ISSUER_PASSWORD) as connection:
            with connection.cursor() as cursor:
                gate.wait(timeout=15)
                return _issue(cursor, _ISSUE_RACE, grant)

    with ThreadPoolExecutor(max_workers=len(_RACE_GRANTS)) as pool:
        futures = [pool.submit(contender, grant) for grant in _RACE_GRANTS]
        receipts = [future.result(timeout=35) for future in futures]
    assert receipts.count(True) == 1 and receipts.count(False) == 2, receipts


def _revoke_race() -> None:
    """Issuer and separate revoker serialize across the confirmation row lock."""
    gate = Barrier(2)

    def issuer() -> bool:
        """Try issuance in its own authenticated PostgreSQL session."""
        with _connection(_ISSUER, _ISSUER_PASSWORD) as connection:
            with connection.cursor() as cursor:
                gate.wait(timeout=15)
                return _issue(cursor, _REVOKE_RACE, _REVOKE_GRANT)

    def revoker() -> bool:
        """Attempt revocation under a separate authenticated identity."""
        with _connection(_REVOKER, _REVOKER_PASSWORD) as connection:
            with connection.cursor() as cursor:
                gate.wait(timeout=15)
                return _revoke(cursor, _REVOKE_RACE)

    with ThreadPoolExecutor(max_workers=2) as pool:
        grant_result = pool.submit(issuer)
        revoke_result = pool.submit(revoker)
        was_issued = grant_result.result(timeout=35)
        was_revoked = revoke_result.result(timeout=35)
    assert type(was_issued) is bool and was_revoked is True


def _expiry_during_issuance() -> None:
    """Expire while a trigger delays insertion, proving atomic rollback."""
    with _owner() as owner:
        with owner.cursor() as cursor:
            _stage(cursor, _EXPIRY_RACE, "1 second")
            cursor.execute(
                "CREATE FUNCTION public.matchdesk_ci_delay_confirmed_issuer() "
                "RETURNS trigger LANGUAGE plpgsql AS $fn$ BEGIN "
                "IF NEW.confirmation_id = '" + _EXPIRY_RACE + "' THEN "
                "PERFORM pg_catalog.pg_sleep(2); END IF; RETURN NEW; "
                "END; $fn$"
            )
            cursor.execute(
                "CREATE TRIGGER matchdesk_ci_delay_confirmed_issuer "
                "BEFORE INSERT ON public.matchdesk_producer_action_grants "
                "FOR EACH ROW EXECUTE FUNCTION "
                "public.matchdesk_ci_delay_confirmed_issuer()"
            )
    try:
        start = time.monotonic()
        with _connection(_ISSUER, _ISSUER_PASSWORD) as connection:
            with connection.cursor() as cursor:
                try:
                    _issue(cursor, _EXPIRY_RACE, _EXPIRY_GRANT)
                except psycopg.Error as exc:
                    if "Confirmation issuance expired or was revoked" not in str(exc):
                        raise
                else:
                    raise AssertionError("Grant did not roll back on mid-write expiry")
        assert time.monotonic() - start >= 1.8, "Expiry barrier did not execute"
    finally:
        with _owner() as owner:
            with owner.cursor() as cursor:
                cursor.execute(
                    "DROP TRIGGER IF EXISTS matchdesk_ci_delay_confirmed_issuer "
                    "ON public.matchdesk_producer_action_grants"
                )
                cursor.execute(
                    "DROP FUNCTION IF EXISTS "
                    "public.matchdesk_ci_delay_confirmed_issuer()"
                )


def _verify() -> None:
    """Reconcile grants and confirmation rows after a real PostgreSQL restart."""
    with _owner() as owner:
        with owner.cursor() as cursor:
            cursor.execute(
                "SELECT issued_grant_id, consumed_at IS NOT NULL, "
                "revoked_at IS NOT NULL FROM "
                "public.matchdesk_producer_confirmations "
                "WHERE confirmation_id=%s",
                (_ISSUE_RACE,),
            )
            race = cursor.fetchone()
            assert race is not None and race[0] in _RACE_GRANTS
            assert race[1:] == (True, False)
            cursor.execute(
                "SELECT grant_id, revoked_at, consumed_at FROM "
                "public.matchdesk_producer_action_grants "
                "WHERE confirmation_id=%s",
                (_ISSUE_RACE,),
            )
            grants = cursor.fetchall()
            assert len(grants) == 1 and grants[0][0] == race[0]
            assert grants[0][1:] == (None, None)

            cursor.execute(
                "SELECT issued_grant_id, consumed_at IS NOT NULL, "
                "revoked_at IS NOT NULL FROM "
                "public.matchdesk_producer_confirmations "
                "WHERE confirmation_id=%s",
                (_REVOKE_RACE,),
            )
            revoked = cursor.fetchone()
            assert revoked is not None and revoked[2] is True
            cursor.execute(
                "SELECT grant_id, revoked_at IS NOT NULL, consumed_at "
                "FROM public.matchdesk_producer_action_grants "
                "WHERE confirmation_id=%s",
                (_REVOKE_RACE,),
            )
            downstream = cursor.fetchall()
            if revoked[1]:
                assert revoked[0] == _REVOKE_GRANT
                assert downstream == [(_REVOKE_GRANT, True, None)]
            else:
                assert revoked[0] is None and downstream == []

            cursor.execute(
                "SELECT issued_grant_id, consumed_at, revoked_at "
                "FROM public.matchdesk_producer_confirmations "
                "WHERE confirmation_id=%s",
                (_EXPIRY_RACE,),
            )
            assert cursor.fetchone() == (None, None, None)
            cursor.execute(
                "SELECT count(*) FROM public.matchdesk_producer_action_grants "
                "WHERE confirmation_id=%s",
                (_EXPIRY_RACE,),
            )
            assert cursor.fetchone() == (0,)
    print(
        "MATCHDESK_CONFIRMATION_RACE_RESTART_PASS: "
        "one grant, serialized revocation, expiry rollback"
    )


def main() -> None:
    """Run the requested CI phase with separate identities and zero publishing."""
    if len(sys.argv) != 2 or sys.argv[1] not in ("initial", "verify"):
        raise ValueError("Expected initial or verify disposable issuer race phase")
    if sys.argv[1] == "verify":
        _verify()
        return
    if min(len(_ISSUER_PASSWORD), len(_REVOKER_PASSWORD)) < 32:
        raise RuntimeError("Two distinct CI workload credentials are required")
    with _owner() as owner:
        with owner.cursor() as cursor:
            _stage(cursor, _ISSUE_RACE)
            _stage(cursor, _REVOKE_RACE)
    _issue_race()
    _revoke_race()
    _expiry_during_issuance()
    print("PASS: physical issuer contention, revocation contention and expiry barrier")


if __name__ == "__main__":
    main()
