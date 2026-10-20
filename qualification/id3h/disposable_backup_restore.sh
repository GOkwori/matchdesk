#!/usr/bin/env bash
# Rehearse ID3H recovery only inside this run's disposable CI PostgreSQL.
# Neither dump nor restored database leaves the isolated container. This does
# not qualify a production backup, restore time objective or operator approval.
set -euo pipefail

if [[ "${CI:-}" != "true" || "${GITHUB_ACTIONS:-}" != "true" ||
      ! "${COMPOSE_PROJECT_NAME:-}" =~ ^matchdesk-it-[0-9]+-[0-9]+$ ]]; then
  echo "ID3H restore requires isolated GitHub CI" >&2
  exit 2
fi

clone="matchdesk_id3h_restore_ci"
stale_clone="matchdesk_id3h_stale_ci"
archive="/tmp/matchdesk-id3h-$(openssl rand -hex 12).dump"
created=0
stale_created=0

database() {
  docker compose --project-name "$COMPOSE_PROJECT_NAME" exec -T postgres "$@"
}

cleanup() {
  local status="$?"
  trap - EXIT
  if [[ "$stale_created" == "1" ]] &&
     ! database dropdb -U matchdesk --if-exists --force "$stale_clone"; then
    echo "ID3H stale restored DB cleanup failed" >&2
    status=1
  fi
  if [[ "$created" == "1" ]] &&
     ! database dropdb -U matchdesk --if-exists --force "$clone"; then
    echo "ID3H temporary restored DB cleanup failed" >&2
    status=1
  fi
  if ! database rm -f "$archive"; then
    echo "ID3H temporary backup cleanup failed" >&2
    status=1
  fi
  exit "$status"
}
trap cleanup EXIT

# pg_dump takes a consistent database snapshot. The original must not be
# modified by this rehearsal; roles/ownership must survive the real restore.
database pg_dump -U matchdesk -d matchdesk -Fc -f "$archive"
database test -s "$archive"
echo "MATCHDESK_ID3H_DISPOSABLE_BACKUP_CREATED"

# The clone is a new database in the CI-only cluster; its global roles already
# exist, permitting pg_restore to reproduce SECURITY DEFINER ownership.
database createdb -U matchdesk -T template0 "$clone"
created=1
database pg_restore -U matchdesk --exit-on-error --single-transaction \
  -d "$clone" "$archive"

database psql --no-psqlrc -X -v ON_ERROR_STOP=1 -U matchdesk -d "$clone" <<'SQL'
DO $id3h_restore$
DECLARE
    safe_definers integer;
BEGIN
    -- Require the guarded migration receipt, post-installation live session,
    -- deliberately invalidated legacy bearer and all five enabled triggers.
    IF (SELECT count(*) FROM public.matchdesk_customer_security_migrations) <> 1
       OR (SELECT count(*) FROM public.matchdesk_customer_security_migrations
           WHERE migration_id = 'P3-05-ID3G-005') <> 1
       OR (SELECT count(*) FROM public.matchdesk_customer_sessions
           WHERE token_hash = repeat('d', 64) AND revoked = FALSE) <> 1
       OR (SELECT count(*) FROM public.matchdesk_customer_sessions
           WHERE token_hash = repeat('e', 64) AND revoked = TRUE) <> 1
       OR (SELECT count(*) FROM pg_catalog.pg_trigger
           WHERE tgname IN (
             'matchdesk_customer_identity_immutable',
             'matchdesk_customer_session_immutable',
             'matchdesk_require_active_customer_insert',
             'matchdesk_revoke_sessions_customer_update',
             'matchdesk_revoke_sessions_customer_delete'
           ) AND tgenabled = 'O') <> 5 THEN
        RAISE EXCEPTION 'ID3H restored data, receipt or trigger mismatch';
    END IF;

    SELECT count(*) INTO safe_definers
    FROM pg_catalog.pg_proc AS p
    JOIN pg_catalog.pg_roles AS r ON r.oid = p.proowner
    WHERE p.oid IN (
      'public.matchdesk_require_active_customer_for_insert()'::regprocedure,
      'public.matchdesk_revoke_sessions_for_customer_change()'::regprocedure
    ) AND r.rolname = 'matchdesk_revocation_guard_owner'
      AND NOT r.rolsuper AND NOT r.rolcanlogin AND p.prosecdef;
    IF safe_definers <> 2 OR EXISTS (
        SELECT 1 FROM pg_catalog.pg_proc AS p
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(p.proacl, pg_catalog.acldefault('f', p.proowner))
        ) AS a
        WHERE p.oid IN (
          'public.matchdesk_require_active_customer_for_insert()'::regprocedure,
          'public.matchdesk_revoke_sessions_for_customer_change()'::regprocedure
        ) AND a.grantee = 0 AND a.privilege_type = 'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'ID3H restored security definer privileges unsafe';
    END IF;
