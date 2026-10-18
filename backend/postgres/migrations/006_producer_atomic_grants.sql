-- P4 candidate: isolated, default-unused, atomic producer action-grant writer.
-- Never apply to a live database without independent DBA review and approval.
-- Existing P3 case writer is unchanged and does NOT enforce these grants.
BEGIN;

CREATE TABLE IF NOT EXISTS public.matchdesk_producer_action_grants (
    grant_id text PRIMARY KEY CHECK (grant_id ~ '^[A-Za-z0-9_-]{16,128}$'),
    tenant_id text NOT NULL CHECK (length(tenant_id) BETWEEN 1 AND 96),
    session_id text NOT NULL CHECK (length(session_id) BETWEEN 1 AND 96),
    output_id text NOT NULL CHECK (length(output_id) BETWEEN 1 AND 96),
    actor_id text NOT NULL CHECK (length(actor_id) BETWEEN 1 AND 256),
    issuer text NOT NULL CHECK (length(issuer) BETWEEN 1 AND 512),
    action text NOT NULL CHECK (action IN ('create', 'edit', 'reverify', 'approve', 'reject')),
    binding jsonb NOT NULL CHECK (jsonb_typeof(binding) = 'object'),
    expected_generation bigint NOT NULL CHECK (expected_generation >= 0),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    consumed_at timestamptz,
    command_id text UNIQUE,
    CHECK ((consumed_at IS NULL) = (command_id IS NULL))
);

-- Grant issuance, expiry, revocation and key provenance belong to a separate
-- trusted authority. No browser-facing or generic application role is granted
-- access to create, read, update, delete or consume grants by this migration.
REVOKE ALL ON TABLE public.matchdesk_producer_action_grants FROM PUBLIC;

-- The only proposed write entry is a tightly constrained SECURITY DEFINER
-- operation. Every identifier is fully qualified and all inputs are values;
-- search_path never resolves application-controlled names.
CREATE OR REPLACE FUNCTION public.matchdesk_commit_producer_grant(
    p_grant_id text,
    p_actor_id text,
    p_tenant_id text,
    p_session_id text,
    p_output_id text,
    p_action text,
    p_command_id text,
    p_expected_generation bigint,
    p_prior_audit_digest text,
    p_next_audit_digest text,
    p_case_json jsonb,
    p_audit_entry jsonb
) RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $function$
DECLARE
    g public.matchdesk_producer_action_grants%ROWTYPE;
    preceding jsonb;
    actual_generation bigint;
    audit_action text;
    expected_status text;
