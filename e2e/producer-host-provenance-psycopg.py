"""Prove physically isolated PostgreSQL host-confirmation provenance read.

This runs only inside disposable CI after other database/browser gates.
Owner creates synthetic fixture rows; the physical reader can SELECT only two
provenance tables, cannot write, sign, mint grants, or mutate terminal events.
No real Entra user, operator dialog, or production signing key is involved.
"""

from __future__ import annotations

import hashlib
import os
import re
import secrets
from datetime import datetime, timezone

import psycopg
from psycopg import sql

from matchdesk.domain.postgres_host_confirmation_reader import PostgresHostConfirmationReader
from matchdesk.domain.producer_confirmation_provenance import (
    qualify_host_confirmation_record,
)
from matchdesk.domain.producer_grant_preflight import ProducerGrantPreflight

ROLE = "matchdesk_host_confirmation_reader_ci"
TENANT = "ci-provenance-tenant"
CONFIRMATION = secrets.token_hex(16)
EVENT = secrets.token_hex(16)
SIGNED = "ci-disposable-human-envelope-not-real-authentication"
PROOF_HASH = hashlib.sha256(SIGNED.encode()).hexdigest()


def connect(role: str, password: str):
    """Use separate real TCP credentials without SET ROLE or shared sessions."""
    return psycopg.connect(
        host="postgres", dbname="matchdesk", user=role,
        password=password, sslmode="prefer", connect_timeout=10,
    )


def record() -> ProducerGrantPreflight:
    """Create exact synthetic preflight metadata with no issuer authority."""
    return ProducerGrantPreflight(
        confirmation_id=CONFIRMATION,
        actor_id="ci-operator",
        token_issuer="https://ci-issuer.invalid",
        tenant_id=TENANT,
        session_id="ci-session",
        output_id="ci-output",
        action="approve",
        expected_generation=2,
        authorized_case_sha256="a" * 64,
        authorized_audit_digest="b" * 64,
        confirmation_expires_at=int(datetime.now(timezone.utc).timestamp()) + 90,
    )


