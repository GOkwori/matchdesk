"""Owner-only disposable fixture issuance for physical-login grant qualification.

Run in the isolated API container using CI's ephemeral PostgreSQL owner password.
The user executing mutations later is a different SCRAM-authenticated LOGIN role.
"""

from __future__ import annotations

import os
import sys

import psycopg
from psycopg import sql

from matchdesk.domain.postgres_producer_store import (
    _CASE,
    _audit_digest,
    _reconcile_audit,
)
from matchdesk.domain.producer_commands import (
    HostVerifiedActor,
    _validate_case,
    open_producer_case,
)
from matchdesk.domain.producer_preview import build_producer_desk_preview

_GRANTS = {
    "valid": "ci-real-grant-valid-00001",
    "revoked": "ci-real-grant-revoked-01",
    "wrong_issuer": "ci-real-grant-issuer-001",
    "wrong_actor": "ci-real-grant-subject-01",
}


def _fixture() -> tuple[str, str, str, str, str, str]:
    """Recompute the same source-bound fixture as the restricted login process."""
    preview = build_producer_desk_preview()
    actor = HostVerifiedActor(
        subject="ci-atomic-producer",
        tenant_id="ci-atomic-tenant",
        issuer="https://ci-atomic-issuer.example.invalid",
        roles=frozenset({"producer"}),
        permitted_sessions=frozenset({"demo-preview-only"}),
    )
    case = open_producer_case(
        actor=actor,
        tenant_id=actor.tenant_id,
        output=preview.output,
        claims=(preview.claim,),
        evidence=preview.evidence,
        accepted_events=preview.events,
    )
    return (
        case.tenant_id,
        case.output.session_id,
        case.output.output_id,
        actor.subject,
        actor.issuer,
        case.output.binding.model_dump_json(),
    )



