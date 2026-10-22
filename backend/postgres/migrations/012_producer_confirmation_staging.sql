-- Candidate resource boundary only. Unmounted and default-denied.
-- A separately authenticated host MUST independently verify the signed human
-- confirmation, current workforce actor/tenant/session authorization, Entra
-- Conditional Access and exact canonical case/audit hashes before calling.
-- A staging SQL row and proof hash are NOT proof of human approval or MFA.
BEGIN;
DROP FUNCTION IF EXISTS public.matchdesk_stage_producer_confirmation(
    text,text,text,text,text,text,text,bigint,jsonb,text,text,text,timestamptz
);
CREATE FUNCTION public.matchdesk_stage_producer_confirmation(
    p_confirmation_id text,
    p_tenant_id text,
    p_session_id text,
    p_output_id text,
    p_actor_id text,
    p_issuer text,
    p_action text,
    p_generation bigint,
    p_binding jsonb,
    p_case_hash text,
    p_audit_hash text,
    p_proof_hash text,
    p_expires_at timestamptz
) RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $stage$
DECLARE
    staged_id text;
    -- Avoid SQL's CURRENT_TIME keyword (timetz); use a named timestamptz.
    v_checked_at timestamptz := clock_timestamp();
BEGIN
    -- Validate every caller-supplied dimension. No stored row is considered
    -- authoritative unless host-side verification also succeeded.
    IF p_confirmation_id IS NULL
       OR p_confirmation_id !~ '^[a-f0-9]{32}$'
       OR p_tenant_id IS NULL OR length(p_tenant_id) NOT BETWEEN 1 AND 96
       OR p_session_id IS NULL OR length(p_session_id) NOT BETWEEN 1 AND 96
       OR p_output_id IS NULL OR length(p_output_id) NOT BETWEEN 1 AND 96
       OR p_actor_id IS NULL OR length(p_actor_id) NOT BETWEEN 1 AND 256
       OR p_issuer IS NULL OR length(p_issuer) NOT BETWEEN 1 AND 512
       OR p_action IS NULL
       OR p_action NOT IN ('create','edit','reverify','approve','reject')
       OR p_generation IS NULL OR p_generation < 0
       OR (p_generation = 0) IS DISTINCT FROM (p_action = 'create')
       OR p_binding IS NULL OR jsonb_typeof(p_binding) <> 'object'
       OR p_case_hash IS NULL OR p_case_hash !~ '^[a-f0-9]{64}$'
       OR p_audit_hash IS NULL OR p_audit_hash !~ '^[a-f0-9]{64}$'
       OR p_proof_hash IS NULL OR p_proof_hash !~ '^[a-f0-9]{64}$'
       OR p_expires_at IS NULL OR p_expires_at <= v_checked_at
       OR p_expires_at > v_checked_at + interval '120 seconds'
    THEN
        RETURN FALSE;
    END IF;

    INSERT INTO public.matchdesk_producer_confirmations
      (confirmation_id, tenant_id, session_id, output_id, actor_id,
       issuer, action, expected_generation, binding,
       authorized_case_sha256, authorized_audit_digest, proof_digest,
       confirmed_at, expires_at)
    VALUES
      (p_confirmation_id, p_tenant_id, p_session_id, p_output_id,
       p_actor_id, p_issuer, p_action, p_generation, p_binding,
       p_case_hash, p_audit_hash, p_proof_hash, v_checked_at, p_expires_at)
    ON CONFLICT (confirmation_id) DO NOTHING
    RETURNING confirmation_id INTO staged_id;
    RETURN staged_id IS NOT NULL;
END;
$stage$;
REVOKE ALL ON FUNCTION public.matchdesk_stage_producer_confirmation(
    text,text,text,text,text,text,text,bigint,jsonb,text,text,text,timestamptz
) FROM PUBLIC;
COMMIT;