def main() -> None:
    """Prove SELECT-only logins, append-only state and fail-closed drift."""
    project = os.getenv("COMPOSE_PROJECT_NAME", "")
    owner_password = os.getenv("PGPASSWORD", "")
    reader_password = os.getenv("READER_CI_PASSWORD", "")
    if (
        os.getenv("CI") != "true"
        or re.fullmatch(r"matchdesk-it-[0-9]+-[0-9]+", project) is None
        or len(owner_password) < 16
        or len(reader_password) < 32
        or owner_password == reader_password
    ):
        raise RuntimeError("Provenance qualification requires isolated CI credentials")
    # No production identity is assigned an ingestion privilege: only the
    # disposable owner can construct these test records.
    with connect("matchdesk", owner_password) as conn:
        with conn.cursor() as cur:
            cur.execute("REVOKE TEMP ON DATABASE matchdesk FROM PUBLIC")
            cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            # The final CI storage gate asserts NO public function EXECUTE,
            # including unrelated functions accidentally made callable.
            cur.execute("REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC")
            cur.execute(
                "CREATE ROLE matchdesk_host_confirmation_reader_ci LOGIN "
                "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
            )
            cur.execute(
                sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                    sql.Identifier(ROLE), sql.Literal(reader_password)
                )
            )
            cur.execute(
                sql.SQL("GRANT CONNECT ON DATABASE matchdesk TO {}").format(
                    sql.Identifier(ROLE)
                )
            )
            cur.execute(
                sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                    sql.Identifier(ROLE)
                )
            )
            cur.execute(
                "GRANT SELECT ON public.matchdesk_producer_host_confirmation_events "
                "TO " + ROLE
            )
            cur.execute(
                "GRANT SELECT ON public.matchdesk_producer_host_confirmation_terminals "
                "TO " + ROLE
            )
            cur.execute(
                "INSERT INTO public.matchdesk_producer_host_confirmation_events "
                "(event_id, confirmation_id, tenant_id, actor_id, token_issuer, "
                "session_id, output_id, action, expected_generation, "
                "authorized_case_sha256, authorized_audit_digest, "
                "signed_envelope_sha256, event_channel, confirmed_at, recorded_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
                "clock_timestamp() - interval '5 seconds', clock_timestamp())",
                (
                    EVENT, CONFIRMATION, TENANT, "ci-operator",
                    "https://ci-issuer.invalid", "ci-session", "ci-output",
                    "approve", 2, "a" * 64, "b" * 64, PROOF_HASH,
                    "workforce_authenticated_custom_dialog",
                ),
            )

    def reader_connection():
        """Bind the same independent SCRAM login on every read."""
        return connect(ROLE, reader_password)

    reader = PostgresHostConfirmationReader(
        reader_connection, expected_role=ROLE
    )
    preflight = record()
    proof = reader.read_verified_confirmation(
        confirmation_id=CONFIRMATION, tenant_id=TENANT
    )
    assert proof is not None and proof.state == "confirmed"
    assert proof.event_id == EVENT
    qualify_host_confirmation_record(
        reader=reader, preflight=preflight,
        signed_confirmation=SIGNED, now=datetime.now(timezone.utc),
    )
    assert reader.read_verified_confirmation(
        confirmation_id=CONFIRMATION, tenant_id="other-tenant"
    ) is None
    assert reader.read_verified_confirmation(
        confirmation_id=secrets.token_hex(16), tenant_id=TENANT
    ) is None

    # Role cannot write, grant approvals, bypass revocation or issue grants.
    with connect(ROLE, reader_password) as conn:
        with conn.cursor() as cur:
            for statement in (
                "UPDATE public.matchdesk_producer_host_confirmation_events "
                "SET actor_id='forged' WHERE confirmation_id=%s",
                "INSERT INTO public.matchdesk_producer_host_confirmation_terminals "
                "(event_id, confirmation_id, tenant_id, terminal_state) "
                "VALUES (%s,%s,%s,'revoked')",
            ):
                try:
                    with conn.transaction():
                        cur.execute(
                            statement,
                            (CONFIRMATION,) if statement.startswith("UPDATE")
                            else (secrets.token_hex(16), CONFIRMATION, TENANT),
                        )
                except psycopg.errors.InsufficientPrivilege:
                    pass
                else:
                    raise AssertionError("SELECT-only role performed DML")

    with connect("matchdesk", owner_password) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.matchdesk_producer_host_confirmation_terminals "
                "(event_id, confirmation_id, tenant_id, terminal_state) "
                "VALUES (%s,%s,%s,'revoked')",
                (secrets.token_hex(16), CONFIRMATION, TENANT),
            )
    proof = reader.read_verified_confirmation(
        confirmation_id=CONFIRMATION, tenant_id=TENANT
    )
    assert proof is not None and proof.state == "revoked"
    try:
        qualify_host_confirmation_record(
            reader=reader, preflight=preflight,
            signed_confirmation=SIGNED, now=datetime.now(timezone.utc),
        )
    except PermissionError:
        pass
    else:
        raise AssertionError("Revoked host confirmation passed provenance")
    with connect("matchdesk", owner_password) as conn:
        with conn.cursor() as cur:
            # Adding a single DML right on either provenance table must
            # invalidate the reader's entire runtime role assertion.
            cur.execute(
                "GRANT UPDATE ON public.matchdesk_producer_host_confirmation_events "
                "TO " + ROLE
            )
    try:
        try:
            reader.read_verified_confirmation(
                confirmation_id=CONFIRMATION, tenant_id=TENANT
            )
        except PermissionError:
            pass
        else:
            raise AssertionError("Role with inherited DML passed isolation")
    finally:
        with connect("matchdesk", owner_password) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "REVOKE UPDATE ON public.matchdesk_producer_host_confirmation_events "
                    "FROM " + ROLE
                )
    # Owner itself also cannot rewrite the append-only record.
    with connect("matchdesk", owner_password) as conn:
        with conn.cursor() as cur:
            try:
                with conn.transaction():
                    cur.execute(
                        "UPDATE public.matchdesk_producer_host_confirmation_events "
                        "SET actor_id='replaced' WHERE confirmation_id=%s",
                        (CONFIRMATION,),
                    )
            except psycopg.errors.RaiseException:
                pass
            else:
                raise AssertionError("Immutable host confirmation event was rewritten")
    print(
        "MATCHDESK_P4_REAL_HOST_PROVENANCE_READER_PASS: SELECT-only SCRAM, "
        "tenant scope, terminal revocation, DML drift and immutability"
    )


if __name__ == "__main__":
    main()
