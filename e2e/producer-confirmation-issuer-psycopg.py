"""Qualify the default-unused issuer and revoker under separate physical logins.

CI owner stages synthetic confirmation records; physical SCRAM-authenticated
workloads may only EXECUTE their own SECURITY DEFINER function. No live MFA,
human confirmation, production identity or publishing is qualified here.
"""

from __future__ import annotations

import os
import sys

import psycopg
from psycopg import sql

_ISSUER = "matchdesk_issuer_executor_ci"
_REVOKER = "matchdesk_revoker_executor_ci"
_SCOPES = {
    "tenant": "ci-issuer-tenant",
    "session": "ci-issuer-session",
    "output": "ci-issuer-output",
    "actor": "ci-issuer-human",
    "issuer": "https://issuer-ci.example.invalid",
    "action": "create",
    "case_hash": "a" * 64,
    "audit_hash": "d" * 64,
}
_BINDING = '{"ci":"confirmed"}'
_CONFIRMATIONS = {
    "valid": "c" * 32,
    "revoke_before": "d" * 32,
    "expired": "e" * 32,
    "revoke_after": "f" * 32,
}
_GRANTS = {
    "valid": "ci-physical-issuer-valid-01",
    "revoke_after": "ci-physical-issuer-revoke-01",
}


def _connect(role: str):
    """Connect over TCP as an actual SCRAM login, not via SET ROLE."""
    if os.environ.get("CI") != "true" or not os.environ.get("PGPASSWORD"):
        raise RuntimeError("Issuer qualification requires disposable CI credentials")
    return psycopg.connect(
        "host=postgres dbname=matchdesk user=" + role + " sslmode=prefer",
        autocommit=True,
    )


def _setup() -> None:
    """Install isolated work identities and stage synthetic signed-evidence rows."""
    issuer_password = os.environ.get("ISSUER_CI_PASSWORD", "")
    revoker_password = os.environ.get("REVOKER_CI_PASSWORD", "")
    if min(len(issuer_password), len(revoker_password)) < 32:
        raise RuntimeError("Two independent ephemeral workload credentials are required")
    with _connect("matchdesk") as conn:
        with conn.cursor() as cursor:
            cursor.execute("REVOKE TEMP ON DATABASE matchdesk FROM PUBLIC")
            cursor.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            issuer_fn = (
                "public.matchdesk_issue_confirmed_producer_grant("
                "text,text,text,text,text,text,text,text,bigint,jsonb,text,text)"
            )
            revoker_fn = "public.matchdesk_revoke_confirmed_producer_grant(text)"
            for name, func, grants in (
                (
                    "matchdesk_issuer_definer_ci",
                    issuer_fn,
                    (
                        "GRANT SELECT, UPDATE ON public.matchdesk_producer_confirmations "
                        "TO matchdesk_issuer_definer_ci",
                        "GRANT SELECT, INSERT ON public.matchdesk_producer_action_grants "
                        "TO matchdesk_issuer_definer_ci",
                    ),
                ),
                (
                    "matchdesk_revoker_definer_ci",
                    revoker_fn,
                    (
                        "GRANT SELECT, UPDATE ON public.matchdesk_producer_confirmations "
                        "TO matchdesk_revoker_definer_ci",
                        "GRANT SELECT, UPDATE ON public.matchdesk_producer_action_grants "
                        "TO matchdesk_revoker_definer_ci",
                    ),
                ),
            ):
                cursor.execute(
                    sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOCREATEDB "
                            "NOCREATEROLE NOREPLICATION NOBYPASSRLS").format(
                        sql.Identifier(name)
                    )
                )
                for command in grants:
                    cursor.execute(command)
                # Ownership transfer requires temporary CREATE; remove it
                # before any execution role can call the function.
                cursor.execute(
                    sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {}").format(
                        sql.Identifier(name)
                    )
                )
                cursor.execute(
                    sql.SQL("ALTER FUNCTION " + func + " OWNER TO {}").format(
                        sql.Identifier(name)
                    )
                )
                cursor.execute(
                    sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(
                        sql.Identifier(name)
                    )
                )

            for role, password, function in (
                (_ISSUER, issuer_password, issuer_fn),
                (_REVOKER, revoker_password, revoker_fn),
            ):
                cursor.execute(
                    sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB "
                            "NOCREATEROLE NOREPLICATION NOBYPASSRLS").format(
                        sql.Identifier(role)
                    )
                )
                cursor.execute(
                    sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                        sql.Identifier(role), sql.Literal(password)
                    )
                )
                cursor.execute(
                    sql.SQL("GRANT CONNECT ON DATABASE matchdesk TO {}").format(
                        sql.Identifier(role)
                    )
                )
                cursor.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                        sql.Identifier(role)
                    )
                )
                cursor.execute(
                    sql.SQL("GRANT EXECUTE ON FUNCTION " + function + " TO {}").format(
                        sql.Identifier(role)
                    )
                )

            for label, confirmation in _CONFIRMATIONS.items():
                modifier = (
                    "clock_timestamp() - interval '90 seconds'"
                    if label == "expired"
                    else "clock_timestamp()"
                )
                expiry = (
                    "clock_timestamp() - interval '30 seconds'"
                    if label == "expired"
                    else "clock_timestamp() + interval '115 seconds'"
                )
                cursor.execute(
                    "INSERT INTO public.matchdesk_producer_confirmations "
                    "(confirmation_id,tenant_id,session_id,output_id,actor_id,"
                    "issuer,action,expected_generation,binding,authorized_case_sha256,"
                    "authorized_audit_digest,proof_digest,confirmed_at,expires_at)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s,0,%s::jsonb,%s,%s,%s,"
                    + modifier + "," + expiry + ")",
                    (
                        confirmation,
                        _SCOPES["tenant"],
                        _SCOPES["session"],
                        _SCOPES["output"],
                        _SCOPES["actor"],
                        _SCOPES["issuer"],
                        _SCOPES["action"],
                        _BINDING,
                        _SCOPES["case_hash"],
                        _SCOPES["audit_hash"],
                        "b" * 64,
                    ),
                )
    print("PASS: independent issuer/revoker physical credentials and scoped fixtures")


