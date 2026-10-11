-- ID3H legacy-installation catalog review, not a migration or authorization.
-- Run as a SELECT/metadata-only transaction against an operator-approved copy.
-- This cannot prove historical migration execution or substitute for evidence
-- of the exact 005 SHA, backup/restore rehearsal and explicit release approval.
BEGIN TRANSACTION READ ONLY;
SET LOCAL lock_timeout = '5s';

DO $legacy$
DECLARE
    owner_role oid;
    matched integer;
BEGIN
    IF current_setting('transaction_read_only') <> 'on' THEN
        RAISE EXCEPTION 'ID3H legacy preflight must be read-only'
            USING ERRCODE = '42501';
    END IF;
    IF to_regclass('public.matchdesk_customer_security_migrations') IS NOT NULL THEN
        RAISE EXCEPTION 'ID3H legacy preflight expects no existing receipt ledger'
            USING ERRCODE = '55000';
    END IF;
    -- Inspect catalog object identities, not merely matching names or comments.
    -- A missing/disabled/column-specific trigger must fail the acceptance gate.
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
    SELECT count(*) INTO matched
    FROM expected AS e
    JOIN pg_catalog.pg_trigger AS t
      ON t.tgrelid = e.relation_oid AND t.tgname = e.trigger_name
     AND t.tgfoid = e.function_oid AND t.tgtype = e.trigger_type
    WHERE NOT t.tgisinternal
      AND t.tgenabled = 'O'
      AND position('UPDATE OF' IN pg_catalog.pg_get_triggerdef(t.oid)) = 0;
    IF matched <> 5 THEN
        RAISE EXCEPTION 'ID3H legacy catalog trigger fingerprint failed'
            USING ERRCODE = '55000';
    END IF;

    SELECT oid INTO owner_role
    FROM pg_catalog.pg_roles
    WHERE rolname = 'matchdesk_revocation_guard_owner'
      AND NOT rolsuper AND NOT rolcanlogin AND NOT rolcreaterole
      AND NOT rolcreatedb AND NOT rolreplication AND NOT rolbypassrls
      AND NOT rolinherit;
    IF owner_role IS NULL OR EXISTS (
        SELECT 1 FROM pg_catalog.pg_auth_members
        WHERE roleid = owner_role OR member = owner_role
    ) THEN
        RAISE EXCEPTION 'ID3H legacy definer role is unsafe'
            USING ERRCODE = '42501';
    END IF;
    SELECT count(*) INTO matched
    FROM pg_catalog.pg_proc AS p
    WHERE p.oid IN (
       'public.matchdesk_require_active_customer_for_insert()'::regprocedure,
       'public.matchdesk_revoke_sessions_for_customer_change()'::regprocedure
    ) AND p.proowner = owner_role
      AND p.prosecdef
      AND 'search_path=pg_catalog' = ANY(p.proconfig);
    IF matched <> 2 THEN
        RAISE EXCEPTION 'ID3H legacy definer ownership mismatch'
            USING ERRCODE = '42501';
    END IF;
    -- PUBLIC EXECUTE would make a definer callable directly from an untrusted
    -- client rather than only through the row triggers.
    IF EXISTS (
        SELECT 1
        FROM pg_catalog.pg_proc AS p
        CROSS JOIN LATERAL pg_catalog.aclexplode(
            COALESCE(p.proacl, pg_catalog.acldefault('f', p.proowner))
        ) AS permission
        WHERE p.oid IN (
          'public.matchdesk_require_active_customer_for_insert()'::regprocedure,
          'public.matchdesk_revoke_sessions_for_customer_change()'::regprocedure
        ) AND permission.grantee = 0 AND permission.privilege_type = 'EXECUTE'
    ) THEN
        RAISE EXCEPTION 'ID3H legacy PUBLIC definer execution grant detected'
            USING ERRCODE = '42501';
    END IF;
    IF pg_catalog.has_table_privilege(
        'matchdesk_revocation_guard_owner',
        'public.matchdesk_producer_cases',
        'SELECT'
    ) THEN
        RAISE EXCEPTION 'ID3H legacy definer role can read producer cases'
            USING ERRCODE = '42501';
    END IF;
END;
$legacy$;

-- Non-sensitive fingerprints for independent review. These alone do not
-- attest to the historical backfill or permit setting a migration receipt.
SELECT p.proname AS protected_function,
       pg_catalog.md5(pg_catalog.pg_get_functiondef(p.oid)) AS catalog_md5
FROM pg_catalog.pg_proc AS p
WHERE p.oid IN (
    'public.matchdesk_block_customer_identity_rewrite()'::regprocedure,
    'public.matchdesk_block_customer_session_rewrite()'::regprocedure,
    'public.matchdesk_require_active_customer_for_insert()'::regprocedure,
    'public.matchdesk_revoke_sessions_for_customer_change()'::regprocedure
)
ORDER BY p.proname;

SELECT COUNT(*) FILTER (WHERE revoked = FALSE) AS active_sessions,
       COUNT(*) FILTER (WHERE revoked = TRUE) AS revoked_sessions
FROM public.matchdesk_customer_sessions;
COMMIT;
