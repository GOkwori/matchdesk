-- P3-05: unmounted, host-only step-up challenges tied to pending workforce state.
-- These rows are NOT sessions, MFA evidence or execution grants. Never expose
-- the parent vault token, raw nonce or unrestricted table rights to app roles.
CREATE TABLE IF NOT EXISTS public.matchdesk_workforce_step_up_challenges (
    state_digest text PRIMARY KEY CHECK (state_digest ~ '^[a-f0-9]{64}$'),
    pending_digest text NOT NULL REFERENCES public.matchdesk_workforce_pending_sessions(record_digest),
    tenant_id uuid NOT NULL,
    client_id uuid NOT NULL,
    object_id uuid NOT NULL,
    subject text NOT NULL CHECK (length(subject) BETWEEN 1 AND 256),
    context_id text NOT NULL CHECK (context_id ~ '^c[1-9][0-9]?$'),
    issued_at_ms bigint NOT NULL CHECK (issued_at_ms > 0),
    expires_at_ms bigint NOT NULL,
    nonce_iv bytea NOT NULL CHECK (octet_length(nonce_iv) = 12),
    nonce_ciphertext bytea NOT NULL CHECK (octet_length(nonce_ciphertext) = 43),
    nonce_tag bytea NOT NULL CHECK (octet_length(nonce_tag) = 16),
    consumed_at timestamptz,
    CHECK (expires_at_ms = issued_at_ms + 300000)
);
CREATE INDEX IF NOT EXISTS md_workforce_step_up_pending
    ON public.matchdesk_workforce_step_up_challenges (pending_digest, expires_at_ms)
    WHERE consumed_at IS NULL;
REVOKE ALL ON public.matchdesk_workforce_step_up_challenges FROM PUBLIC;

-- Lock the pending row FIRST on both create and consume. This serializes
-- against matchdesk_revoke_workforce_session(), which updates the same row.
-- Enforce the exact actor and a full challenge lifetime inside that vault.
CREATE OR REPLACE FUNCTION public.matchdesk_create_workforce_step_up_challenge(
    p_state text, p_pending text, p_tenant uuid, p_client uuid,
    p_object uuid, p_subject text, p_context text, p_issued bigint,
    p_expires bigint, p_iv bytea, p_cipher bytea, p_tag bytea
) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog
AS $md_step_up$
DECLARE
    current_ms bigint;
    parent_ok boolean;
    inserted boolean;
BEGIN
    current_ms := floor(extract(epoch FROM clock_timestamp()) * 1000)::bigint;
    IF p_issued < current_ms - 30000 OR p_issued > current_ms + 30000
       OR p_expires <> p_issued + 300000 OR p_expires <= current_ms THEN
        RETURN false;
    END IF;
    SELECT true INTO parent_ok
      FROM public.matchdesk_workforce_pending_sessions AS p
     WHERE p.record_digest = p_pending AND p.revoked_at IS NULL
       AND p.issued_at_ms <= current_ms
       AND p.expires_at_ms >= p_expires
       AND p.tenant_id = p_tenant AND p.client_id = p_client
       AND p.object_id = p_object AND p.subject = p_subject
     FOR UPDATE OF p;
    IF parent_ok IS DISTINCT FROM true THEN RETURN false; END IF;
    INSERT INTO public.matchdesk_workforce_step_up_challenges (
        state_digest, pending_digest, tenant_id, client_id, object_id,
        subject, context_id, issued_at_ms, expires_at_ms,
        nonce_iv, nonce_ciphertext, nonce_tag
    ) VALUES (
        p_state, p_pending, p_tenant, p_client, p_object, p_subject,
        p_context, p_issued, p_expires, p_iv, p_cipher, p_tag
    ) ON CONFLICT DO NOTHING RETURNING true INTO inserted;
    RETURN COALESCE(inserted, false);
END;
$md_step_up$;

-- On revocation or pending expiry return NOTHING, not a partial receipt.
-- The consumed_at tombstone persists even if later cryptographic/CA checks
-- fail in the host; qualification cannot retry the same state.
CREATE OR REPLACE FUNCTION public.matchdesk_consume_workforce_step_up_challenge(
    p_state text, p_pending text
) RETURNS TABLE (
    state_digest text, pending_digest text, tenant_id uuid, client_id uuid,
    object_id uuid, subject text, context_id text, issued_at_ms bigint,
    expires_at_ms bigint, nonce_iv bytea, nonce_ciphertext bytea, nonce_tag bytea
)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog
AS $md_step_up$
DECLARE
    current_ms bigint;
    parent_ok boolean;
BEGIN
    current_ms := floor(extract(epoch FROM clock_timestamp()) * 1000)::bigint;
    SELECT true INTO parent_ok
      FROM public.matchdesk_workforce_pending_sessions AS p
     WHERE p.record_digest = p_pending AND p.revoked_at IS NULL
       AND p.issued_at_ms <= current_ms AND p.expires_at_ms > current_ms
     FOR UPDATE OF p;
    IF parent_ok IS DISTINCT FROM true THEN RETURN; END IF;
    RETURN QUERY
    UPDATE public.matchdesk_workforce_step_up_challenges AS c
       SET consumed_at = clock_timestamp()
     WHERE c.state_digest = p_state AND c.pending_digest = p_pending
       AND c.consumed_at IS NULL AND c.issued_at_ms <= current_ms
       AND c.expires_at_ms > current_ms
    RETURNING c.state_digest, c.pending_digest, c.tenant_id, c.client_id,
              c.object_id, c.subject, c.context_id, c.issued_at_ms,
              c.expires_at_ms, c.nonce_iv, c.nonce_ciphertext, c.nonce_tag;
END;
$md_step_up$;

-- PostgreSQL grants EXECUTE to PUBLIC by default. Production requires a
-- separately approved constrained, non-superuser function owner and caller.
REVOKE ALL ON FUNCTION public.matchdesk_create_workforce_step_up_challenge(
    text, text, uuid, uuid, uuid, text, text, bigint, bigint,
    bytea, bytea, bytea
) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.matchdesk_consume_workforce_step_up_challenge(text, text)
    FROM PUBLIC;
