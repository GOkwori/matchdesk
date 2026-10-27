#!/usr/bin/env bash
# ID3H: prove legacy receipt reconciliation only on a disposable CI database clone.
# This cannot attest to a production historical migration, and must never be
# reused as a live migration runner or substituted for signed operator evidence.
set -euo pipefail

if [[ "${CI:-}" != "true" || "${GITHUB_ACTIONS:-}" != "true" ||
      ! "${COMPOSE_PROJECT_NAME:-}" =~ ^matchdesk-it-[0-9]+-[0-9]+$ ]]; then
  echo "ID3H legacy reconciliation is disposable GitHub CI only" >&2
  exit 2
fi
# The preceding CI step executed this exact baseline SQL in disposable DB.
# A catalog match alone NEVER proves a live historical backfill occurred.
migration=backend/postgres/migrations/005_customer_account_revocation.sql
test "$(git hash-object "$migration")" = 78c2403f528f42492472b921ef221ec3187cebde
test "$(git hash-object qualification/id3h/legacy_catalog_preflight_REVIEW_ONLY.sql)" = 6240a844c80c662a8303211d41dac4cec585255a
test "$(git hash-object qualification/id3h/005_customer_account_revocation_once_REVIEW_ONLY.sql)" = 52e2f4c4730fc2ae12f8bae180a895f193d59784

clone=matchdesk_id3h_legacy_reconciliation_ci
archive="/tmp/matchdesk-id3h-legacy-$(openssl rand -hex 12).dump"
created=0
database() {
  docker compose --project-name "$COMPOSE_PROJECT_NAME" exec -T postgres "$@"
}
cleanup() {
  local status="$?"
  trap - EXIT
  if [[ "$created" == "1" ]] &&
     ! database dropdb -U matchdesk --if-exists --force "$clone"; then
    echo "ID3H legacy clone cleanup failed" >&2
    status=1
  fi
  if ! database rm -f "$archive"; then
    echo "ID3H legacy backup cleanup failed" >&2
    status=1
  fi
  exit "$status"
}
trap cleanup EXIT

# The clone models a legacy installation with revocation triggers but NO
# version receipt. Provenance is known here because CI itself ran migration 005.
database pg_dump -U matchdesk -d matchdesk -Fc -f "$archive"
database test -s "$archive"
database createdb -U matchdesk -T template0 "$clone"
created=1
database pg_restore -U matchdesk --exit-on-error --single-transaction -d "$clone" "$archive"
database psql --no-psqlrc -X -v ON_ERROR_STOP=1 -U matchdesk -d "$clone" \
  < qualification/id3h/legacy_catalog_preflight_REVIEW_ONLY.sql >/dev/null
echo "MATCHDESK_ID3H_RECONCILIATION_LEGACY_CLONE_PASS"

# Synthetic bearer created AFTER legacy 005, simulating an active login.
database psql --no-psqlrc -X -v ON_ERROR_STOP=1 -U matchdesk -d "$clone" <<'SQL'
INSERT INTO public.matchdesk_customer_sessions
  (token_hash, issuer, tenant_id, subject, account_id, realm,
   created_at, expires_at, last_seen_at, revoked)
VALUES
  (repeat('b', 64),
   'https://ci.ciamlogin.com/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/v2.0',
   'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee', 'ci-registered', 'ci-1',
   'customer', now(), now() + interval '1 hour', now(), FALSE);
SQL

# Receipt-only adoption is a PROOF OF MECHANICS, not an approved migration.
# Lock session and account writes; verify the legacy database objects again
# in the same transaction before recording a one-time receipt.
database psql --no-psqlrc -X -v ON_ERROR_STOP=1 -U matchdesk -d "$clone" <<'SQL'
BEGIN;
SET LOCAL lock_timeout = '5s';
LOCK TABLE public.matchdesk_customer_accounts,
           public.matchdesk_customer_sessions IN SHARE MODE;
DO $validate$
DECLARE
    matches integer;
