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
DO $quarantine$
BEGIN
    IF EXISTS (SELECT 1 FROM public.matchdesk_customer_accounts WHERE state = 'active')
       OR EXISTS (SELECT 1 FROM public.matchdesk_customer_sessions WHERE revoked = FALSE)
       OR (SELECT count(*) FROM public.matchdesk_customer_sessions
           WHERE token_hash = repeat('d', 64) AND revoked = TRUE) <> 1 THEN
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
           WHERE subject = 'ci-registered' AND state = 'active') <> 1 THEN
        RAISE EXCEPTION 'ID3H source database changed during restore';
    END IF;
END;
$source_unchanged$;
SQL
echo "MATCHDESK_ID3H_SOURCE_UNCHANGED_PASS"
echo "MATCHDESK_ID3H_DISPOSABLE_RESTORE_PASS"
