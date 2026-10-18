"""Real restricted-login producer grant qualification for disposable CI PostgreSQL.

The synthetic actor is a test fixture, NOT a signed workforce identity. All
database mutations are performed via a physically distinct least-privilege
LOGIN role. Privileged fixture issuance lives outside the API container.
"""

from __future__ import annotations

import json
import os
import sys

import psycopg

from matchdesk.domain.postgres_producer_grant_writer import PostgresProducerGrantWriter
from matchdesk.domain.postgres_producer_store import _ENTRY, _audit_digest, _case_json
from matchdesk.domain.producer_commands import HostVerifiedActor, open_producer_case
from matchdesk.domain.producer_preview import build_producer_desk_preview
from matchdesk.domain.psycopg_producer_driver import producer_connection_factory

_ROLE = "matchdesk_grant_executor_ci"
_GRANTS = {
    "valid": "ci-real-grant-valid-00001",
    "revoked": "ci-real-grant-revoked-01",
    "wrong_issuer": "ci-real-grant-issuer-001",
    "wrong_actor": "ci-real-grant-subject-01",
    "tampered_case": "ci-real-grant-case-tamper-01",
    "tampered_audit": "ci-real-grant-audit-tamper-01",
}


def _case():
    """Create a deterministic version-one case with genuine source binding."""
    actor = _actor()
    preview = build_producer_desk_preview()
    return open_producer_case(
        actor=actor,
        tenant_id=actor.tenant_id,
        output=preview.output,
        claims=(preview.claim,),
        evidence=preview.evidence,
        accepted_events=preview.events,
    )


def _actor() -> HostVerifiedActor:
    """Construct synthetic test identity, never infer it from caller headers."""
    return HostVerifiedActor(
        subject="ci-atomic-producer",
        tenant_id="ci-atomic-tenant",
        issuer="https://ci-atomic-issuer.example.invalid",
        roles=frozenset({"producer"}),
        permitted_sessions=frozenset({"demo-preview-only"}),
    )


def _conninfo() -> str:
    """Require an ephemeral password and explicit disposable CI execution."""
    if os.environ.get("CI") != "true" or not os.environ.get("PGPASSWORD"):
        raise RuntimeError("Real producer grant qualification is restricted to CI")
    return "host=postgres dbname=matchdesk user=matchdesk_grant_executor_ci sslmode=prefer"


def _writer() -> PostgresProducerGrantWriter:
    """Create a new connection for each atomic grant decision."""
    return PostgresProducerGrantWriter(
        producer_connection_factory(conninfo=_conninfo()),
        expected_role=_ROLE,
    )


def _physical_role() -> None:
    """Independently verify actual login and deny direct DML and membership."""
    with psycopg.connect(_conninfo(), autocommit=True) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT current_user::text, session_user::text")
            assert cursor.fetchone() == (_ROLE, _ROLE)
            cursor.execute(
                "SELECT rolsuper, rolcreaterole, rolcreatedb, rolbypassrls "
                "FROM pg_catalog.pg_roles WHERE rolname=current_user"
            )
            assert cursor.fetchone() == (False, False, False, False)
            for table in (
                "public.matchdesk_producer_cases",
                "public.matchdesk_producer_audit",
                "public.matchdesk_producer_action_grants",
            ):
                cursor.execute(
                    "SELECT has_table_privilege(current_user, %s, "
                    "'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER')",
                    (table,),
                )
                assert cursor.fetchone() == (False,), table
            for statement in (
                "SELECT count(*) FROM public.matchdesk_producer_action_grants",
                "UPDATE public.matchdesk_producer_cases SET generation=999",
                "DELETE FROM public.matchdesk_producer_audit",
            ):
                try:
                    cursor.execute(statement)
                except psycopg.errors.InsufficientPrivilege:
                    pass
                else:
                    raise AssertionError("Restricted login accepted direct grant/table access")
    print("PASS: separate physical login denied direct producer DML and grant reads")