BEGIN
    IF to_regclass('public.matchdesk_customer_security_migrations') IS NOT NULL THEN
        RAISE EXCEPTION 'ID3H clone unexpectedly already has a receipt ledger';
    END IF;
    WITH expected(relation_oid, trigger_name, function_oid, trigger_type) AS (
        VALUES
          ('public.matchdesk_customer_accounts'::regclass,
           'matchdesk_customer_identity_immutable',
           'public.matchdesk_block_customer_identity_rewrite()'::regprocedure, 19),
          ('public.matchdesk_customer_sessions'::regclass,
           'matchdesk_customer_session_immutable',
           'public.matchdesk_block_customer_session_rewrite()'::regprocedure, 19),
          ('public.matchdesk_customer_sessions'::regclass,
           'matchdesk_require_active_customer_insert',
           'public.matchdesk_require_active_customer_for_insert()'::regprocedure, 7),
          ('public.matchdesk_customer_accounts'::regclass,
           'matchdesk_revoke_sessions_customer_update',
           'public.matchdesk_revoke_sessions_for_customer_change()'::regprocedure, 17),
          ('public.matchdesk_customer_accounts'::regclass,
           'matchdesk_revoke_sessions_customer_delete',
           'public.matchdesk_revoke_sessions_for_customer_change()'::regprocedure, 9)
    )
    SELECT count(*) INTO matches
    FROM expected AS e
    JOIN pg_catalog.pg_trigger AS t
      ON t.tgrelid = e.relation_oid AND t.tgname = e.trigger_name
     AND t.tgfoid = e.function_oid AND t.tgtype = e.trigger_type
    WHERE NOT t.tgisinternal AND t.tgenabled = 'O'
      AND position('UPDATE OF' IN pg_catalog.pg_get_triggerdef(t.oid)) = 0;
    IF matches <> 5 THEN
        RAISE EXCEPTION 'ID3H clone catalog changed during reconciliation';
    END IF;
    IF (SELECT count(*) FROM public.matchdesk_customer_sessions
        WHERE token_hash = repeat('b', 64) AND revoked = FALSE) <> 1 THEN
        RAISE EXCEPTION 'ID3H clone active session absent';
    END IF;
END;
$validate$;
CREATE TABLE public.matchdesk_customer_security_migrations (
    migration_id text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
REVOKE ALL ON TABLE public.matchdesk_customer_security_migrations FROM PUBLIC;
INSERT INTO public.matchdesk_customer_security_migrations (migration_id)
VALUES ('P3-05-ID3G-005');
COMMIT;
SQL

# The guarded candidate must refuse without ever revoking the post-install
# bearer. Failure must have the expected ID3H reason, not an unrelated fault.
if database psql --no-psqlrc -X -v ON_ERROR_STOP=1 -U matchdesk -d "$clone" \
     < qualification/id3h/005_customer_account_revocation_once_REVIEW_ONLY.sql \
       > artifacts/integration/id3h-legacy-reconcile-replay.log 2>&1; then
  echo "ID3H ERROR: clone replay unexpectedly applied" >&2
  exit 1
fi
grep -F 'Customer revocation migration already applied' \
  artifacts/integration/id3h-legacy-reconcile-replay.log >/dev/null

database psql --no-psqlrc -X -v ON_ERROR_STOP=1 -U matchdesk -d "$clone" <<'SQL'
DO $assert$
BEGIN
    IF (SELECT count(*) FROM public.matchdesk_customer_security_migrations
        WHERE migration_id = 'P3-05-ID3G-005') <> 1
       OR (SELECT count(*) FROM public.matchdesk_customer_sessions
           WHERE token_hash = repeat('b', 64) AND revoked = FALSE) <> 1 THEN
        RAISE EXCEPTION 'ID3H clone receipt or customer session changed';
    END IF;
END;
$assert$;
SQL
# The disposable SOURCE remains legacy: never record a receipt on it.
database psql --no-psqlrc -X -v ON_ERROR_STOP=1 -U matchdesk -d matchdesk <<'SQL'
DO $unchanged$
BEGIN
    IF to_regclass('public.matchdesk_customer_security_migrations') IS NOT NULL
       OR (SELECT count(*) FROM public.matchdesk_customer_sessions
           WHERE token_hash = repeat('b', 64)) <> 0 THEN
        RAISE EXCEPTION 'ID3H source database was modified during clone rehearsal';
    END IF;
END;
$unchanged$;
SQL
echo "MATCHDESK_ID3H_LEGACY_RECEIPT_CLONE_PASS"