def _role_authority(cursor, role: str, permitted: str, forbidden: str) -> None:
    """Reject owner impersonation, elevated roles and direct row privileges."""
    cursor.execute(
        "SELECT current_user::text, session_user::text, "
        "r.rolcanlogin, r.rolsuper, r.rolcreatedb, r.rolcreaterole, "
        "r.rolbypassrls, EXISTS("
        "SELECT 1 FROM pg_catalog.pg_auth_members m WHERE m.member=r.oid)"
        " FROM pg_catalog.pg_roles r WHERE r.rolname=current_user"
    )
    assert cursor.fetchone() == (role, role, True, False, False, False, False, False)
    for table in (
        "public.matchdesk_producer_confirmations",
        "public.matchdesk_producer_action_grants",
        "public.matchdesk_producer_cases",
        "public.matchdesk_producer_audit",
    ):
        cursor.execute(
            "SELECT has_table_privilege(current_user, %s, "
            "'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER')",
            (table,),
        )
        assert cursor.fetchone() == (False,), table
    cursor.execute(
        "SELECT has_function_privilege(current_user,%s,'EXECUTE'),"
        "has_function_privilege(current_user,%s,'EXECUTE')",
        (permitted, forbidden),
    )
    assert cursor.fetchone() == (True, False)


def _issue(cursor, confirmation: str, grant: str, *, actor: str | None = None):
    """Invoke one SQL-only, host-shaped action; it cannot mint confirmation."""
    cursor.execute(
        "SELECT public.matchdesk_issue_confirmed_producer_grant("
        "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)",
        (
            confirmation, grant, _SCOPES["tenant"], _SCOPES["session"],
            _SCOPES["output"], actor or _SCOPES["actor"], _SCOPES["issuer"],
            _SCOPES["action"], 0, _BINDING,
            _SCOPES["case_hash"], _SCOPES["audit_hash"],
        ),
    )
    return cursor.fetchone()