BEGIN
    -- A validated workforce actor / MFA assertion is not established by this
    -- function. The invoker must be a separately authenticated trusted host.
    SELECT * INTO g
    FROM public.matchdesk_producer_action_grants
    WHERE grant_id = p_grant_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    IF g.revoked_at IS NOT NULL OR g.consumed_at IS NOT NULL
       OR g.expires_at <= clock_timestamp()
       OR g.actor_id IS DISTINCT FROM p_actor_id
       OR g.tenant_id IS DISTINCT FROM p_tenant_id
       OR g.session_id IS DISTINCT FROM p_session_id
       OR g.output_id IS DISTINCT FROM p_output_id
       OR g.action IS DISTINCT FROM p_action
       OR g.expected_generation IS DISTINCT FROM p_expected_generation
       OR p_command_id !~ '^[A-Za-z0-9_-]{16,128}$'
       OR p_next_audit_digest !~ '^[a-f0-9]{64}$'
       OR p_expected_generation IS NULL
       OR p_expected_generation < 0 THEN
        RETURN FALSE;
    END IF;

    -- The whole immutable approval binding is compared at all three layers;
    -- no single digest, browser-supplied actor flag or claimed review status
    -- can substitute for the host's validated producer domain state.
    IF p_case_json IS NULL OR p_audit_entry IS NULL
       OR jsonb_typeof(p_case_json) IS DISTINCT FROM 'object'
       OR jsonb_typeof(p_audit_entry) IS DISTINCT FROM 'object'
       OR p_case_json #>> '{tenant_id}' IS DISTINCT FROM p_tenant_id
       OR p_case_json #>> '{output,session_id}' IS DISTINCT FROM p_session_id
       OR p_case_json #>> '{output,output_id}' IS DISTINCT FROM p_output_id
       OR p_case_json #>> '{generation}' IS DISTINCT FROM (p_expected_generation + 1)::text
       OR p_case_json #> '{output,binding}' IS DISTINCT FROM g.binding
       OR p_case_json #> '{review,binding}' IS DISTINCT FROM g.binding
       OR p_audit_entry -> 'binding' IS DISTINCT FROM g.binding
       OR p_audit_entry ->> 'actor_id' IS DISTINCT FROM p_actor_id
       OR jsonb_typeof(p_case_json #> '{review,audit}') IS DISTINCT FROM 'array'
       OR jsonb_array_length(p_case_json #> '{review,audit}') <> p_expected_generation + 1 THEN
        RETURN FALSE;
    END IF;

    audit_action := CASE p_action
        WHEN 'create' THEN 'review_started'
        WHEN 'edit' THEN 'revision_opened'
        WHEN 'reverify' THEN 'reverified'
        WHEN 'approve' THEN 'approved'
        WHEN 'reject' THEN 'rejected'
        ELSE NULL
    END;
    expected_status := CASE p_action
        WHEN 'create' THEN 'pending_verification'
        WHEN 'edit' THEN 'pending_verification'
        WHEN 'reverify' THEN 'ready_for_decision'
        WHEN 'approve' THEN 'approved'
        WHEN 'reject' THEN 'rejected'
        ELSE NULL
    END;
    IF audit_action IS NULL OR expected_status IS NULL
       OR p_audit_entry ->> 'action' IS DISTINCT FROM audit_action
       OR p_case_json #>> '{review,status}' IS DISTINCT FROM expected_status
       OR p_case_json #> '{review,audit}' -> (p_expected_generation::integer)
          IS DISTINCT FROM p_audit_entry THEN
        RETURN FALSE;
    END IF;

    IF p_action = 'create' THEN
        IF p_expected_generation <> 0 OR p_prior_audit_digest IS NOT NULL
           OR p_case_json #> '{review,audit}'
              IS DISTINCT FROM jsonb_build_array(p_audit_entry) THEN
            RETURN FALSE;
        END IF;
        INSERT INTO public.matchdesk_producer_cases
            (tenant_id, session_id, output_id, generation, case_json, audit_digest)
        VALUES (p_tenant_id, p_session_id, p_output_id, 1, p_case_json, p_next_audit_digest)
        ON CONFLICT DO NOTHING
        RETURNING generation INTO actual_generation;
    ELSE
        IF p_expected_generation < 1
           OR p_prior_audit_digest !~ '^[a-f0-9]{64}$' THEN
            RETURN FALSE;
        END IF;
        SELECT case_json INTO preceding
        FROM public.matchdesk_producer_cases
        WHERE tenant_id = p_tenant_id AND session_id = p_session_id
          AND output_id = p_output_id
          AND generation = p_expected_generation
          AND audit_digest = p_prior_audit_digest
        FOR UPDATE;
        IF NOT FOUND
           OR jsonb_typeof(preceding #> '{review,audit}') IS DISTINCT FROM 'array'
           OR p_case_json #> '{review,audit}' IS DISTINCT FROM
              ((preceding #> '{review,audit}') || jsonb_build_array(p_audit_entry)) THEN
            RETURN FALSE;
        END IF;
        UPDATE public.matchdesk_producer_cases
        SET generation = p_expected_generation + 1,
            case_json = p_case_json, audit_digest = p_next_audit_digest,
            updated_at = clock_timestamp()
        WHERE tenant_id = p_tenant_id AND session_id = p_session_id
          AND output_id = p_output_id
          AND generation = p_expected_generation
          AND audit_digest = p_prior_audit_digest
        RETURNING generation INTO actual_generation;
    END IF;

    IF actual_generation IS NULL THEN
        RETURN FALSE;
    END IF;

    INSERT INTO public.matchdesk_producer_audit
        (tenant_id, session_id, output_id, generation, entry_json, audit_digest)
    VALUES (p_tenant_id, p_session_id, p_output_id, actual_generation,
            p_audit_entry, p_next_audit_digest);

    -- If expiry occurs during a blocked CAS/audit, abort the entire statement
    -- and roll back the case write and append-only audit.
    IF g.expires_at <= clock_timestamp() THEN
        RAISE EXCEPTION 'Producer grant expired during commit';
    END IF;
    UPDATE public.matchdesk_producer_action_grants
    SET consumed_at = clock_timestamp(), command_id = p_command_id
    WHERE grant_id = p_grant_id AND revoked_at IS NULL AND consumed_at IS NULL;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Producer grant was not consumed atomically';
    END IF;
    RETURN TRUE;
END;
$function$;

-- Function defaults in PostgreSQL permit PUBLIC execution: explicitly remove it
-- in the same migration transaction. CI grants EXECUTE to only its test role.
REVOKE ALL ON FUNCTION public.matchdesk_commit_producer_grant(
    text, text, text, text, text, text, text, bigint, text, text, jsonb, jsonb
) FROM PUBLIC;
COMMIT;
