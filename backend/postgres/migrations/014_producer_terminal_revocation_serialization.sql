-- P4 candidate: serialize host terminal revocation against atomic grant issuance.
-- Disposable CI ONLY. Never run on a live database without DBA/identity review.
-- Migration 013 stores append-only host events and terminal events. The former
-- issuer checked only the staged confirmation; revocation could occur after
-- the separate host read and before a grant was inserted.
BEGIN;

-- Retain the exact 011 function signature and its existing constrained
-- EXECUTE grants. CREATE OR REPLACE does not grant new authority or create an
-- unreviewed overload. A separately audited NOLOGIN owner is still required
-- before any operational deployment.
CREATE OR REPLACE FUNCTION public.matchdesk_issue_confirmed_producer_grant(
    p_confirmation_id text, p_grant_id text, p_tenant_id text,
    p_session_id text, p_output_id text, p_actor_id text, p_issuer text,
    p_action text, p_generation bigint, p_binding jsonb,
    p_case_hash text, p_audit_hash text
) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $serialized_issue$
DECLARE
    host_event public.matchdesk_producer_host_confirmation_events%ROWTYPE;
    verified public.matchdesk_producer_confirmations%ROWTYPE;
    inserted_id text;
BEGIN
    -- A REPEATABLE READ or SERIALIZABLE transaction can hold a stale snapshot
    -- across this advisory lock and miss a committed terminal revocation.
    -- Reject unsupported isolation before taking a lock or minting a grant.
    IF pg_catalog.current_setting('transaction_isolation') <> 'read committed' THEN
        RETURN FALSE;
    END IF;
    -- FIRST serialize before locking the staged confirmation.
    -- The terminal INSERT trigger obtains the same advisory xact lock.
    -- This establishes a single PostgreSQL serialization point for issuance
    -- and revocation, without relying on an earlier Python provenance read.
    -- Serialize issuer and terminal insertion without host-event UPDATE ACL.
    -- Both transactions acquire this confirmation-scoped xact advisory lock.
    IF p_confirmation_id IS NULL OR p_confirmation_id !~ '^[a-f0-9]{32}$' THEN
        RETURN FALSE;
    END IF;
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(p_confirmation_id, 0)
    );
    SELECT * INTO host_event
    FROM public.matchdesk_producer_host_confirmation_events
    WHERE confirmation_id = p_confirmation_id AND tenant_id = p_tenant_id;
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- SECOND lock the staged confirmation: advisory -> staged -> action grant.
    -- An independent legacy revoker may lock staged -> grant, but does not
    -- acquire event; no reverse staged -> event lock path is introduced.
    SELECT * INTO verified
    FROM public.matchdesk_producer_confirmations
    WHERE confirmation_id = p_confirmation_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    -- A terminal event committed before our advisory lock was acquired is
    -- visible to this statement under READ COMMITTED. A concurrent terminal
    -- writer must wait on the same advisory lock before it can commit.
    IF EXISTS (
        SELECT 1
        FROM public.matchdesk_producer_host_confirmation_terminals terminal
        WHERE terminal.confirmation_id = p_confirmation_id
          AND terminal.tenant_id = p_tenant_id
    ) THEN
        RETURN FALSE;
    END IF;

    -- The signed envelope hash staged by the verified host must exactly match
    -- the independently persisted host event, not merely its nonce. Check
    -- every overlapping actor/scope/hash dimension before issuing authority.
    IF host_event.actor_id IS DISTINCT FROM verified.actor_id
       OR host_event.token_issuer IS DISTINCT FROM verified.issuer
       OR host_event.session_id IS DISTINCT FROM verified.session_id
       OR host_event.output_id IS DISTINCT FROM verified.output_id
       OR host_event.action IS DISTINCT FROM verified.action
       OR host_event.expected_generation IS DISTINCT FROM verified.expected_generation
       OR host_event.authorized_case_sha256 IS DISTINCT FROM verified.authorized_case_sha256
       OR host_event.authorized_audit_digest IS DISTINCT FROM verified.authorized_audit_digest
       OR host_event.signed_envelope_sha256 IS DISTINCT FROM verified.proof_digest
       OR host_event.event_channel IS DISTINCT FROM 'workforce_authenticated_custom_dialog'
       OR host_event.confirmed_at > host_event.recorded_at
       OR host_event.confirmed_at > clock_timestamp()
       OR host_event.recorded_at > verified.confirmed_at
       OR host_event.confirmed_at < clock_timestamp() - interval '120 seconds'
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
       OR verified.consumed_at IS NOT NULL OR verified.revoked_at IS NOT NULL
       OR verified.expires_at <= clock_timestamp()
       OR verified.confirmed_at > clock_timestamp()
       OR p_grant_id IS NULL OR length(p_grant_id) NOT BETWEEN 16 AND 128
       OR p_grant_id ~ '[^A-Za-z0-9_-]'
    THEN
        RETURN FALSE;
    END IF;

    -- Both the action grant and the consumed confirmation commit together.
    -- The unique confirmation index prevents a second issuance even when
    -- separate issuer processes race on the same signed confirmation.
    INSERT INTO public.matchdesk_producer_action_grants
      (grant_id, confirmation_id, tenant_id, session_id, output_id, actor_id,
       issuer, action, binding, expected_generation, authorized_case_sha256,
       authorized_audit_digest, expires_at)
    VALUES
      (p_grant_id, p_confirmation_id, verified.tenant_id, verified.session_id,
       verified.output_id, verified.actor_id, verified.issuer, verified.action,
       verified.binding, verified.expected_generation,
       verified.authorized_case_sha256, verified.authorized_audit_digest,
       LEAST(verified.expires_at, clock_timestamp() + interval '60 seconds'))
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
        RAISE EXCEPTION 'Confirmation issuance expired or was revoked';
    END IF;
    RETURN TRUE;
