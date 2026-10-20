"""Unmounted, host-owned signed-confirmation to atomic producer grant bridge.

The bridge has no HTTP entry point, signer, live Entra configuration or
publication authority. It accepts a bearer token only after independent
resource-server verification, obtains signed human intent from a trusted
SERVER source, verifies it, then uses distinct physical PostgreSQL logins to
stage and issue a one-time action grant before the restricted atomic writer.
It never trusts a browser-selected grant ID, a Boolean approval or case DML.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from matchdesk.domain.postgres_producer_grant_writer import PostgresProducerGrantWriter
from matchdesk.domain.postgres_producer_store import DbConnection
from matchdesk.domain.producer_commands import HostVerifiedActor, ProducerCase, _authorize
from matchdesk.domain.producer_grant_preflight import (
    CaseDigestResolver,
    GrantAction,
    qualify_producer_grant_preflight,
)
from matchdesk.domain.producer_identity import (
    EntitlementResolver,
    ProducerIdentityPolicy,
    TrustedKeyResolver,
    verify_producer_access_token,
)

_ROLE = re.compile(r"matchdesk_[a-z][a-z0-9_]{0,54}\Z")
_STAGE_SIG = (
    "public.matchdesk_stage_producer_confirmation("
    "text,text,text,text,text,text,text,bigint,jsonb,text,text,text,timestamptz)"
)
_ISSUE_SIG = (
    "public.matchdesk_issue_confirmed_producer_grant("
    "text,text,text,text,text,text,text,text,bigint,jsonb,text,text)"
)
# This query executes on the SAME database connection and inside the SAME
# transaction as the host's fixed stage or issuance function. Every PostgreSQL
# privilege check uses effective privileges (including PUBLIC) rather than
# trusting role names, session-supplied settings or a request-supplied claim.
_PINNED_ISSUER_QUERY = """
SELECT current_user::text, session_user::text,
       (
         r.rolcanlogin
         AND NOT (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole
                  OR r.rolreplication OR r.rolbypassrls)
         AND NOT EXISTS (
             SELECT 1 FROM pg_catalog.pg_auth_members m WHERE m.member = r.oid
         )
         AND NOT pg_catalog.has_database_privilege(current_database(), 'CREATE, TEMP')
         AND NOT EXISTS (
             SELECT 1 FROM pg_catalog.pg_namespace ns
             WHERE ns.nspname !~ '^pg_' AND ns.nspname <> 'information_schema'
               AND pg_catalog.has_schema_privilege(ns.oid, 'CREATE')
         )
         AND NOT EXISTS (
             SELECT 1 FROM pg_catalog.pg_class c
             JOIN pg_catalog.pg_namespace ns ON ns.oid = c.relnamespace
             WHERE ns.nspname !~ '^pg_' AND ns.nspname <> 'information_schema'
               AND CASE WHEN c.relkind IN ('r', 'p', 'v', 'm', 'f') THEN
                   pg_catalog.has_table_privilege(
                       c.oid, 'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER'
                   )
                   OR pg_catalog.has_any_column_privilege(
                       c.oid, 'SELECT, INSERT, UPDATE, REFERENCES'
                   )
                   ELSE FALSE
               END
         )
         AND NOT EXISTS (
             SELECT 1 FROM pg_catalog.pg_class c
             JOIN pg_catalog.pg_namespace ns ON ns.oid = c.relnamespace
             WHERE ns.nspname !~ '^pg_' AND ns.nspname <> 'information_schema'
               AND CASE WHEN c.relkind = 'S' THEN
                   pg_catalog.has_sequence_privilege(c.oid, 'USAGE, UPDATE')
                   ELSE FALSE
               END
         )
         -- No stage/issue/revoke/commit/legacy grant function may coexist on
         -- a single login. Prevent a privileged issuer calling the writer or
         -- issuing without the independently validated confirmation.
         AND NOT EXISTS (
             SELECT 1 FROM pg_catalog.pg_proc p
             JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
             WHERE n.nspname = 'public'
               AND p.proname IN (
                   'matchdesk_stage_producer_confirmation',
                   'matchdesk_issue_confirmed_producer_grant',
                   'matchdesk_revoke_confirmed_producer_grant',
                   'matchdesk_commit_producer_grant',
                   'matchdesk_consume_producer_execution_grant'
               )
               AND p.oid <> pg_catalog.to_regprocedure(%s)
               AND pg_catalog.has_function_privilege(p.oid, 'EXECUTE')
         )
         AND pg_catalog.has_function_privilege(
             pg_catalog.to_regprocedure(%s), 'EXECUTE'
         )
       )