END;
$id3h_restore$;
SQL
echo "MATCHDESK_ID3H_RESTORED_RECEIPT_AND_ROLES_PASS"

# Exercise the restored trigger on the clone only: a suspension permanently
# invalidates the newly issued bearer. Never run this DML on the source DB.
database psql --no-psqlrc -X -v ON_ERROR_STOP=1 -U matchdesk -d "$clone" <<'SQL'
DO $clone_revoke$
DECLARE
    updated integer;
BEGIN
    UPDATE public.matchdesk_customer_accounts
       SET state = 'suspended'
     WHERE issuer = 'https://ci.ciamlogin.com/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/v2.0'
       AND tenant_id = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
       AND subject = 'ci-registered'
       AND state = 'active';
    GET DIAGNOSTICS updated = ROW_COUNT;
    IF updated <> 1 OR
       (SELECT count(*) FROM public.matchdesk_customer_sessions
        WHERE token_hash = repeat('d', 64) AND revoked = TRUE) <> 1 THEN
        RAISE EXCEPTION 'ID3H restored clone failed account revocation';
    END IF;
END;
$clone_revoke$;
SQL
echo "MATCHDESK_ID3H_CLONE_REVOCATION_PASS"

# A stale backup contains a bearer that was active at snapshot time but could
# subsequently have been revoked. Restore a SECOND disposable clone to prove
# recovery must quarantine both accounts and session hashes BEFORE reconnecting
# any application to that restored database. No production endpoint is tested.
database createdb -U matchdesk -T template0 "$stale_clone"
stale_created=1
database pg_restore -U matchdesk --exit-on-error --single-transaction \
  -d "$stale_clone" "$archive"
database psql --no-psqlrc -X -v ON_ERROR_STOP=1 -U matchdesk -d "$stale_clone" <<'SQL'
DO $before_quarantine$
BEGIN
    IF (SELECT count(*) FROM public.matchdesk_customer_sessions
        WHERE token_hash = repeat('d', 64) AND revoked = FALSE) <> 1
       OR (SELECT count(*) FROM public.matchdesk_customer_accounts
        WHERE subject = 'ci-registered' AND state = 'active') <> 1 THEN
        RAISE EXCEPTION 'Stale backup did not contain live bearer and account fixture';
    END IF;
END;
$before_quarantine$;

-- Test ONLY real grant rows present in the archived disposable CI snapshot.
-- The owner restores expiry on one otherwise unused old P3 grant inside this
-- clone so a later denial can be attributed to revocation, not elapsed time.
-- A similarly unused P4 grant must exist in the archive; no source DB writes.
DO $producer_snapshot$
BEGIN
    IF to_regclass('public.matchdesk_producer_execution_grants') IS NULL
       OR to_regclass('public.matchdesk_producer_action_grants') IS NULL
       OR to_regclass('public.matchdesk_producer_confirmations') IS NULL
       OR (SELECT count(*) FROM public.matchdesk_producer_execution_grants
           WHERE grant_id = '11111111-1111-4111-8111-111111111104'::uuid
             AND revoked_at IS NULL AND consumed_at IS NULL) <> 1
       OR (SELECT count(*) FROM public.matchdesk_producer_action_grants
           WHERE grant_id = 'ci-wrong-actor-01'
             AND revoked_at IS NULL AND consumed_at IS NULL) <> 1
       -- The source CI suite already uses ffffffff... confirmations. The
       -- distinct restore-only 7777... ID must NOT exist in the snapshot.
       -- Refuse collisions rather than overwriting or skipping test evidence.
       OR EXISTS (
           SELECT 1 FROM public.matchdesk_producer_confirmations
           WHERE confirmation_id = repeat('7',32)
       )
       OR EXISTS (
           SELECT 1 FROM public.matchdesk_producer_action_grants
           WHERE grant_id = 'ci-restore-issue-candidate-00001'
       )
       OR EXISTS (
           SELECT 1 FROM public.matchdesk_producer_host_confirmation_events
           WHERE confirmation_id = repeat('7',32)
              OR event_id = repeat('e',32)
       )
       OR EXISTS (
           SELECT 1 FROM public.matchdesk_producer_host_confirmation_terminals
           WHERE confirmation_id = repeat('7',32)
              OR event_id = pg_catalog.md5(
                 'matchdesk-offline-restore:' || repeat('e',32)
              )
       ) THEN
        RAISE EXCEPTION 'Restored snapshot lacks required producer fixture or test ID is already taken';
    END IF;