def _verify_after_restart(scope: tuple[str, str, str, str, str, str]) -> None:
    """Reconcile persisted case, immutable audit, and every grant as DB owner.

    The workload role cannot read any of these tables directly. Only this
    independent CI-only auditor inspects full persistent state after restart.
    """
    with psycopg.connect(
        "host=postgres dbname=matchdesk user=matchdesk sslmode=prefer",
        autocommit=True,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_user::text, session_user::text")
            assert cursor.fetchone() == ("matchdesk", "matchdesk")
            cursor.execute(
                "SELECT generation, case_json, audit_digest "
                "FROM public.matchdesk_producer_cases "
                "WHERE tenant_id=%s AND session_id=%s AND output_id=%s",
                scope[:3],
            )
            row = cursor.fetchone()
            assert row is not None and row[0] == 1
            case = _CASE.validate_python(row[1])
            _validate_case(case)
            assert case.tenant_id == scope[0]
            assert case.output.session_id == scope[1]
            assert case.output.output_id == scope[2]
            assert case.output.binding.model_dump_json() == scope[5]
            assert case.generation == 1
            assert case.review.status == "pending_verification"
            assert len(case.review.audit) == 1
            assert case.review.audit[0].actor_id == scope[3]
            assert case.review.audit[0].action == "review_started"
            assert row[2] == _audit_digest(case.review.audit)

            cursor.execute(
                "SELECT generation, entry_json, audit_digest "
                "FROM public.matchdesk_producer_audit "
                "WHERE tenant_id=%s AND session_id=%s AND output_id=%s "
                "ORDER BY generation",
                scope[:3],
            )
            # A second, separately constrained append-only table must match
            # the entire case-side audit history, not just the final digest.
            _reconcile_audit(case, cursor.fetchall())

            cursor.execute(
                "SELECT grant_id, revoked_at IS NOT NULL, "
                "consumed_at IS NOT NULL, command_id, action "
                "FROM public.matchdesk_producer_action_grants "
                "WHERE grant_id = ANY(%s)",
                (list(_GRANTS.values()),),
            )
            persisted = {
                grant_id: (revoked, consumed, command, action)
                for grant_id, revoked, consumed, command, action in cursor.fetchall()
            }
            assert len(persisted) == len(_GRANTS)
            assert persisted[_GRANTS["valid"]] == (
                False, True, "ci-valid-command-0000001", "create"
            )
            assert persisted[_GRANTS["revoked"]] == (
                True, False, None, "create"
            )
            assert persisted[_GRANTS["wrong_issuer"]] == (
                False, False, None, "create"
            )
            assert persisted[_GRANTS["wrong_actor"]] == (
                False, False, None, "create"
            )
    print("MATCHDESK_P4_GRANT_AUDIT_RESTART_RECONCILED: exact case, audit and grants")


def main() -> None:
    """Issue synthetic grants via the owner, never via the grant execution role."""
    if sys.argv[1:] not in (["setup"], ["verify"]) or os.getenv("CI") != "true":
        raise RuntimeError("Grant owner audit is only available in disposable CI")
    if not os.getenv("PGPASSWORD"):
        raise RuntimeError("Disposable database-owner secret is required")
    scope = _fixture()
    if sys.argv[1:] == ["verify"]:
        _verify_after_restart(scope)
        return
    with psycopg.connect(
        "host=postgres dbname=matchdesk user=matchdesk sslmode=prefer"
    ) as connection:
        with connection.cursor() as cursor:
            # Keep owner-equivalent permission out of the physical workload user.
            cursor.execute("REVOKE TEMP ON DATABASE matchdesk FROM PUBLIC")
            cursor.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            cursor.execute(
                "CREATE ROLE matchdesk_grant_definer_ci NOLOGIN NOSUPERUSER "
                "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
            )
            cursor.execute(
                "GRANT SELECT, INSERT, UPDATE ON public.matchdesk_producer_cases "
                "TO matchdesk_grant_definer_ci"
            )
            cursor.execute(
                "GRANT SELECT, INSERT ON public.matchdesk_producer_audit "
                "TO matchdesk_grant_definer_ci"
            )
            cursor.execute(
                "GRANT SELECT, UPDATE ON public.matchdesk_producer_action_grants "
                "TO matchdesk_grant_definer_ci"
            )
            # ALTER FUNCTION OWNER requires CREATE on its schema only during
            # reassignment. Remove it immediately, before restricted execution.
            cursor.execute(
                "GRANT USAGE, CREATE ON SCHEMA public TO matchdesk_grant_definer_ci"
            )
            signature = (
                "public.matchdesk_commit_producer_grant("
                "text,text,text,text,text,text,text,text,bigint,text,text,jsonb,jsonb)"
            )
            cursor.execute(
                "ALTER FUNCTION " + signature + " OWNER TO matchdesk_grant_definer_ci"
            )
            cursor.execute(
                "REVOKE CREATE ON SCHEMA public FROM matchdesk_grant_definer_ci"
            )
            cursor.execute(
                "CREATE ROLE matchdesk_grant_executor_ci LOGIN NOSUPERUSER "
                "NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
            )
            # Temporary CI SCRAM credential comes from a runner-masked env var,
            # never from a request or model-generated SQL.
            password = os.environ.get("GRANT_WRITER_CI_PASSWORD")
            if not password or len(password) < 32:
                raise RuntimeError("Ephemeral restricted login password is required")
            cursor.execute(
                sql.SQL("ALTER ROLE matchdesk_grant_executor_ci PASSWORD {}").format(
                    sql.Literal(password)
                )
            )
            cursor.execute(
                "GRANT CONNECT ON DATABASE matchdesk TO matchdesk_grant_executor_ci"
            )
            cursor.execute(
                "GRANT USAGE ON SCHEMA public TO matchdesk_grant_executor_ci"
            )
            cursor.execute(
                "GRANT EXECUTE ON FUNCTION " + signature
                + " TO matchdesk_grant_executor_ci"
            )
            for label, grant_id in _GRANTS.items():
                issuer = "https://untrusted-issuer.invalid" if label == "wrong_issuer" else scope[4]
                actor = "forged-subject" if label == "wrong_actor" else scope[3]
                cursor.execute(
                    "INSERT INTO public.matchdesk_producer_action_grants "
                    "(grant_id, tenant_id, session_id, output_id, actor_id, issuer, "
                    "action, binding, expected_generation, expires_at, revoked_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,'create',%s::jsonb,0,"
                    "clock_timestamp() + interval '10 minutes',"
                    "CASE WHEN %s THEN clock_timestamp() ELSE NULL END)",
                    (
                        grant_id,
                        scope[0],
                        scope[1],
                        scope[2],
                        actor,
                        issuer,
                        scope[5],
                        label == "revoked",
                    ),
                )
    print("PASS: synthetic issuer prepared distinct SCRAM login and four bound grants")


if __name__ == "__main__":
    main()
