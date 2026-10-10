-- MATCHDESK P3-05-ID3G -- REVIEW-ONLY CANDIDATE, NOT AN APPROVED MIGRATION.
-- Requires 002_customer_sessions.sql and 004_customer_accounts.sql.
-- Test on disposable PostgreSQL before placing it in backend/postgres/migrations/.
-- No new identity providers, cloud resources, or runtime role permissions.
-- An operator must review account-state authority, table ownership, lock order,
-- rollout downtime, archival/restoration, and incident recovery before adoption.
BEGIN;
SET LOCAL lock_timeout = '5s';

-- The official disposable image initialises POSTGRES_USER as a SUPERUSER.
-- A SECURITY DEFINER routine must NOT inherit that full authority. A
-- dedicated NOLOGIN/NOSUPERUSER owner receives only the exact DML privileges
-- needed by the two reviewed trigger bodies. Reject an unsafe existing role.
DO $owner$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname = 'matchdesk_revocation_guard_owner'
    ) THEN
        CREATE ROLE matchdesk_revocation_guard_owner
            NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOINHERIT NOREPLICATION NOBYPASSRLS;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
        WHERE rolname = 'matchdesk_revocation_guard_owner'
          AND NOT rolsuper AND NOT rolcanlogin AND NOT rolcreaterole
          AND NOT rolcreatedb AND NOT rolreplication AND NOT rolbypassrls
    ) THEN
        RAISE EXCEPTION 'Customer revocation trigger owner is privileged'
            USING ERRCODE = '42501';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_auth_members m
        JOIN pg_catalog.pg_roles r ON r.oid = m.roleid
        WHERE r.rolname = 'matchdesk_revocation_guard_owner'
    ) THEN
        RAISE EXCEPTION 'Customer revocation trigger owner has role members'
            USING ERRCODE = '42501';
    END IF;
END;
$owner$;
GRANT USAGE ON SCHEMA public TO matchdesk_revocation_guard_owner;
GRANT SELECT ON public.matchdesk_customer_accounts
    TO matchdesk_revocation_guard_owner;
-- PostgreSQL FOR SHARE additionally requires UPDATE on at least one column.
-- This capability stays on the non-login, no-member trigger owner only.
GRANT UPDATE (state) ON public.matchdesk_customer_accounts
    TO matchdesk_revocation_guard_owner;
GRANT SELECT ON public.matchdesk_customer_sessions
    TO matchdesk_revocation_guard_owner;
GRANT UPDATE (revoked) ON public.matchdesk_customer_sessions
    TO matchdesk_revocation_guard_owner;

-- Broker identity must be immutable. A change is delete/insert with governed
-- verification rather than silent account linking or changing a trusted key.
CREATE OR REPLACE FUNCTION public.matchdesk_block_customer_identity_rewrite()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $md$
BEGIN
    IF ROW(OLD.issuer, OLD.tenant_id, OLD.subject)
       IS DISTINCT FROM ROW(NEW.issuer, NEW.tenant_id, NEW.subject) THEN
        RAISE EXCEPTION 'Customer broker identity cannot be rewritten'
            USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END;
$md$;
REVOKE ALL ON FUNCTION public.matchdesk_block_customer_identity_rewrite()
    FROM PUBLIC;
DROP TRIGGER IF EXISTS matchdesk_customer_identity_immutable
    ON public.matchdesk_customer_accounts;
CREATE TRIGGER matchdesk_customer_identity_immutable
BEFORE UPDATE ON public.matchdesk_customer_accounts
FOR EACH ROW EXECUTE FUNCTION public.matchdesk_block_customer_identity_rewrite();

-- The session's bearer digest, identity and expiry never change. In particular,
-- a server-side revocation cannot be undone even if an operator reactivates the
-- account or a compromised runtime DB credential attempts direct SQL updates.
CREATE OR REPLACE FUNCTION public.matchdesk_block_customer_session_rewrite()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $md$
BEGIN
    IF OLD.revoked IS TRUE AND NEW.revoked IS DISTINCT FROM TRUE THEN
        RAISE EXCEPTION 'Revoked customer sessions cannot be restored'
            USING ERRCODE = '42501';
    END IF;
    IF ROW(NEW.token_hash, NEW.issuer, NEW.tenant_id, NEW.subject,
           NEW.account_id, NEW.realm, NEW.created_at, NEW.expires_at)
       IS DISTINCT FROM
       ROW(OLD.token_hash, OLD.issuer, OLD.tenant_id, OLD.subject,
           OLD.account_id, OLD.realm, OLD.created_at, OLD.expires_at) THEN
        RAISE EXCEPTION 'Customer session ownership and lifetime are immutable'
            USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END;
$md$;
REVOKE ALL ON FUNCTION public.matchdesk_block_customer_session_rewrite()
    FROM PUBLIC;
DROP TRIGGER IF EXISTS matchdesk_customer_session_immutable
    ON public.matchdesk_customer_sessions;
CREATE TRIGGER matchdesk_customer_session_immutable
BEFORE UPDATE ON public.matchdesk_customer_sessions
FOR EACH ROW EXECUTE FUNCTION public.matchdesk_block_customer_session_rewrite();

