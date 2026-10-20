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
from datetime import datetime, timezone

import jwt
import psycopg
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from jwt import PyJWK
from psycopg import sql

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
from matchdesk.domain.producer_preview import build_producer_desk_preview

TENANT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ISSUER = f"https://login.microsoftonline.com/{TENANT}/v2.0"
ACTOR = "ci-signed-bridge-person"
STAGER = "matchdesk_stager_executor_ci"
ISSUER_ROLE = "matchdesk_issuer_executor_ci"
WRITER = "matchdesk_grant_executor_ci"
PASSWORD_ENVS = {
    STAGER: "STAGER_CI_PASSWORD",
    ISSUER_ROLE: "ISSUER_CI_PASSWORD",
    WRITER: "GRANT_WRITER_CI_PASSWORD",
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
    return {
        ("create", 0): created,
        ("reverify", 1): reverified,
        ("approve", 2): approved,
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
                "WHERE confirmation_id=ANY(%s) ORDER BY expected_generation",
                (ids,),
            )
            assert cur.fetchall() == [
                ("create", True, False),
                ("reverify", True, False),
                ("approve", True, False),
            ]


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
        or len(set(passwords.values())) != 3
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
            for role, password in passwords.items():
                cur.execute(
                    sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                        sql.Identifier(role), sql.Literal(password)
                    )
                )
    hashes, envelopes, ids = signed_intents(cases, signer)
    entitlements = Entitlements()
    confirmations = Confirmations(envelopes)

    def physical(role):
        """Return a separately authenticated connection factory."""
        return lambda: db(role, passwords[role])

    bridge = ProducerAtomicGrantBridge(
        policy=ProducerIdentityPolicy(
            issuer=ISSUER, tenant_id=TENANT,
            audience="api://matchdesk-bridge-ci",
            client_ids=frozenset({"matchdesk-bridge-ci"}),
            required_auth_context="c1", max_token_age_seconds=300,
        ),
        keys=keys, entitlements=entitlements,
        confirmations=confirmations,
        confirmation_public_key=signer.public_key(),
        case_hash=Digest(hashes),
        stager_connections=physical(STAGER),
        issuer_connections=physical(ISSUER_ROLE),
        stager_role=STAGER, issuer_role=ISSUER_ROLE,
        writer=PostgresProducerGrantWriter(
            physical(WRITER), expected_role=WRITER,
        ),
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

    for (action, generation), case in cases.items():
        assert bridge.execute(
            access_token=valid, case=case,
            action=action, expected_generation=generation,
        ) is True
    assert bridge.execute(
        access_token=valid, case=create, action="create", expected_generation=0
    ) is False
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
        "JWT/confirmation, three durable generations, replay/CA/drift denied"
    )


if __name__ == "__main__":
    main()
