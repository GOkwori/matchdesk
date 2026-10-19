-- P3-05-ID3: workforce-only OIDC state, never customer state or session.
-- Static functions, fixed equality parameters, owner-only table and AES-256-GCM
-- ciphertext. No production rollout or DB role creation is approved here.
CREATE TABLE IF NOT EXISTS public.matchdesk_workforce_oidc_attempts (
    state_digest text PRIMARY KEY CHECK (state_digest ~ '^[a-f0-9]{64}$'),
    binding_digest text NOT NULL CHECK (binding_digest ~ '^[a-f0-9]{64}$'),
    issuer text NOT NULL CHECK (length(issuer) BETWEEN 30 AND 512),
    client_id text NOT NULL CHECK (length(client_id) BETWEEN 1 AND 160),
    redirect_uri text NOT NULL CHECK (length(redirect_uri) BETWEEN 1 AND 2048),
    issued_at_ms bigint NOT NULL CHECK (issued_at_ms > 0),
    expires_at_ms bigint NOT NULL,
    secret_iv bytea NOT NULL CHECK (octet_length(secret_iv) = 12),
    secret_ciphertext bytea NOT NULL CHECK (octet_length(secret_ciphertext) = 87),
    secret_tag bytea NOT NULL CHECK (octet_length(secret_tag) = 16),
    consumed_at timestamptz,
    CHECK (expires_at_ms = issued_at_ms + 300000)
);
CREATE INDEX IF NOT EXISTS md_workforce_oidc_expiry
    ON public.matchdesk_workforce_oidc_attempts (expires_at_ms)
    WHERE consumed_at IS NULL;

-- Never grant the application state role raw SELECT/INSERT/UPDATE/DELETE.
REVOKE ALL ON public.matchdesk_workforce_oidc_attempts FROM PUBLIC;

CREATE OR REPLACE FUNCTION public.matchdesk_create_workforce_oidc_attempt(
    p_state text, p_binding text, p_issuer text, p_client text, p_redirect text,
    p_issued bigint, p_expires bigint, p_iv bytea, p_cipher bytea, p_tag bytea
) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog
AS $md_workforce$
DECLARE inserted boolean;
BEGIN
    INSERT INTO public.matchdesk_workforce_oidc_attempts (
        state_digest, binding_digest, issuer, client_id, redirect_uri,
        issued_at_ms, expires_at_ms, secret_iv, secret_ciphertext, secret_tag
    ) VALUES (
        p_state, p_binding, p_issuer, p_client, p_redirect,
        p_issued, p_expires, p_iv, p_cipher, p_tag
    ) ON CONFLICT DO NOTHING RETURNING true INTO inserted;
    RETURN COALESCE(inserted, false);
END;
$md_workforce$;

CREATE OR REPLACE FUNCTION public.matchdesk_consume_workforce_oidc_attempt(
    p_state text
) RETURNS TABLE (
    state_digest text, binding_digest text, issuer text, client_id text,
    redirect_uri text, issued_at_ms bigint, expires_at_ms bigint,
    secret_iv bytea, secret_ciphertext bytea, secret_tag bytea
)
LANGUAGE sql VOLATILE SECURITY DEFINER
SET search_path = pg_catalog
AS $md_workforce$
    -- One UPDATE owns the replay tombstone and ensures only its first caller
    -- receives encrypted PKCE/nonce. The database clock, not the browser,
    -- decides whether the single-use attempt is still valid.
    UPDATE public.matchdesk_workforce_oidc_attempts AS a
       SET consumed_at = clock_timestamp()
     WHERE a.state_digest = p_state
       AND a.consumed_at IS NULL
       AND a.issued_at_ms <= floor(extract(epoch FROM clock_timestamp()) * 1000)::bigint
       AND a.expires_at_ms > floor(extract(epoch FROM clock_timestamp()) * 1000)::bigint
    RETURNING a.state_digest, a.binding_digest, a.issuer, a.client_id,
              a.redirect_uri, a.issued_at_ms, a.expires_at_ms,
              a.secret_iv, a.secret_ciphertext, a.secret_tag;
$md_workforce$;

-- PostgreSQL grants EXECUTE to PUBLIC on new functions by default.
-- An independently approved provisioning step must grant EXECUTE on these
-- exact signatures only to a trusted workforce state adapter identity.
REVOKE ALL ON FUNCTION public.matchdesk_create_workforce_oidc_attempt(
    text, text, text, text, text, bigint, bigint, bytea, bytea, bytea
) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.matchdesk_consume_workforce_oidc_attempt(text)
    FROM PUBLIC;