def _issuer_run() -> None:
    """Require exact scope, replay denial and a real issuer-only LOGIN."""
    with _connect(_ISSUER) as conn:
        with conn.cursor() as cursor:
            _role_authority(
                cursor,
                _ISSUER,
                "public.matchdesk_issue_confirmed_producer_grant("
                "text,text,text,text,text,text,text,text,bigint,jsonb,text,text)",
                "public.matchdesk_revoke_confirmed_producer_grant(text)",
            )
            assert _issue(
                cursor, _CONFIRMATIONS["valid"], _GRANTS["valid"],
                actor="forged-operator"
            ) == (False,)
            assert _issue(cursor, _CONFIRMATIONS["expired"], "ci-expired-grant-01") == (
                False,
            )
            assert _issue(cursor, _CONFIRMATIONS["valid"], _GRANTS["valid"]) == (True,)
            assert _issue(
                cursor, _CONFIRMATIONS["valid"], "ci-replayed-grant-01"
            ) == (False,)
            assert _issue(
                cursor, _CONFIRMATIONS["revoke_after"], _GRANTS["revoke_after"]
            ) == (True,)
    print("PASS: real issuer role bound to scope, expiry and single-use grants")


def _revoke_run() -> None:
    """A separately authenticated revoker cannot issue or read grant rows."""
    with _connect(_REVOKER) as conn:
        with conn.cursor() as cursor:
            _role_authority(
                cursor,
                _REVOKER,
                "public.matchdesk_revoke_confirmed_producer_grant(text)",
                "public.matchdesk_issue_confirmed_producer_grant("
                "text,text,text,text,text,text,text,text,bigint,jsonb,text,text)",
            )
            for cid in (
                _CONFIRMATIONS["revoke_before"],
                _CONFIRMATIONS["revoke_after"],
            ):
                cursor.execute(
                    "SELECT public.matchdesk_revoke_confirmed_producer_grant(%s)",
                    (cid,),
                )
                assert cursor.fetchone() == (True,)
    print("PASS: physically separate revoker invalidated pending/issued grants")


def _verify() -> None:
    """Owner independently reconciles persistent outcomes after restart."""
    with _connect("matchdesk") as conn:
        with conn.cursor() as cursor:
            for label, cid in _CONFIRMATIONS.items():
                cursor.execute(
                    "SELECT consumed_at IS NOT NULL, revoked_at IS NOT NULL,"
                    "issued_grant_id FROM public.matchdesk_producer_confirmations "
                    "WHERE confirmation_id=%s",
                    (cid,),
                )
                row = cursor.fetchone()
                expected = {
                    "valid": (True, False, _GRANTS["valid"]),
                    "revoke_before": (False, True, None),
                    "expired": (False, False, None),
                    "revoke_after": (True, True, _GRANTS["revoke_after"]),
                }[label]
                assert row == expected, (label, row)
            cursor.execute(
                "SELECT grant_id, revoked_at IS NOT NULL, consumed_at IS NOT NULL "
                "FROM public.matchdesk_producer_action_grants "
                "WHERE confirmation_id = ANY(%s)",
                (list(_CONFIRMATIONS.values()),),
            )
            rows = {grant: (revoked, consumed) for grant, revoked, consumed in cursor}
            assert rows == {
                _GRANTS["valid"]: (False, False),
                _GRANTS["revoke_after"]: (True, False),
            }, rows
    print("MATCHDESK_P4_PHYSICAL_ISSUER_RESTART_RECONCILED: 2 grants, no replay")


def main() -> None:
    """Run only the explicitly requested, CI-gated qualification phase."""
    if len(sys.argv) != 2:
        raise ValueError("Expected a single disposable CI qualification phase")
    phase = sys.argv[1]
    if phase == "setup":
        _setup()
    elif phase == "issue":
        _issuer_run()
    elif phase == "revoke":
        _revoke_run()
    elif phase == "verify":
        _verify()
    else:
        raise ValueError("Unknown issuer test phase")


if __name__ == "__main__":
    main()