END;
$producer_snapshot$;
UPDATE public.matchdesk_producer_execution_grants
   SET issued_at = clock_timestamp(),
       expires_at = clock_timestamp() + interval '120 seconds'
 WHERE grant_id = '11111111-1111-4111-8111-111111111104'::uuid
   AND revoked_at IS NULL AND consumed_at IS NULL;

-- The old snapshot's staging schema must also be quarantined. Stage one
-- deliberately synthetic, valid confirmation IN THE RESTORED CLONE ONLY so
-- the issuer acceptance/denial probes are deterministic despite CI timing.
INSERT INTO public.matchdesk_producer_confirmations
    (confirmation_id, tenant_id, session_id, output_id, actor_id, issuer,
     action, expected_generation, binding, authorized_case_sha256,
     authorized_audit_digest, proof_digest, confirmed_at, expires_at)
VALUES
    (repeat('7', 32), 'ci-restore-tenant', 'ci-restore-session',
     'ci-restore-output', 'ci-restore-operator', 'https://restore-ci.invalid',
     'create', 0, '{}'::jsonb, repeat('a', 64), repeat('b', 64),
     repeat('c', 64), clock_timestamp(), clock_timestamp() + interval '90 seconds');

-- The newer host-provenance store is append-only. Create a synthetic
-- un-terminated event inside this OFFLINE restored clone, never the source.
-- A restored host confirmation is an additional authority dependency and
-- must acquire a terminal 'revoked' record before any provider reconnect.
INSERT INTO public.matchdesk_producer_host_confirmation_events
    (event_id, confirmation_id, tenant_id, actor_id, token_issuer,
     session_id, output_id, action, expected_generation,
     authorized_case_sha256, authorized_audit_digest,
     signed_envelope_sha256, event_channel, confirmed_at, recorded_at)
VALUES
    (repeat('e', 32), repeat('7', 32), 'ci-restore-tenant',
     'ci-restore-operator', 'https://restore-ci.invalid',
     'ci-restore-session', 'ci-restore-output', 'create', 0,
     repeat('a', 64), repeat('b', 64), repeat('c', 64),
     'workforce_authenticated_custom_dialog',
     clock_timestamp() - interval '1 second', clock_timestamp());
DO $host_before_quarantine$
BEGIN
    IF (SELECT count(*) FROM public.matchdesk_producer_host_confirmation_events e
        LEFT JOIN public.matchdesk_producer_host_confirmation_terminals t
          ON t.confirmation_id=e.confirmation_id AND t.tenant_id=e.tenant_id
        WHERE e.event_id=repeat('e',32) AND e.confirmation_id=repeat('7',32)
          AND t.confirmation_id IS NULL) <> 1 THEN
        RAISE EXCEPTION 'Synthetic restored host event is not initially active';
    END IF;
END;
$host_before_quarantine$;

-- Prove these previously granted capabilities really WOULD work absent
-- recovery quarantine, but ROLLBACK both effects. A fake function or expired
-- grant cannot accidentally give us a false-positive recovery certificate.
BEGIN;
DO $producer_pre_quarantine$
DECLARE
    granted boolean;
BEGIN
    SELECT public.matchdesk_consume_producer_execution_grant(
        '11111111-1111-4111-8111-111111111104'::uuid,
        'ci-grant-tenant', 'ci-grant-producer',
        'https://ci.example.invalid/v2.0', 'create',
        'ci-grant-session', 'exact-match', 0, repeat('f', 64)
    ) INTO granted;
    IF granted IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Restored P3 grant not usable before quarantine';
    END IF;

    SELECT public.matchdesk_issue_confirmed_producer_grant(
        repeat('7', 32), 'ci-restore-issue-candidate-00001',
        'ci-restore-tenant', 'ci-restore-session', 'ci-restore-output',
        'ci-restore-operator', 'https://restore-ci.invalid',
        'create', 0, '{}'::jsonb, repeat('a', 64), repeat('b', 64)
    ) INTO granted;
    IF granted IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Restored P4 confirmation not issuable before quarantine';
    END IF;
