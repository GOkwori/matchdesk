"""CI-only physically authenticated signed producer bridge qualification.

Synthetic RSA/Ed25519 material is created in memory. This is not evidence
of a real operator's confirmation, live Conditional Access or production access.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier

import jwt
import psycopg
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from jwt import PyJWK
from psycopg import sql

from matchdesk.domain.postgres_host_confirmation_reader import PostgresHostConfirmationReader
from matchdesk.domain.postgres_producer_grant_writer import PostgresProducerGrantWriter
from matchdesk.domain.postgres_producer_store import _audit_digest, _case_json
from matchdesk.domain.producer_atomic_grant_bridge import (
    ProducerAtomicGrantBridge,
    _ISSUE_SIG,
)
from matchdesk.domain.producer_commands import (
    HostVerifiedActor,
    apply_producer_command,
    open_producer_case,
)
from matchdesk.domain.producer_identity import ProducerIdentityPolicy, StaticTrustedKeys
from matchdesk.domain.producer_policy_assurance import ProducerPolicyEvidence
from matchdesk.domain.producer_preview import build_producer_desk_preview

TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ISSUER = f"https://login.microsoftonline.com/{TENANT}/v2.0"
ACTOR = "ci-signed-bridge-person"
STAGER = "matchdesk_stager_executor_ci"
ISSUER_ROLE = "matchdesk_issuer_executor_ci"
WRITER = "matchdesk_grant_executor_ci"
REVOKER = "matchdesk_revoker_executor_ci"
PROVENANCE_READER = "matchdesk_bridge_provenance_reader_ci"
PASSWORD_ENVS = {
    STAGER: "STAGER_CI_PASSWORD",
    ISSUER_ROLE: "ISSUER_CI_PASSWORD",
    WRITER: "GRANT_WRITER_CI_PASSWORD",
    REVOKER: "REVOKER_CI_PASSWORD",
    PROVENANCE_READER: "BRIDGE_READER_CI_PASSWORD",
}


def db(role: str, password: str):
    """Open one real SCRAM/TCP login; never impersonate through SET ROLE."""
    return psycopg.connect(
        host="postgres", dbname="matchdesk", user=role,
        password=password, sslmode="prefer", connect_timeout=10,
    )


def owner():
    """Reserve owner access for fixture setup and independent audit readback."""
    return db("matchdesk", os.environ["PGPASSWORD"])


class Entitlements:
    """Synthetic server-side session entitlement, with revocation control."""

    def __init__(self):
        """Initialize allowed only for the fixed CI producer."""
        self.allowed = True

    def resolve(self, *, tenant_id, subject):
        """Return roles and sessions only when current host grants allow them."""
        if self.allowed and (tenant_id, subject) == (TENANT, ACTOR):
            return frozenset({"producer"}), frozenset({"demo-preview-only"})
        return None


class PolicyAssurance:
    """Synthetic CI policy proof, never an authoritative Entra CA query."""

    def __init__(self):
        """Initialize an explicitly revocable CI-only assurance fixture."""
        self.allowed = True
        self.calls = 0

    def assess(self, *, tenant_id, subject, session_id, context_id, client_ids):
        """Generate scope-bound policy evidence for the offline CI actor only."""
        self.calls += 1
        if not self.allowed or (tenant_id, subject) != (TENANT, ACTOR):
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
            verified_at_seconds=int(datetime.now(timezone.utc).timestamp()),
        )


class Digest:
    """Restrict signing to source-pinned PostgreSQL-normalized JSONB hashes."""

    def __init__(self, records):
        """Load only hashes independently computed by disposable PostgreSQL."""
        self.records = records

    def digest_case_jsonb(self, case_json):
        """Deny unknown JSON rather than replacing canonical hashing."""
        return self.records[case_json]


class Confirmations:
    """Host-held signed synthetic intents, keyed by action and generation."""

    def __init__(self, records):
        """Retain signed case snapshots outside browser-controlled inputs."""
        self.records = records
        self.calls = 0

    def resolve_signed_confirmation(
        self, *, actor, case, action, expected_generation
    ):
        """Return one signed envelope only for the matching verified actor."""
        self.calls += 1
        entry = self.records.get((action, expected_generation))
        if actor.subject != ACTOR or entry is None or case != entry[0]:
            return None
        return entry[1]


def rsa_keys():
    """Produce a short-lived JWT key pair and issuer-pinned JWK."""
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    n = private.public_key().public_numbers()

    def enc(value):
        """Convert one unsigned RSA integer to JWK base64url."""
        data = value.to_bytes((value.bit_length() + 7) // 8, "big")
        return jwt.utils.base64url_encode(data).decode()

    public = PyJWK.from_dict({
        "kty": "RSA", "alg": "RS256", "use": "sig", "kid": "bridge-ci",
        "n": enc(n.n), "e": enc(n.e),
    })
    return private, StaticTrustedKeys(ISSUER, {"bridge-ci": public})


def token(private, *, step_up):
    """Sign a synthetic delegated access token with optional c1 context."""
    now = int(datetime.now(timezone.utc).timestamp())
    claims = {
        "iss": ISSUER, "aud": "api://matchdesk-bridge-ci", "tid": TENANT,
        "sub": ACTOR, "azp": "matchdesk-bridge-ci",
        "scp": "MatchDesk.Producer.Access",
        "acrs": ["c1"] if step_up else [],
        "iat": now - 3, "nbf": now - 3, "exp": now + 180,
    }
    return jwt.encode(
        claims, private, algorithm="RS256", headers={"kid": "bridge-ci"}
    )


def states(actor):
    """Generate domain-approved create, reverify and approve transitions."""
    preview = build_producer_desk_preview()
    created = open_producer_case(
        actor=actor, tenant_id=TENANT, output=preview.output,
        claims=(preview.claim,), evidence=preview.evidence,
        accepted_events=preview.events,
    )
    reverified = apply_producer_command(
        created, actor=actor, expected_generation=1,
        command="reverify", reason="CI synthetic evidence check",
    )
    approved = apply_producer_command(
        reverified, actor=actor, expected_generation=2,
        command="approve", reason="CI synthetic human signature",
    )
    rejected = apply_producer_command(
        reverified, actor=actor, expected_generation=2,
        command="reject", reason="CI revocation must block rejection mutation",
    )
    return {
        ("create", 0): created,
        ("reverify", 1): reverified,
        ("approve", 2): approved,
        ("reject", 2): rejected,
    }


def signed_intents(candidates, signer):
    """Create Ed25519 confirmations against actual PostgreSQL JSONB hashes."""
    hashed = {}
    signed = {}
    ids = []
    with owner() as conn:
        with conn.cursor() as cur:
            for (action, generation), case in candidates.items():
                body = _case_json(case)
                cur.execute(
                    "SELECT encode(sha256(convert_to(%s::jsonb::text,'UTF8')),'hex')",
                    (body,),
                )
                digest = cur.fetchone()[0]
                hashed[body] = digest
                confirmation_id = secrets.token_hex(16)
                ids.append(confirmation_id)
                now = int(datetime.now(timezone.utc).timestamp())
                claims = {
                    "version": 1,
                    "issuer": "matchdesk-trusted-producer-confirmation-v1",
                    "audience": "matchdesk-producer-grant-issuer",
                    "confirmation_id": confirmation_id,
                    "confirmation_method": "custom-dialog-execution",
                    "actor_id": ACTOR,
                    "token_issuer": ISSUER,
                    "tenant_id": TENANT,
                    "session_id": case.output.session_id,
                    "output_id": case.output.output_id,
                    "action": action,
                    "expected_generation": generation,
                    "authorized_case_sha256": digest,
                    "authorized_audit_digest": _audit_digest(case.review.audit),
                    "issued_at": now - 2,
                    "not_before": now - 1,
                    "expires_at": now + 80,
                }
                canonical = json.dumps(
                    claims, ensure_ascii=True, sort_keys=True,
                    separators=(",", ":"),
                ).encode()
                signature = signer.sign(canonical)
                envelope = json.dumps({
                    "claims": claims,
                    "signature": base64.urlsafe_b64encode(signature).decode().rstrip("="),
                })
                signed[(action, generation)] = (case, envelope)
    return hashed, signed, ids


def reconcile(approved, ids):
    """Compare exact durable producer/audit/grant rows under owner-only readback."""
    with owner() as conn:
        with conn.cursor() as cur:
            scope = (TENANT, approved.output.session_id, approved.output.output_id)
            cur.execute(
                "SELECT generation,case_json,audit_digest "
                "FROM public.matchdesk_producer_cases "
                "WHERE tenant_id=%s AND session_id=%s AND output_id=%s",
                scope,
            )
            row = cur.fetchone()
            assert row is not None and row[0] == 3
            assert row[1] == json.loads(_case_json(approved))
            assert row[2] == _audit_digest(approved.review.audit)
            cur.execute(
                "SELECT generation,entry_json,audit_digest "
                "FROM public.matchdesk_producer_audit "
                "WHERE tenant_id=%s AND session_id=%s AND output_id=%s "
                "ORDER BY generation",
                scope,
            )
            entries = cur.fetchall()
            assert len(entries) == 3
            assert [r[1]["action"] for r in entries] == [
                "review_started", "reverified", "approved",
            ]
            assert [r[2] for r in entries] == [
                _audit_digest(approved.review.audit[:i]) for i in (1, 2, 3)
            ]
            cur.execute(
                "SELECT action,consumed_at IS NOT NULL,revoked_at IS NOT NULL "
                "FROM public.matchdesk_producer_action_grants "
                "WHERE confirmation_id=ANY(%s) ORDER BY expected_generation, action",
                (ids,),
            )
            assert cur.fetchall() == [
                ("create", True, False),
                ("reverify", True, False),
                ("approve", True, False),
                ("reject", False, True),
            ]
            cur.execute(
                "SELECT consumed_at IS NOT NULL, revoked_at IS NOT NULL, "
                "issued_grant_id IS NOT NULL "
                "FROM public.matchdesk_producer_confirmations "
                "WHERE confirmation_id=%s",
                (ids[-1],),
            )
            assert cur.fetchone() == (True, True, True)


def main():
    """Qualify SQL role isolation and signed 3-stage operation in one CI DB."""
    passwords = {
        role: os.getenv(key, "") for role, key in PASSWORD_ENVS.items()
    }
    if (
        os.getenv("CI") != "true"
        or re.fullmatch(
            r"matchdesk-it-[0-9]+-[0-9]+", os.getenv("COMPOSE_PROJECT_NAME", "")
        ) is None
        or len(os.getenv("PGPASSWORD", "")) < 16
        or any(len(value) < 32 for value in passwords.values())
        or len(set(passwords.values())) != 5
    ):
        raise RuntimeError("Only disposable CI with distinct masked credentials is allowed")
    actor = HostVerifiedActor(
        subject=ACTOR, tenant_id=TENANT, issuer=ISSUER,
        roles=frozenset({"producer"}),
        permitted_sessions=frozenset({"demo-preview-only"}),
    )
    cases = states(actor)
    signer = ed25519.Ed25519PrivateKey.generate()
    rsa_private, keys = rsa_keys()
    with owner() as conn:
        with conn.cursor() as cur:
            # Runtime confirmation provenance uses a FIFTH physically distinct
            # SCRAM login. No model, token or browser may supply this identity.
            cur.execute(
                "CREATE ROLE matchdesk_bridge_provenance_reader_ci LOGIN "
                "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
            )
            cur.execute("REVOKE TEMP ON DATABASE matchdesk FROM PUBLIC")
            cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            cur.execute("REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC")
            cur.execute(
                "GRANT CONNECT ON DATABASE matchdesk "
                "TO matchdesk_bridge_provenance_reader_ci"
            )
            cur.execute(
                "GRANT USAGE ON SCHEMA public TO matchdesk_bridge_provenance_reader_ci"
            )
            cur.execute(
                "GRANT SELECT ON public.matchdesk_producer_host_confirmation_events "
                "TO matchdesk_bridge_provenance_reader_ci"
            )
            cur.execute(
                "GRANT SELECT ON public.matchdesk_producer_host_confirmation_terminals "
                "TO matchdesk_bridge_provenance_reader_ci"
            )
            for role, password in passwords.items():
                cur.execute(
                    sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                        sql.Identifier(role), sql.Literal(password)
                    )
                )
    hashes, envelopes, ids = signed_intents(cases, signer)
    # Only the CI database owner can seed synthetic custom-dialog records.
    # The producer bridge receives no INSERT role or public confirmation API.
    with owner() as conn:
        with conn.cursor() as cur:
            for (action, generation), (_, envelope) in envelopes.items():
                claims = json.loads(envelope)["claims"]
                confirmation_id = claims["confirmation_id"]
                cur.execute(
                    "INSERT INTO public.matchdesk_producer_host_confirmation_events "
                    "(event_id, confirmation_id, tenant_id, actor_id, token_issuer, "
                    "session_id, output_id, action, expected_generation, "
                    "authorized_case_sha256, authorized_audit_digest, "
                    "signed_envelope_sha256, event_channel, confirmed_at, recorded_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
                    "clock_timestamp() - interval '2 seconds', clock_timestamp())",
                    (
                        hashlib.sha256(confirmation_id.encode()).hexdigest()[:32],
                        confirmation_id, TENANT, ACTOR, ISSUER,
                        claims["session_id"], claims["output_id"],
                        action, generation,
                        claims["authorized_case_sha256"],
                        claims["authorized_audit_digest"],
                        hashlib.sha256(envelope.encode()).hexdigest(),
                        "workforce_authenticated_custom_dialog",
                    ),
                )
    entitlements = Entitlements()
    assurance = PolicyAssurance()
    confirmations = Confirmations(envelopes)

    def physical(role):
        """Return a separately authenticated connection factory."""
        return lambda: db(role, passwords[role])

    writer = PostgresProducerGrantWriter(
        physical(WRITER), expected_role=WRITER,
    )
    provenance = PostgresHostConfirmationReader(
        physical(PROVENANCE_READER), expected_role=PROVENANCE_READER,
    )
    # Independently assert that the same isolated reader used by the bridge
    # cannot read a valid confirmation under a different tenant.
    assert provenance.read_verified_confirmation(
        confirmation_id=ids[0], tenant_id="other-tenant"
    ) is None
    assert provenance.read_verified_confirmation(
        confirmation_id=ids[0], tenant_id=TENANT
    ) is not None
    bridge = ProducerAtomicGrantBridge(
        policy=ProducerIdentityPolicy(
            issuer=ISSUER, tenant_id=TENANT,
            audience="api://matchdesk-bridge-ci",
            client_ids=frozenset({"matchdesk-bridge-ci"}),
            required_auth_context="c1", max_token_age_seconds=300,
        ),
        keys=keys, entitlements=entitlements,
        policy_assurance=assurance,
        confirmations=confirmations,
        provenance=provenance,
        confirmation_public_key=signer.public_key(),
        case_hash=Digest(hashes),
        stager_connections=physical(STAGER),
        issuer_connections=physical(ISSUER_ROLE),
        stager_role=STAGER, issuer_role=ISSUER_ROLE,
        writer=writer,
    )
    valid = token(rsa_private, step_up=True)
    create = cases[("create", 0)]
    try:
        bridge.execute(
            access_token=token(rsa_private, step_up=False),
            case=create, action="create", expected_generation=0,
        )
    except PermissionError:
        pass
    else:
        raise AssertionError("Missing Entra authentication context was accepted")
    assert confirmations.calls == 0

    assurance.allowed = False
    try:
        bridge.execute(
            access_token=valid, case=create, action="create", expected_generation=0
        )
    except PermissionError:
        pass
    else:
        raise AssertionError("Unenforced host CA policy was allowed")
    assert confirmations.calls == 0
    assurance.allowed = True

    # Before staging, make the physical stager incorrectly inherit issuer
    # execution. The bridge MUST reject role drift; restore immediately.
    with owner() as conn:
        with conn.cursor() as cur:
            cur.execute("GRANT EXECUTE ON FUNCTION " + _ISSUE_SIG + " TO " + STAGER)
    try:
        try:
            bridge.execute(
                access_token=valid, case=create,
                action="create", expected_generation=0,
            )
        except PermissionError:
            pass
        else:
            raise AssertionError("Cross-authorized stager bypassed role isolation")
    finally:
        with owner() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "REVOKE EXECUTE ON FUNCTION " + _ISSUE_SIG + " FROM " + STAGER
                )

    # Simulate an acknowledgement disappearing AFTER the actual writer
    # committed; the bridge must return UNRECONCILED, never success or retry.
    # Owner-only readback then proves exactly one durable create grant/audit.
    durable_commit = writer.commit
    dropped_acknowledgements = []

    def drop_create_ack(**kwargs):
        """Drop only the initial post-commit acknowledgement in synthetic CI."""
        receipt = durable_commit(**kwargs)
        if kwargs["action"] == "create" and receipt is True:
            dropped_acknowledgements.append(kwargs["command_id"])
            raise ConnectionError("CI simulated lost acknowledgement after commit")
        return receipt

    # Observe only Boolean stage/issue receipts in CI; never log signed
    # envelopes, grant IDs, actor identifiers or SQL parameters.
    original_invoke = bridge._invoke
    create_boundary_receipts = []

    def observe_create_boundary(connections, *, role, signature, statement, parameters):
        """Retain non-sensitive stage/issue outcome for denied CI paths."""
        receipt = original_invoke(
            connections, role=role, signature=signature,
            statement=statement, parameters=parameters,
        )
        if parameters[6 if role == STAGER else 7] == "create":
            stage_name = "stage" if role == STAGER else "issue"
            create_boundary_receipts.append((stage_name, receipt))
        return receipt

    bridge._invoke = observe_create_boundary
    writer.commit = drop_create_ack
    try:
        try:
            bridge.execute(
                access_token=valid, case=create, action="create",
                expected_generation=0,
            )
        except RuntimeError as exc:
            assert "unreconciled" in str(exc) and "simulated" not in str(exc)
        else:
            raise AssertionError("Lost commit acknowledgement was treated as success")
    finally:
        writer.commit = durable_commit
        bridge._invoke = original_invoke
    assert len(dropped_acknowledgements) == 1, (
        "CI create declined before durable writer acknowledgement: "
        + repr(create_boundary_receipts)
    )
    with owner() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT generation, case_json FROM public.matchdesk_producer_cases "
                "WHERE tenant_id=%s AND session_id=%s AND output_id=%s",
                (TENANT, create.output.session_id, create.output.output_id),
            )
            assert cur.fetchone() == (1, json.loads(_case_json(create)))
            cur.execute(
                "SELECT consumed_at IS NOT NULL, revoked_at IS NOT NULL "
                "FROM public.matchdesk_producer_action_grants "
                "WHERE confirmation_id=%s",
                (ids[0],),
            )
            assert cur.fetchone() == (True, False)
    # No blind resend may perform another create after an unknown outcome.
    assert bridge.execute(
        access_token=valid, case=create, action="create",
        expected_generation=0,
    ) is False
    assert bridge.execute(
        access_token=valid, case=cases[("reverify", 1)],
        action="reverify", expected_generation=1,
    ) is True

    # Revocation after issuance but before the atomic writer must invalidate
    # the action grant without appending the rejected case or audit event.
    revoked_calls = []

    def revoke_before_reject(**kwargs):
        """Revoke via the independent SCRAM revoker before writer execution."""
        if kwargs["action"] == "reject":
            with db(REVOKER, passwords[REVOKER]) as connection:
                with connection.cursor() as cur:
                    cur.execute(
                        "SELECT current_user::text, session_user::text, "
                        "has_function_privilege(current_user,"
                        "'public.matchdesk_revoke_confirmed_producer_grant(text)',"
                        "'EXECUTE'),"
                        "has_table_privilege(current_user,"
                        "'public.matchdesk_producer_action_grants','UPDATE')"
                    )
                    assert cur.fetchone() == (REVOKER, REVOKER, True, False)
                    cur.execute(
                        "SELECT public.matchdesk_revoke_confirmed_producer_grant(%s)",
                        (ids[-1],),
                    )
                    assert cur.fetchone() == (True,)
            revoked_calls.append(True)
        return durable_commit(**kwargs)

    writer.commit = revoke_before_reject
    try:
        assert bridge.execute(
            access_token=valid, case=cases[("reject", 2)],
            action="reject", expected_generation=2,
        ) is False
    finally:
        writer.commit = durable_commit
    assert revoked_calls == [True]
    with owner() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT generation, case_json #>> '{review,status}' "
                "FROM public.matchdesk_producer_cases "
                "WHERE tenant_id=%s AND session_id=%s AND output_id=%s",
                (TENANT, create.output.session_id, create.output.output_id),
            )
            assert cur.fetchone() == (2, "ready_for_decision")
            cur.execute(
                "SELECT revoked_at IS NOT NULL, consumed_at IS NOT NULL "
                "FROM public.matchdesk_producer_action_grants "
                "WHERE confirmation_id=%s",
                (ids[-1],),
            )
            assert cur.fetchone() == (True, False)

    # Two physically independent staged-issuer-writer attempts contend for
    # the SAME signed approval confirmation and proposed case generation.
    # One and only one may consume it; the loser cannot append another audit.
    start = Barrier(2)

    def competing_approval(_index):
        """Race one caller against the same immutable signed approval."""
        start.wait(timeout=15)
        return bridge.execute(
            access_token=valid, case=cases[("approve", 2)],
            action="approve", expected_generation=2,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        contenders = [executor.submit(competing_approval, index) for index in (0, 1)]
        receipts = [future.result(timeout=35) for future in contenders]
    assert sorted(receipts) == [False, True], receipts

    # The already-consumed confirmation must still reject an entirely new
    # host-created attempt: no idempotency confusion or second approval.
    assert bridge.execute(
        access_token=valid, case=cases[("approve", 2)],
        action="approve", expected_generation=2,
    ) is False
    assert bridge.execute(
        access_token=valid, case=create, action="create", expected_generation=0
    ) is False
    # A host revocation written to PostgreSQL after an approval does not
    # rewrite previously committed history. It MUST deny a later attempt
    # before staging even if the same Ed25519 envelope still verifies.
    with owner() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.matchdesk_producer_host_confirmation_terminals "
                "(event_id, confirmation_id, tenant_id, terminal_state) "
                "VALUES (%s,%s,%s,'revoked')",
                (secrets.token_hex(16), ids[2], TENANT),
            )
    try:
        bridge.execute(
            access_token=valid, case=cases[("approve", 2)],
            action="approve", expected_generation=2,
        )
    except PermissionError:
        pass
    else:
        raise AssertionError("Revoked physical confirmation provenance was accepted")
    entitlements.allowed = False
    try:
        bridge.execute(
            access_token=valid, case=cases[("approve", 2)],
            action="approve", expected_generation=2,
        )
    except PermissionError:
        pass
    else:
        raise AssertionError("Revoked host session grant was accepted")
    reconcile(cases[("approve", 2)], ids)
    print(
        "MATCHDESK_P4_REAL_BRIDGE_PASS: separate SCRAM roles, signed synthetic "
        "JWT/confirmation, three durable generations, lost-ACK reconciliation, "
        "revoked pre-write grant denied, physical host-event revoke enforced, "
        "one-winner approve race, replay/CA/drift denied"
    )


if __name__ == "__main__":
    main()