def _invoke(grant: str, command: str) -> bool:
    """Write through the trusted-host adapter, never through the legacy store."""
    return _writer().commit(
        actor=_actor(),
        case=_case(),
        grant_id=grant,
        command_id=command,
        action="create",
        expected_generation=0,
    )


def _direct_sql_tamper(grant: str, *, modify_case: bool = False,
                       modify_audit: bool = False) -> bool:
    """Direct restricted EXECUTE must not bypass the issuer-bound proposal."""
    case = _case()
    payload = json.loads(_case_json(case))
    if modify_case:
        payload["output"]["unauthorized_extra_content"] = "substituted"
    digest = "d" * 64 if modify_audit else _audit_digest(case.review.audit)
    entry = _ENTRY.dump_json(case.review.audit[-1]).decode("utf-8")
    with psycopg.connect(_conninfo()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT public.matchdesk_commit_producer_grant("
                "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb)",
                (
                    grant, _actor().subject, _actor().issuer, case.tenant_id,
                    case.output.session_id, case.output.output_id, "create",
                    "ci-direct-tamper-command-01", 0, None, digest,
                    json.dumps(payload, separators=(",", ":")), entry,
                ),
            )
            result = cursor.fetchone()
            assert result is not None and type(result[0]) is bool
            return result[0]


def main() -> None:
    """Run explicit offline fixture export, first commit, or restart replay."""
    if len(sys.argv) != 2:
        raise RuntimeError("Expected fixture, initial or after-restart phase")
    phase = sys.argv[1]
    case = _case()
    if phase == "fixture":
        # Synthetic source-bound data only. No credentials or grant secrets.
        print(
            json.dumps(
                {
                    "binding": case.output.binding.model_dump(mode="json"),
                    "tenant_id": case.tenant_id,
                    "session_id": case.output.session_id,
                    "output_id": case.output.output_id,
                    "actor_id": _actor().subject,
                    "issuer": _actor().issuer,
                },
                separators=(",", ":"),
            )
        )
        return
    if phase not in ("initial", "after-restart", "elevated"):
        raise RuntimeError("Unknown real grant qualification phase")

    if phase == "elevated":
        # Check the physical principal but deliberately do not run the normal
        # no-DML acceptance helper: this phase intentionally grants extra DML.
        with psycopg.connect(_conninfo(), autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_user::text, session_user::text")
                assert cursor.fetchone() == (_ROLE, _ROLE)
        # The grant itself remains valid. The unexpected unrelated UPDATE
        # permission must be rejected before a database function call.
        try:
            _invoke(_GRANTS["valid"], "ci-elevated-privilege-deny-01")
        except PermissionError as exc:
            assert "pinned restricted login" in str(exc)
        else:
            raise AssertionError("Unexpected DML privilege did not block the writer")
        print("PASS: unrelated application DML privilege blocked atomic grant")
        return
    _physical_role()
    if phase == "initial":
        assert _invoke(_GRANTS["revoked"], "ci-revoked-command-00001") is False
        assert _invoke(_GRANTS["wrong_issuer"], "ci-wrongissuer-command-01") is False
        assert _invoke(_GRANTS["wrong_actor"], "ci-wrongactor-command-001") is False
        assert _direct_sql_tamper(_GRANTS["tampered_case"], modify_case=True) is False
        assert _direct_sql_tamper(_GRANTS["tampered_audit"], modify_audit=True) is False
        assert _invoke(_GRANTS["valid"], "ci-valid-command-0000001") is True
        assert _invoke(_GRANTS["valid"], "ci-replayed-command-00001") is False
        print("PASS: restricted Psycopg create committed once; revoked/issuer/actor/replay denied")
        return

    assert _invoke(_GRANTS["valid"], "ci-restart-replay-00001") is False
    print("MATCHDESK_P4_REAL_GRANT_PSYCOPG_PASS: restarted restricted login rejects replay")


if __name__ == "__main__":
    main()