END;
$producer_pre_quarantine$;
ROLLBACK;

DO $producer_pre_quarantine_reset$
BEGIN
    IF (SELECT count(*) FROM public.matchdesk_producer_execution_grants
         WHERE grant_id = '11111111-1111-4111-8111-111111111104'::uuid
           AND revoked_at IS NULL AND consumed_at IS NULL) <> 1
       OR (SELECT count(*) FROM public.matchdesk_producer_confirmations
           WHERE confirmation_id = repeat('7',32)
             AND revoked_at IS NULL AND consumed_at IS NULL) <> 1
       OR EXISTS (SELECT 1 FROM public.matchdesk_producer_action_grants
           WHERE grant_id = 'ci-restore-issue-candidate-00001') THEN
        RAISE EXCEPTION 'Pre-quarantine rollback left producer authority changed';
    END IF;
END;
$producer_pre_quarantine_reset$;

-- Make the restored identity directory inactive and revoke ALL old bearers in
-- the same commit. No restored approval, broker identity, or raw bearer is
-- promoted to runtime authority by this isolated rehearsal.
BEGIN;
SET LOCAL lock_timeout = '5s';
UPDATE public.matchdesk_customer_accounts
   SET state = 'suspended'
 WHERE state = 'active';
UPDATE public.matchdesk_customer_sessions
   SET revoked = TRUE
 WHERE revoked = FALSE;
-- Invalidate every unspent P3 and P4 producer authorization and all
-- confirmations in this same offline recovery transaction. Nothing here
-- changes source grants, historical audit, or a live operator.
UPDATE public.matchdesk_producer_execution_grants
   SET revoked_at = clock_timestamp()
 WHERE consumed_at IS NULL AND revoked_at IS NULL;
UPDATE public.matchdesk_producer_action_grants
   SET revoked_at = clock_timestamp()
 WHERE consumed_at IS NULL AND revoked_at IS NULL;
UPDATE public.matchdesk_producer_confirmations
   SET revoked_at = clock_timestamp()
 WHERE revoked_at IS NULL;
-- Existing host events are immutable. Append a terminal event for every
-- restored confirmation without one; do NOT rewrite signed provenance.
-- Deterministic synthetic terminal IDs make replay observable. Any collision
-- or failed foreign key aborts the entire recovery transaction.
INSERT INTO public.matchdesk_producer_host_confirmation_terminals
    (event_id, confirmation_id, tenant_id, terminal_state)
SELECT pg_catalog.md5('matchdesk-offline-restore:' || e.event_id),
       e.confirmation_id, e.tenant_id, 'revoked'
FROM public.matchdesk_producer_host_confirmation_events e
WHERE NOT EXISTS (
    SELECT 1 FROM public.matchdesk_producer_host_confirmation_terminals t
    WHERE t.confirmation_id=e.confirmation_id AND t.tenant_id=e.tenant_id
);
DO $quarantine$
BEGIN
    IF EXISTS (SELECT 1 FROM public.matchdesk_customer_accounts WHERE state = 'active')
       OR EXISTS (SELECT 1 FROM public.matchdesk_customer_sessions WHERE revoked = FALSE)
       OR (SELECT count(*) FROM public.matchdesk_customer_sessions
           WHERE token_hash = repeat('d', 64) AND revoked = TRUE) <> 1
       OR EXISTS (SELECT 1 FROM public.matchdesk_producer_execution_grants
                  WHERE consumed_at IS NULL AND revoked_at IS NULL)
       OR EXISTS (SELECT 1 FROM public.matchdesk_producer_action_grants
                  WHERE consumed_at IS NULL AND revoked_at IS NULL)
       OR EXISTS (SELECT 1 FROM public.matchdesk_producer_confirmations
                  WHERE revoked_at IS NULL)
       OR EXISTS (
           SELECT 1 FROM public.matchdesk_producer_host_confirmation_events e
           LEFT JOIN public.matchdesk_producer_host_confirmation_terminals t
             ON t.confirmation_id=e.confirmation_id AND t.tenant_id=e.tenant_id
           WHERE t.confirmation_id IS NULL
       )
       OR (SELECT count(*) FROM public.matchdesk_producer_execution_grants
           WHERE grant_id = '11111111-1111-4111-8111-111111111104'::uuid
             AND revoked_at IS NOT NULL AND consumed_at IS NULL) <> 1
       OR (SELECT count(*) FROM public.matchdesk_producer_action_grants
           WHERE grant_id = 'ci-wrong-actor-01'
             AND revoked_at IS NOT NULL AND consumed_at IS NULL) <> 1 THEN
        RAISE EXCEPTION 'Stale snapshot quarantine failed';
    END IF;