-- A session insert holds a share lock on the exact ACTIVE account row until
-- its transaction commits. This conflicts with account state updates. If the
-- suspension wins, the insert is denied. If the insert wins, the suspension
-- waits and the account-change trigger revokes the newly committed session.
-- Credential theft of the session writer remains a separate threat: this
-- trigger does NOT replace the broker-token or host-action authorization.
CREATE OR REPLACE FUNCTION public.matchdesk_require_active_customer_for_insert()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $md$
DECLARE
    active_account text;
BEGIN
    IF NEW.realm IS DISTINCT FROM 'customer'
       OR NEW.revoked IS DISTINCT FROM FALSE THEN
        RAISE EXCEPTION 'Customer session insertion denied'
            USING ERRCODE = '42501';
    END IF;

    SELECT a.account_id INTO active_account
    FROM public.matchdesk_customer_accounts AS a
    WHERE a.issuer = NEW.issuer
      AND a.tenant_id = NEW.tenant_id
      AND a.subject = NEW.subject
      AND a.state = 'active'
    FOR SHARE;

    IF active_account IS NULL OR active_account <> NEW.account_id THEN
        RAISE EXCEPTION 'Customer session account is not active'
            USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END;
$md$;
REVOKE ALL ON FUNCTION public.matchdesk_require_active_customer_for_insert()
    FROM PUBLIC;
DROP TRIGGER IF EXISTS matchdesk_require_active_customer_insert
    ON public.matchdesk_customer_sessions;
CREATE TRIGGER matchdesk_require_active_customer_insert
BEFORE INSERT ON public.matchdesk_customer_sessions
FOR EACH ROW EXECUTE FUNCTION public.matchdesk_require_active_customer_for_insert();

-- Account suspension, account-ID changes and deletion permanently revoke all
-- previously issued sessions for the OLD broker identity. The transition and
-- revocation share one transaction. For an UPDATE the row lock also prevents
-- concurrent post-change inserts from succeeding on stale account status.
CREATE OR REPLACE FUNCTION public.matchdesk_revoke_sessions_for_customer_change()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $md$
BEGIN
    IF TG_OP = 'DELETE' OR (
        TG_OP = 'UPDATE'
        AND ROW(OLD.state, OLD.account_id)
            IS DISTINCT FROM ROW(NEW.state, NEW.account_id)
    ) THEN
        UPDATE public.matchdesk_customer_sessions AS s
        SET revoked = TRUE
        WHERE s.issuer = OLD.issuer
          AND s.tenant_id = OLD.tenant_id
          AND s.subject = OLD.subject
          AND s.revoked = FALSE;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$md$;
REVOKE ALL ON FUNCTION public.matchdesk_revoke_sessions_for_customer_change()
    FROM PUBLIC;
-- Use an unqualified AFTER UPDATE trigger: PostgreSQL column-specific
-- UPDATE OF triggers do not fire when a BEFORE UPDATE trigger changes state
-- while the original UPDATE targets another column. The body compares OLD
-- and NEW state/account_id, so unrelated changes never revoke sessions.
DROP TRIGGER IF EXISTS matchdesk_revoke_sessions_customer_update
    ON public.matchdesk_customer_accounts;
CREATE TRIGGER matchdesk_revoke_sessions_customer_update
AFTER UPDATE ON public.matchdesk_customer_accounts
FOR EACH ROW EXECUTE FUNCTION public.matchdesk_revoke_sessions_for_customer_change();
DROP TRIGGER IF EXISTS matchdesk_revoke_sessions_customer_delete
    ON public.matchdesk_customer_accounts;
CREATE TRIGGER matchdesk_revoke_sessions_customer_delete
AFTER DELETE ON public.matchdesk_customer_accounts
FOR EACH ROW EXECUTE FUNCTION public.matchdesk_revoke_sessions_for_customer_change();

-- The migration is executed by the disposable bootstrap superuser. Transfer
-- ONLY the two SECURITY DEFINER functions to a tightly permissioned NOLOGIN
-- role so neither trigger executes with PostgreSQL superuser authority.
-- Re-applying the migration must preserve these exact owners.
ALTER FUNCTION public.matchdesk_require_active_customer_for_insert()
    OWNER TO matchdesk_revocation_guard_owner;
ALTER FUNCTION public.matchdesk_revoke_sessions_for_customer_change()
    OWNER TO matchdesk_revocation_guard_owner;

-- Migration-time safety: *all* pre-trigger sessions must be revoked. An
-- active account snapshot cannot prove the account was never previously
-- suspended/reactivated, so a conditional inactive-only backfill would allow
-- old revoked-in-spirit bearers to resurrect after this migration. No old
-- cookie or CSRF proof is grandfathered across this security boundary.
-- This is intentionally disruptive if applied after live launch: owner review,
-- bulk-row plan, and customer reauthentication comms must precede rollout.
UPDATE public.matchdesk_customer_sessions
SET revoked = TRUE
WHERE revoked = FALSE;
COMMIT;
