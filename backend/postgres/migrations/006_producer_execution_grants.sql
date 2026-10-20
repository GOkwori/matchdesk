-- DEV/CI-only P3-05 execution-grant schema. Not a live identity bootstrap.
-- Only a separately trusted issuer may insert grants or revoke them.
-- A restricted writer may EXECUTE a fixed SECURITY DEFINER function only,
-- never read or mutate the grant table or control revocation.
BEGIN;
CREATE TABLE IF NOT EXISTS public.matchdesk_producer_execution_grants (
    grant_id uuid PRIMARY KEY,
    tenant_id text NOT NULL CHECK (length(btrim(tenant_id)) BETWEEN 1 AND 96),
    actor_subject text NOT NULL CHECK (length(btrim(actor_subject)) BETWEEN 1 AND 128),
    actor_issuer text NOT NULL CHECK (length(btrim(actor_issuer)) BETWEEN 1 AND 256),
    action text NOT NULL CHECK (action IN ('create', 'edit', 'reverify', 'approve', 'reject')),
    session_id text NOT NULL CHECK (length(btrim(session_id)) BETWEEN 1 AND 96),
    output_id text NOT NULL CHECK (length(btrim(output_id)) BETWEEN 1 AND 96),
    expected_generation bigint NOT NULL CHECK (expected_generation >= 0),
    binding_digest text NOT NULL CHECK (binding_digest ~ '^[a-f0-9]{64}$'),
    issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    consumed_at timestamptz,
    CHECK ((action = 'create') = (expected_generation = 0)),
    CHECK (expires_at > issued_at AND expires_at <= issued_at + interval '5 minutes')
);

-- Never expose grant rows to the ordinary case writer.
REVOKE ALL ON public.matchdesk_producer_execution_grants FROM PUBLIC;

-- CREATE OR REPLACE preserves existing per-role EXECUTE grants on reapplication.
-- Re-create the exact function in the SAME transaction to invalidate every
-- obsolete invoker grant. Dependencies must stop migration, not be cascaded.
DROP FUNCTION IF EXISTS public.matchdesk_consume_producer_execution_grant(
    uuid, text, text, text, text, text, text, bigint, text
);
CREATE FUNCTION public.matchdesk_consume_producer_execution_grant(
    p_id uuid, p_tenant text, p_actor text, p_issuer text, p_action text,
    p_session text, p_output text, p_generation bigint, p_binding text
) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog
AS $mdgrant$
DECLARE claimed boolean;
BEGIN
    -- All tables are schema qualified. Caller values are typed equality
    -- parameters, never SQL fragments or configurable table identifiers.
    UPDATE public.matchdesk_producer_execution_grants
    SET consumed_at = clock_timestamp()
    WHERE grant_id = p_id AND tenant_id = p_tenant
      AND actor_subject = p_actor AND actor_issuer = p_issuer
      AND action = p_action AND session_id = p_session
      AND output_id = p_output AND expected_generation = p_generation
      AND binding_digest = p_binding
      AND revoked_at IS NULL AND consumed_at IS NULL
      AND expires_at > clock_timestamp()
    RETURNING true INTO claimed;
    RETURN COALESCE(claimed, false);
END;
$mdgrant$;

-- PostgreSQL defaults to PUBLIC EXECUTE for new functions. Deny by default.
-- An approved provisioning step must grant EXECUTE only to its exact writer.
REVOKE ALL ON FUNCTION public.matchdesk_consume_producer_execution_grant(
    uuid, text, text, text, text, text, text, bigint, text
) FROM PUBLIC;
COMMIT;
