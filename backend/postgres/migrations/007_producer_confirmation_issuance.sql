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
COMMIT;