END;
$quarantine$;
COMMIT;
SQL

# An entirely new PostgreSQL transaction must observe the committed quarantine.
# The restored immutable-revocation and active-account triggers must reject an
# attempted bearer revival and new session against the suspended identity.
database psql --no-psqlrc -X -v ON_ERROR_STOP=1 -U matchdesk -d "$stale_clone" <<'SQL'
DO $after_quarantine$
DECLARE
    attempted_at timestamptz := clock_timestamp();
BEGIN
    IF (SELECT count(*) FROM public.matchdesk_customer_security_migrations
         WHERE migration_id = 'P3-05-ID3G-005') <> 1
       OR EXISTS (SELECT 1 FROM public.matchdesk_customer_accounts WHERE state = 'active')
       OR EXISTS (SELECT 1 FROM public.matchdesk_customer_sessions WHERE revoked = FALSE)
       OR (SELECT count(*) FROM public.matchdesk_customer_sessions
           WHERE token_hash = repeat('d', 64) AND revoked = TRUE) <> 1 THEN
        RAISE EXCEPTION 'Stale snapshot quarantine not persisted';
    END IF;

    BEGIN
        UPDATE public.matchdesk_customer_sessions
           SET revoked = FALSE
         WHERE token_hash = repeat('d', 64);
        RAISE EXCEPTION 'Restored revoked bearer unexpectedly reactivated';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL; -- Expected denial from the immutable session trigger.
    END;

    IF EXISTS (SELECT 1 FROM public.matchdesk_customer_sessions
               WHERE token_hash = repeat('f', 64)) THEN
        RAISE EXCEPTION 'Stale fixture bearer collides with an existing session';
    END IF;
    BEGIN
        INSERT INTO public.matchdesk_customer_sessions
            (token_hash, issuer, tenant_id, subject, account_id, realm,
             created_at, expires_at, last_seen_at, revoked)
        SELECT repeat('f', 64), issuer, tenant_id, subject, account_id, 'customer',
               attempted_at, attempted_at + interval '1 hour', attempted_at, FALSE
          FROM public.matchdesk_customer_accounts
         WHERE subject = 'ci-registered'
           AND tenant_id = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
        RAISE EXCEPTION 'Suspended restored identity unexpectedly minted a bearer';
    EXCEPTION WHEN insufficient_privilege THEN
        NULL; -- Expected denial from the active-account insert trigger.
    END;

    IF EXISTS (SELECT 1 FROM public.matchdesk_customer_sessions
               WHERE revoked = FALSE OR token_hash = repeat('f', 64)) THEN
        RAISE EXCEPTION 'Restored bearer survived quarantine denial probes';
    END IF;
END;
$after_quarantine$;
SQL
# A SECOND connection validates commit visibility and tests both independently
# callable producer authorities. They were proven usable BEFORE quarantine;
# neither can now re-consume or mint a revoked restored authorization.
database psql --no-psqlrc -X -v ON_ERROR_STOP=1 -U matchdesk -d "$stale_clone" <<'SQL'
DO $producer_after_quarantine$
DECLARE
    granted boolean;
