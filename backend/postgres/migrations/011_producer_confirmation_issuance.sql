-- Candidate for disposable CI only: unmounted confirmation-to-grant database work.
-- It has no live identity trust, human approval, or production authority.
BEGIN;
CREATE TABLE IF NOT EXISTS public.matchdesk_producer_confirmations (
    confirmation_id text PRIMARY KEY CHECK (confirmation_id ~ '^[a-f0-9]{32}$'),
    tenant_id text NOT NULL,
    session_id text NOT NULL,
    output_id text NOT NULL,
    actor_id text NOT NULL,
    issuer text NOT NULL,
    action text NOT NULL CHECK (action IN ('create','edit','reverify','approve','reject')),
    expected_generation bigint NOT NULL CHECK (expected_generation >= 0),
    binding jsonb NOT NULL CHECK (jsonb_typeof(binding)='object'),
    authorized_case_sha256 text NOT NULL CHECK (authorized_case_sha256 ~ '^[a-f0-9]{64}$'),
    authorized_audit_digest text NOT NULL CHECK (authorized_audit_digest ~ '^[a-f0-9]{64}$'),
    proof_digest text NOT NULL CHECK (proof_digest ~ '^[a-f0-9]{64}$'),
    confirmed_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    consumed_at timestamptz,
    issued_grant_id text UNIQUE,
    CHECK (expires_at > confirmed_at),
    CHECK (expires_at <= confirmed_at + interval '120 seconds'),
    CHECK ((consumed_at IS NULL) = (issued_grant_id IS NULL))
);
REVOKE ALL ON public.matchdesk_producer_confirmations FROM PUBLIC;
ALTER TABLE public.matchdesk_producer_action_grants
  ADD COLUMN IF NOT EXISTS confirmation_id text;
CREATE UNIQUE INDEX IF NOT EXISTS matchdesk_confirmation_grant_once
  ON public.matchdesk_producer_action_grants (confirmation_id)
  WHERE confirmation_id IS NOT NULL;
-- The trusted stager must verify the signed human-confirmation envelope,
-- current actor/session entitlements, enforced Entra policy and exact hashes
-- before inserting a confirmation. This function is not that stager.

-- A dedicated NOLOGIN definer owner must be assigned by a separately reviewed
-- DBA step before any deployment. Never leave a SECURITY DEFINER function owned
-- by a superuser, and never grant issuer table DML or role membership.
DROP FUNCTION IF EXISTS public.matchdesk_issue_confirmed_producer_grant(
    text, text, text, text, text, text, text, text, bigint, jsonb, text, text
);
CREATE FUNCTION public.matchdesk_issue_confirmed_producer_grant(
    p_confirmation_id text, p_grant_id text, p_tenant_id text,
    p_session_id text, p_output_id text, p_actor_id text, p_issuer text,
    p_action text, p_generation bigint, p_binding jsonb,
    p_case_hash text, p_audit_hash text
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
    verified public.matchdesk_producer_confirmations%ROWTYPE;
    inserted_id text;
BEGIN
    SELECT * INTO verified
      FROM public.matchdesk_producer_confirmations
      WHERE confirmation_id = p_confirmation_id
      FOR UPDATE;
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;
    IF verified.consumed_at IS NOT NULL
       OR verified.revoked_at IS NOT NULL
       OR verified.expires_at <= clock_timestamp()
       OR verified.confirmed_at > clock_timestamp()
       OR verified.tenant_id IS DISTINCT FROM p_tenant_id
       OR verified.session_id IS DISTINCT FROM p_session_id
       OR verified.output_id IS DISTINCT FROM p_output_id
       OR verified.actor_id IS DISTINCT FROM p_actor_id
       OR verified.issuer IS DISTINCT FROM p_issuer
       OR verified.action IS DISTINCT FROM p_action
       OR verified.expected_generation IS DISTINCT FROM p_generation
       OR verified.binding IS DISTINCT FROM p_binding
       OR verified.authorized_case_sha256 IS DISTINCT FROM p_case_hash
       OR verified.authorized_audit_digest IS DISTINCT FROM p_audit_hash
       OR p_grant_id IS NULL
       OR length(p_grant_id) < 16
       OR length(p_grant_id) > 128
       OR p_grant_id ~ ''[^A-Za-z0-9_-]''
    THEN
        RETURN FALSE;
    END IF;

    -- Grant insertion and confirmation consumption share this transaction.
    -- The unique confirmation index makes duplicate issuance fail closed.
    INSERT INTO public.matchdesk_producer_action_grants
      (grant_id, confirmation_id, tenant_id, session_id, output_id, actor_id,
       issuer, action, binding, expected_generation, authorized_case_sha256,
       authorized_audit_digest, expires_at)
    VALUES
      (p_grant_id, p_confirmation_id, verified.tenant_id, verified.session_id,
       verified.output_id, verified.actor_id, verified.issuer, verified.action,
       verified.binding, verified.expected_generation,
       verified.authorized_case_sha256, verified.authorized_audit_digest,
       LEAST(verified.expires_at, clock_timestamp() + interval ''60 seconds''))
    ON CONFLICT DO NOTHING
    RETURNING grant_id INTO inserted_id;
    IF inserted_id IS NULL THEN
        RETURN FALSE;
    END IF;

    UPDATE public.matchdesk_producer_confirmations
      SET consumed_at = clock_timestamp(), issued_grant_id = inserted_id
      WHERE confirmation_id = p_confirmation_id
        AND consumed_at IS NULL AND revoked_at IS NULL;
    IF NOT FOUND OR verified.expires_at <= clock_timestamp() THEN
        RAISE EXCEPTION ''Confirmation issuance expired or was revoked'';
    END IF;
    RETURN TRUE;
END;';
REVOKE ALL ON FUNCTION public.matchdesk_issue_confirmed_producer_grant(
    text,text,text,text,text,text,text,text,bigint,jsonb,text,text
) FROM PUBLIC;

DROP FUNCTION IF EXISTS public.matchdesk_revoke_confirmed_producer_grant(text);
CREATE FUNCTION public.matchdesk_revoke_confirmed_producer_grant(
    p_confirmation_id text
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS 'DECLARE
    selected_id text;
BEGIN
    SELECT confirmation_id INTO selected_id
      FROM public.matchdesk_producer_confirmations
      WHERE confirmation_id = p_confirmation_id
      FOR UPDATE;
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;
    UPDATE public.matchdesk_producer_confirmations
      SET revoked_at = COALESCE(revoked_at, clock_timestamp())
      WHERE confirmation_id = selected_id;
    UPDATE public.matchdesk_producer_action_grants
      SET revoked_at = COALESCE(revoked_at, clock_timestamp())
      WHERE confirmation_id = selected_id
        AND consumed_at IS NULL AND revoked_at IS NULL;
    RETURN TRUE;
END;';
REVOKE ALL ON FUNCTION public.matchdesk_revoke_confirmed_producer_grant(text)
FROM PUBLIC;
COMMIT;
