-- P4 disposable-only host confirmation provenance store.
-- These rows are NOT an authentication service or authorization receipt.
-- A future separately governed host writer must authenticate the actual human
-- and sign independently; neither public HTTP nor producer executor may write.
BEGIN;

CREATE TABLE IF NOT EXISTS public.matchdesk_producer_host_confirmation_events (
    event_id text PRIMARY KEY CHECK (event_id ~ '^[a-f0-9]{32}$'),
    confirmation_id text NOT NULL UNIQUE
        CHECK (confirmation_id ~ '^[a-f0-9]{32}$'),
    tenant_id text NOT NULL CHECK (length(tenant_id) BETWEEN 1 AND 96),
    actor_id text NOT NULL CHECK (length(actor_id) BETWEEN 1 AND 256),
    token_issuer text NOT NULL CHECK (length(token_issuer) BETWEEN 1 AND 512),
    session_id text NOT NULL CHECK (length(session_id) BETWEEN 1 AND 96),
    output_id text NOT NULL CHECK (length(output_id) BETWEEN 1 AND 96),
    action text NOT NULL
        CHECK (action IN ('create', 'edit', 'reverify', 'approve', 'reject')),
    expected_generation bigint NOT NULL CHECK (expected_generation >= 0),
    authorized_case_sha256 text NOT NULL
        CHECK (authorized_case_sha256 ~ '^[a-f0-9]{64}$'),
    authorized_audit_digest text NOT NULL
        CHECK (authorized_audit_digest ~ '^[a-f0-9]{64}$'),
    signed_envelope_sha256 text NOT NULL
        CHECK (signed_envelope_sha256 ~ '^[a-f0-9]{64}$'),
    event_channel text NOT NULL
        CHECK (event_channel = 'workforce_authenticated_custom_dialog'),
    confirmed_at timestamptz NOT NULL,
    recorded_at timestamptz NOT NULL,
    CONSTRAINT matchdesk_host_confirmation_timeline CHECK (
        confirmed_at <= recorded_at
        AND recorded_at <= confirmed_at + interval '120 seconds'
    ),
    CONSTRAINT matchdesk_host_confirmation_scope UNIQUE (confirmation_id, tenant_id)
);

-- Append-only terminal events prevent an approved confirmation from being
-- silently reactivated by overwriting a status column.
CREATE TABLE IF NOT EXISTS public.matchdesk_producer_host_confirmation_terminals (
    event_id text PRIMARY KEY CHECK (event_id ~ '^[a-f0-9]{32}$'),
    confirmation_id text NOT NULL UNIQUE,
    tenant_id text NOT NULL,
    terminal_state text NOT NULL CHECK (terminal_state IN ('revoked', 'cancelled')),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT matchdesk_host_confirmation_terminal_scope
        FOREIGN KEY (confirmation_id, tenant_id)
        REFERENCES public.matchdesk_producer_host_confirmation_events
        (confirmation_id, tenant_id) ON DELETE RESTRICT
);

-- The runtime provider has no INSERT/UPDATE/DELETE, no table ownership and
-- no role-membership privileges. Even its read account is not created here.
REVOKE ALL ON public.matchdesk_producer_host_confirmation_events FROM PUBLIC;
REVOKE ALL ON public.matchdesk_producer_host_confirmation_terminals FROM PUBLIC;

CREATE OR REPLACE FUNCTION public.matchdesk_block_host_confirmation_mutation()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path = pg_catalog, pg_temp
AS $immutable$
BEGIN
    RAISE EXCEPTION 'MatchDesk host confirmations are append-only';
END;
$immutable$;
REVOKE ALL ON FUNCTION public.matchdesk_block_host_confirmation_mutation() FROM PUBLIC;

DROP TRIGGER IF EXISTS matchdesk_host_confirmation_events_immutable
    ON public.matchdesk_producer_host_confirmation_events;
CREATE TRIGGER matchdesk_host_confirmation_events_immutable
BEFORE UPDATE OR DELETE OR TRUNCATE
    ON public.matchdesk_producer_host_confirmation_events
FOR EACH STATEMENT EXECUTE FUNCTION public.matchdesk_block_host_confirmation_mutation();

DROP TRIGGER IF EXISTS matchdesk_host_confirmation_terminals_immutable
    ON public.matchdesk_producer_host_confirmation_terminals;
CREATE TRIGGER matchdesk_host_confirmation_terminals_immutable
BEFORE UPDATE OR DELETE OR TRUNCATE
    ON public.matchdesk_producer_host_confirmation_terminals
FOR EACH STATEMENT EXECUTE FUNCTION public.matchdesk_block_host_confirmation_mutation();

COMMIT;
