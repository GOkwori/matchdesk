-- P3-05: pending-only workforce session vault. Not a login cookie store.
-- No active session read, step-up bypass, activation or publication function.
-- All encrypted delegated tokens are owned by the database table owner.
CREATE TABLE IF NOT EXISTS public.matchdesk_workforce_pending_sessions (
    record_digest text PRIMARY KEY CHECK (record_digest ~ '^[a-f0-9]{64}$'),
    tenant_id uuid NOT NULL,
    issuer text NOT NULL CHECK (length(issuer) BETWEEN 30 AND 512),
    subject text NOT NULL CHECK (length(subject) BETWEEN 1 AND 256),
    object_id uuid NOT NULL,
    client_id uuid NOT NULL,
    issued_at_ms bigint NOT NULL CHECK (issued_at_ms > 0),
    expires_at_ms bigint NOT NULL,
    token_iv bytea NOT NULL CHECK (octet_length(token_iv) = 12),
    token_ciphertext bytea NOT NULL
        CHECK (octet_length(token_ciphertext) BETWEEN 16 AND 8192),
    token_tag bytea NOT NULL CHECK (octet_length(token_tag) = 16),
    revoked_at timestamptz,
    CHECK (
        expires_at_ms > issued_at_ms
        AND expires_at_ms <= issued_at_ms + 900000
    )
);
CREATE INDEX IF NOT EXISTS md_workforce_pending_expiry
    ON public.matchdesk_workforce_pending_sessions (expires_at_ms)
    WHERE revoked_at IS NULL;

REVOKE ALL ON public.matchdesk_workforce_pending_sessions FROM PUBLIC;

-- SECURITY DEFINER is limited to two immutable signatures and a fixed table.
-- The database clock enforces the maximum pending lifetime independently
-- of any host-supplied timestamp. No raw-token field is returned to callers.
CREATE OR REPLACE FUNCTION public.matchdesk_prepare_workforce_session(
    p_digest text, p_tenant uuid, p_issuer text, p_subject text,
    p_object uuid, p_client uuid, p_issued bigint, p_expires bigint,
    p_iv bytea, p_ciphertext bytea, p_tag bytea
) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog
AS $md_pending$
DECLARE inserted boolean;
BEGIN
    IF p_issued > floor(extract(epoch FROM clock_timestamp()) * 1000)::bigint
       OR p_expires <= floor(extract(epoch FROM clock_timestamp()) * 1000)::bigint
       OR p_issuer <> ('https://login.microsoftonline.com/' || p_tenant::text || '/v2.0')
    THEN
        RETURN false;
    END IF;
    INSERT INTO public.matchdesk_workforce_pending_sessions (
        record_digest, tenant_id, issuer, subject, object_id, client_id,
        issued_at_ms, expires_at_ms, token_iv, token_ciphertext, token_tag
    ) VALUES (
        p_digest, p_tenant, p_issuer, p_subject, p_object, p_client,
        p_issued, p_expires, p_iv, p_ciphertext, p_tag
    ) ON CONFLICT DO NOTHING RETURNING true INTO inserted;
    RETURN COALESCE(inserted, false);
END;
$md_pending$;

-- Revocation is an atomic tombstone: the record is never deleted or
-- restored. Repeated calls return false; no token/plaintext is exposed.
CREATE OR REPLACE FUNCTION public.matchdesk_revoke_workforce_session(
    p_digest text
) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog
AS $md_pending$
DECLARE marked boolean;
BEGIN
    UPDATE public.matchdesk_workforce_pending_sessions
       SET revoked_at = clock_timestamp()
     WHERE record_digest = p_digest AND revoked_at IS NULL
    RETURNING true INTO marked;
    RETURN COALESCE(marked, false);
END;
$md_pending$;

-- PostgreSQL functions default to PUBLIC EXECUTE. Deny it explicitly.
-- A future audited grant can allow only these exact functions to a
-- restricted backend role. This migration does not create live roles.
REVOKE ALL ON FUNCTION public.matchdesk_prepare_workforce_session(
    text, uuid, text, text, uuid, uuid, bigint, bigint, bytea, bytea, bytea
) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.matchdesk_revoke_workforce_session(text)
    FROM PUBLIC;