BEGIN
    IF EXISTS (SELECT 1 FROM public.matchdesk_producer_execution_grants
               WHERE consumed_at IS NULL AND revoked_at IS NULL)
       OR EXISTS (SELECT 1 FROM public.matchdesk_producer_action_grants
                  WHERE consumed_at IS NULL AND revoked_at IS NULL)
       OR EXISTS (SELECT 1 FROM public.matchdesk_producer_confirmations
                  WHERE revoked_at IS NULL)
       OR EXISTS (
           SELECT 1 FROM public.matchdesk_producer_host_confirmation_events e
           LEFT JOIN public.matchdesk_producer_host_confirmation_terminals t
             ON t.confirmation_id=e.confirmation_id AND t.tenant_id=e.tenant_id
           WHERE t.confirmation_id IS NULL
       )
       OR (SELECT count(*) FROM public.matchdesk_producer_host_confirmation_events e
           JOIN public.matchdesk_producer_host_confirmation_terminals t
             ON t.confirmation_id=e.confirmation_id AND t.tenant_id=e.tenant_id
           WHERE e.event_id=repeat('e',32)
             AND e.confirmation_id=repeat('7',32)
             AND t.terminal_state='revoked') <> 1 THEN
        RAISE EXCEPTION 'Restored producer authority survived committed quarantine';
    END IF;

    SELECT public.matchdesk_consume_producer_execution_grant(
        '11111111-1111-4111-8111-111111111104'::uuid,
        'ci-grant-tenant', 'ci-grant-producer',
        'https://ci.example.invalid/v2.0', 'create',
        'ci-grant-session', 'exact-match', 0, repeat('f', 64)
    ) INTO granted;
    IF granted IS DISTINCT FROM FALSE THEN
        RAISE EXCEPTION 'Restored P3 grant was accepted after quarantine';
    END IF;

    SELECT public.matchdesk_issue_confirmed_producer_grant(
        repeat('7', 32), 'ci-restore-issue-candidate-00001',
        'ci-restore-tenant', 'ci-restore-session', 'ci-restore-output',
        'ci-restore-operator', 'https://restore-ci.invalid',
        'create', 0, '{}'::jsonb, repeat('a', 64), repeat('b', 64)
    ) INTO granted;
    IF granted IS DISTINCT FROM FALSE OR EXISTS (
        SELECT 1 FROM public.matchdesk_producer_action_grants
         WHERE grant_id = 'ci-restore-issue-candidate-00001'
    ) THEN
        RAISE EXCEPTION 'Restored P4 confirmation minted a new action grant';
    END IF;
END;
$producer_after_quarantine$;
SQL
echo "MATCHDESK_ID3H_STALE_HOST_PROVENANCE_QUARANTINE_PASS"
echo "MATCHDESK_ID3H_STALE_PRODUCER_AUTHORITY_QUARANTINE_PASS"
echo "MATCHDESK_ID3H_STALE_RESTORE_QUARANTINE_PASS"

# An isolated restore must not have changed the original source database.
database psql --no-psqlrc -X -v ON_ERROR_STOP=1 -U matchdesk -d matchdesk <<'SQL'
DO $source_unchanged$
BEGIN
    IF (SELECT count(*) FROM public.matchdesk_customer_security_migrations
        WHERE migration_id = 'P3-05-ID3G-005') <> 1
       OR (SELECT count(*) FROM public.matchdesk_customer_sessions
           WHERE token_hash = repeat('d', 64) AND revoked = FALSE) <> 1
       OR (SELECT count(*) FROM public.matchdesk_customer_accounts
           WHERE subject = 'ci-registered' AND state = 'active') <> 1
       OR (SELECT count(*) FROM public.matchdesk_producer_execution_grants
           WHERE grant_id = '11111111-1111-4111-8111-111111111104'::uuid
             AND consumed_at IS NULL AND revoked_at IS NULL) <> 1
       OR (SELECT count(*) FROM public.matchdesk_producer_action_grants
           WHERE grant_id = 'ci-wrong-actor-01'
             AND consumed_at IS NULL AND revoked_at IS NULL) <> 1
       OR EXISTS (SELECT 1 FROM public.matchdesk_producer_confirmations
                  WHERE confirmation_id = repeat('7',32))
       OR EXISTS (SELECT 1 FROM public.matchdesk_producer_host_confirmation_events
                  WHERE event_id=repeat('e',32) AND confirmation_id=repeat('7',32)) THEN
        RAISE EXCEPTION 'ID3H source database changed during restore';
    END IF;
END;
$source_unchanged$;
SQL
echo "MATCHDESK_ID3H_SOURCE_UNCHANGED_PASS"
echo "MATCHDESK_ID3H_DISPOSABLE_RESTORE_PASS"