END;
$serialized_issue$;
REVOKE ALL ON FUNCTION public.matchdesk_issue_confirmed_producer_grant(
    text,text,text,text,text,text,text,text,bigint,jsonb,text,text
) FROM PUBLIC;

-- A separate terminal-writer role may INSERT but never UPDATE/DELETE event
-- rows or acquire issuer function EXECUTE. This SECURITY DEFINER trigger is a
-- narrow fixed operation: lock the exact host event and revoke only a matching
-- unconsumed staged confirmation and its matching unspent action grant.
-- The terminal row insertion and revocation UPDATEs form ONE transaction.
CREATE OR REPLACE FUNCTION public.matchdesk_serialize_host_confirmation_terminal()
RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $serialized_terminal$
DECLARE
    parent_id text;
BEGIN
    -- A stale transaction snapshot could otherwise commit a terminal row but
    -- miss a grant issued after that snapshot began. Fail closed before any
    -- terminal insert/revocation rather than silently switch isolation.
    IF pg_catalog.current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION 'Terminal revocation requires READ COMMITTED'
            USING ERRCODE = '0A000';
    END IF;
    IF NEW.confirmation_id IS NULL OR NEW.tenant_id IS NULL
       OR NEW.terminal_state NOT IN ('revoked', 'cancelled') THEN
        RAISE EXCEPTION 'Invalid terminal confirmation scope';
    END IF;
    IF NEW.confirmation_id !~ '^[a-f0-9]{32}$' THEN
        RAISE EXCEPTION 'Invalid terminal confirmation identifier';
    END IF;
    PERFORM pg_catalog.pg_advisory_xact_lock(
        pg_catalog.hashtextextended(NEW.confirmation_id, 0)
    );
    SELECT e.event_id INTO parent_id
    FROM public.matchdesk_producer_host_confirmation_events e
    WHERE e.confirmation_id = NEW.confirmation_id
      AND e.tenant_id = NEW.tenant_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Host confirmation event does not exist';
    END IF;

    -- The issuer holds this advisory lock through its transaction.
    -- If issuance wins, the terminal writer waits and then revokes the new
    -- unconsumed grant. If revocation wins, the issuer waits and returns FALSE.
    UPDATE public.matchdesk_producer_confirmations
    SET revoked_at = COALESCE(revoked_at, clock_timestamp())
    WHERE confirmation_id = NEW.confirmation_id
      AND tenant_id = NEW.tenant_id
      AND revoked_at IS NULL;
    UPDATE public.matchdesk_producer_action_grants
    SET revoked_at = COALESCE(revoked_at, clock_timestamp())
    WHERE confirmation_id = NEW.confirmation_id
      AND tenant_id = NEW.tenant_id
      AND consumed_at IS NULL AND revoked_at IS NULL;
    RETURN NEW;
END;
$serialized_terminal$;
REVOKE ALL ON FUNCTION public.matchdesk_serialize_host_confirmation_terminal()
FROM PUBLIC;

DROP TRIGGER IF EXISTS matchdesk_host_confirmation_terminal_serialization
ON public.matchdesk_producer_host_confirmation_terminals;
CREATE TRIGGER matchdesk_host_confirmation_terminal_serialization
BEFORE INSERT ON public.matchdesk_producer_host_confirmation_terminals
FOR EACH ROW EXECUTE FUNCTION
    public.matchdesk_serialize_host_confirmation_terminal();

COMMIT;