FROM pg_catalog.pg_roles r WHERE r.rolname = current_user
"""
_STAGE = """
SELECT public.matchdesk_stage_producer_confirmation(
    %s, %s, %s, %s, %s, %s, %s, %s,
    %s::jsonb, %s, %s, %s, %s::timestamptz
)
"""
_ISSUE = """
SELECT public.matchdesk_issue_confirmed_producer_grant(
    %s, %s, %s, %s, %s, %s, %s, %s,
    %s, %s::jsonb, %s, %s
)
"""


class ConfirmedIntentSource(Protocol):
    """Trusted server-side source of an existing signed custom-dialog decision.

    The source must independently associate the exact actor/case/action with
    the operator's genuine custom confirmation. It must never echo a browser
    supplied approval flag, signature, role or arbitrary confirmation blob.
    """

    def resolve_signed_confirmation(
        self,
        *,
        actor: HostVerifiedActor,
        case: ProducerCase,
        action: GrantAction,
        expected_generation: int,
    ) -> str | None:
        """Return only a host-held signed confirmation or None to deny."""


class ProducerAtomicGrantBridge:
    """Compose signed-intent preflight, two physical issuer roles and atomic CAS.

    Construction only defines an unmounted capability. A real host must still
    qualify Entra tenant Conditional Access/MFA, trusted confirmation signing,
    independent role provisioning, revocation and manual DEV operator UAT.
    """

    def __init__(
        self,
        *,
        policy: ProducerIdentityPolicy,
        keys: TrustedKeyResolver,
        entitlements: EntitlementResolver,
        confirmations: ConfirmedIntentSource,
        confirmation_public_key: Ed25519PublicKey,
        case_hash: CaseDigestResolver,
        stager_connections: Callable[[], DbConnection],
        issuer_connections: Callable[[], DbConnection],
        stager_role: str,
        issuer_role: str,
        writer: PostgresProducerGrantWriter,
    ) -> None:
        """Require explicit host-owned dependencies and separate issuer identities."""
        if (
            type(policy) is not ProducerIdentityPolicy
            or policy.required_auth_context is None
            or policy.max_token_age_seconds > 300
            or not isinstance(confirmation_public_key, Ed25519PublicKey)
            or not _ROLE.fullmatch(stager_role)
            or not _ROLE.fullmatch(issuer_role)
            or stager_role == issuer_role
            or not callable(getattr(keys, "resolve", None))
            or not callable(getattr(entitlements, "resolve", None))
            or not callable(getattr(confirmations, "resolve_signed_confirmation", None))
            or not callable(getattr(case_hash, "digest_case_jsonb", None))
            or not callable(stager_connections)
            or not callable(issuer_connections)
            or type(writer) is not PostgresProducerGrantWriter
        ):
            raise ValueError("Atomic producer bridge requires independent trusted host authorities")
        policy.__post_init__()
        self._policy = policy
        self._keys = keys
        self._entitlements = entitlements
        self._confirmations = confirmations
        self._confirmation_public_key = confirmation_public_key
        self._case_hash = case_hash
        self._stager_connections = stager_connections
        self._issuer_connections = issuer_connections
        self._stager_role = stager_role
        self._issuer_role = issuer_role
        self._writer = writer

    @staticmethod
    def _invoke(
        connections: Callable[[], DbConnection],
        *,
        role: str,
        signature: str,
        statement: str,
        parameters: tuple[object, ...],
    ) -> bool:
        """Check one real PostgreSQL role and invoke only its fixed function.

        Unknown outcomes are NOT silently retried. A failed role check never
        reaches staging or issuance, even if the caller holds a valid token.
        """
        connection = connections()
        try:
            with connection.transaction():
                with connection.cursor() as cursor:
                    cursor.execute("SET LOCAL statement_timeout = '15000ms'", ())
                    cursor.execute("SET LOCAL search_path TO pg_catalog, public", ())
                    cursor.execute(_PINNED_ISSUER_QUERY, (signature, signature))
                    observed = cursor.fetchone()
                    if (
                        observed is None
                        or len(observed) != 3
                        or observed[0] != role
                        or observed[1] != role
                        or observed[2] is not True
                    ):
                        raise PermissionError("Producer grant requires an isolated issuer login")
                    cursor.execute(statement, parameters)
                    result = cursor.fetchone()
                    if result is None or len(result) != 1 or type(result[0]) is not bool:
                        raise RuntimeError("Producer grant returned an unknown database receipt")
                    return result[0]
        finally:
            connection.close()

    def execute(
        self,
        *,
        access_token: str,
        case: ProducerCase,
        action: GrantAction,
        expected_generation: int,
    ) -> bool:
        """Authorize and commit one exact case without any legacy write fallback.

        All credentials, signing keys and database connections are host-owned.
        A False receipt means no approval, and every database exception is
        UNRECONCILED until an independent audit readback; never blind-retry it.
        """
        now = datetime.now(timezone.utc)
        try:
            if type(access_token) is not str or not access_token:
                raise PermissionError("Missing delegated workforce identity")
            actor = verify_producer_access_token(
                access_token,
                policy=self._policy,
                keys=self._keys,
                entitlements=self._entitlements,
                now=now,
            )
            if type(actor) is not HostVerifiedActor:
                raise PermissionError("Host actor is not independently verified")
            _authorize(actor, case.tenant_id, case.output.session_id)
            signed = self._confirmations.resolve_signed_confirmation(
                actor=actor,
                case=case,
                action=action,
                expected_generation=expected_generation,
            )
            if type(signed) is not str or not signed:
                raise PermissionError("No server-held human confirmation")
            preflight = qualify_producer_grant_preflight(
                access_token=access_token,
                policy=self._policy,
                keys=self._keys,
                entitlements=self._entitlements,
                case=case,
                action=action,
                expected_generation=expected_generation,
                signed_confirmation=signed,
                confirmation_public_key=self._confirmation_public_key,
                case_hash=self._case_hash,
                now=now,
            )
            if (
                preflight.actor_id != actor.subject
                or preflight.token_issuer != actor.issuer
                or preflight.tenant_id != actor.tenant_id
                or preflight.session_id != case.output.session_id
                or preflight.output_id != case.output.output_id
                or preflight.action != action
                or preflight.expected_generation != expected_generation
            ):
                raise PermissionError("Confirmation scope differs from verified actor")
        except (PermissionError, LookupError, ValueError, TypeError):
            raise PermissionError("Producer execution denied") from None
        except Exception:
            raise RuntimeError("Producer identity/confirmation unavailable") from None

        # Database IDs are generated only after signature and step-up preflight.
        # Neither ID can be selected or observed by the browser.
        grant_id = secrets.token_urlsafe(32)
        command_id = secrets.token_urlsafe(32)
        binding = case.output.binding.model_dump_json()
        stage = (
            preflight.confirmation_id,
            preflight.tenant_id,
            preflight.session_id,
            preflight.output_id,
            preflight.actor_id,
            preflight.token_issuer,
            preflight.action,
            preflight.expected_generation,
            binding,
            preflight.authorized_case_sha256,
            preflight.authorized_audit_digest,
            hashlib.sha256(signed.encode("utf-8")).hexdigest(),
            datetime.fromtimestamp(preflight.confirmation_expires_at, timezone.utc),
        )
        issue = (
            preflight.confirmation_id,
            grant_id,
            preflight.tenant_id,
            preflight.session_id,
            preflight.output_id,
            preflight.actor_id,
            preflight.token_issuer,
            preflight.action,
            preflight.expected_generation,
            binding,
            preflight.authorized_case_sha256,
            preflight.authorized_audit_digest,
        )
        try:
            if not self._invoke(
                self._stager_connections,
                role=self._stager_role,
                signature=_STAGE_SIG,
                statement=_STAGE,
                parameters=stage,
            ):
                return False
            if not self._invoke(
                self._issuer_connections,
                role=self._issuer_role,
                signature=_ISSUE_SIG,
                statement=_ISSUE,
                parameters=issue,
            ):
                return False
            result = self._writer.commit(
                actor=actor,
                case=case,
                grant_id=grant_id,
                command_id=command_id,
                action=action,
                expected_generation=expected_generation,
            )
            if type(result) is not bool:
                raise RuntimeError("Atomic writer returned an invalid receipt")
            return result
        except PermissionError:
            raise PermissionError("Producer database authority denied") from None
        except Exception:
            raise RuntimeError(
                "Producer grant outcome is unreconciled; no automatic retry"
            ) from None
