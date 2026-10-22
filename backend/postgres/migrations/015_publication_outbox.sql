-- Publication outbox and language reviews. Requires 001_producer_review.sql.
-- Targets disposable/local databases until the owner approves a hosted deployment.
-- Applied (and re-applied) by the database owner, which must be able to act as every role here.
--
-- The database is the authority, not a mirror of the application:
-- * Nobody writes these tables directly. Logins act only through SECURITY DEFINER functions owned
--   by a NOLOGIN role that may have no members (checked on every call) and holds the minimum
--   table privileges. Every function pins its search path and qualifies every name.
-- * Queueing reads the producer audit itself: the audit entry at the case's current generation
--   must approve exactly the binding being queued, and the producer is taken from that entry.
-- * The database computes each publication ID from the binding and destination, so a caller can
--   neither squat on another publication's ID nor create a second row for the same version.
-- * Spanish and French need the latest language review of the exact content, in the same tenant,
--   by someone other than the producer, to approve. Reviews are numbered by the database under an
--   advisory lock that queueing and delivery also take; READ COMMITTED is required everywhere so
--   no caller can read past a review committed while it waited for that lock.
-- * Each delivery attempt is claimed first. The claim re-checks the approval and the review and
--   withdraws the row if either no longer holds; otherwise it moves the row to in_flight with a
--   random claim token and a lease of at most 15 minutes. Only the holder of the token can record
--   the outcome. Content sent under a live claim is recorded as delivered even if the approval
--   changes during the lease: it has already gone out. Destinations must still be idempotent on
--   publication ID, because a sender that outlives its lease may race a retry.
-- * Only a digest of each claim token is stored, so a login that can read the outbox cannot
--   record another worker's outcome. A lease that expires unreported counts as one attempt; if it
--   was the last, the row is 'unconfirmed' (never 'abandoned', since the send may have worked).
--   Every claim is kept, so any expired claim can still report a late success, which is recorded
--   as a settlement even if the row has since ended. An operator can settle an unconfirmed row
--   with outside evidence.
-- * Queueing stores and hashes the producer audit's own binding, never the caller's spelling of
--   it, so 1 and 1.0 cannot become two publications of one version.
-- * Withdrawn, abandoned and delivered rows are final; unconfirmed rows end only through a
--   settlement. Publishing that content again needs a new version.
-- * Two-person rules: the publisher and the language reviewer each differ from the producer. The
--   publisher may also be the language reviewer.
-- * Human actor IDs are asserted by the authenticated host (as in 001). The database records the
--   physical login that made each change next to them, so an asserted identity is attributable.
--   Logins are not bound to tenants; one deployment serves one organisation.
-- * The table owner can still disable triggers. Hosts must run as the capability roles below,
--   never as the owner. A worker should claim one row per transaction.
BEGIN;
SET LOCAL lock_timeout = '5s';

DO $roles$
DECLARE
    role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'matchdesk_publication_guard_owner', 'matchdesk_publisher', 'matchdesk_language_reviewer'
    ] LOOP
        IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = role_name) THEN
            EXECUTE pg_catalog.format(
                'CREATE ROLE %I NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT'
                ' NOREPLICATION NOBYPASSRLS', role_name);
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles
            WHERE rolname = role_name AND NOT rolsuper AND NOT rolcanlogin AND NOT rolcreaterole
              AND NOT rolcreatedb AND NOT rolreplication AND NOT rolbypassrls
        ) THEN
            RAISE EXCEPTION 'Publication role % is privileged', role_name USING ERRCODE = '42501';
        END IF;
    END LOOP;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_auth_members m
        WHERE m.roleid = 'matchdesk_publication_guard_owner'::regrole
    ) THEN
        RAISE EXCEPTION 'Publication guard owner has role members' USING ERRCODE = '42501';
    END IF;
END;
$roles$;

-- The publication ID scheme, shared with matchdesk.domain.publication.publication_id. NULL unless
-- the binding has exactly the ApprovalBinding 1.0 fields.
CREATE OR REPLACE FUNCTION public.matchdesk_publication_id(p_binding jsonb, p_destination text)
RETURNS text LANGUAGE sql IMMUTABLE STRICT SET search_path = pg_catalog, pg_temp AS $$
    SELECT CASE WHEN jsonb_typeof(p_binding) = 'object'
        AND ARRAY(SELECT k FROM jsonb_object_keys(p_binding) AS k ORDER BY k) = ARRAY[
            'content_digest', 'evidence_digest', 'item_id', 'item_version', 'language',
            'persona', 'replay_id', 'schema_version']::text[]
        AND jsonb_typeof(p_binding->'item_version') = 'number'
        AND p_binding->>'item_version' ~ '^[1-9][0-9]*$'
        AND p_binding->>'schema_version' = '1.0'
    THEN encode(sha256(convert_to(concat_ws(chr(31),
        'matchdesk-publication-v1', p_binding->>'item_id', p_binding->>'item_version',
        p_binding->>'replay_id', p_binding->>'content_digest', p_binding->>'evidence_digest',
        p_binding->>'language', p_binding->>'persona', p_destination), 'UTF8')), 'hex')
    END;
$$;

CREATE TABLE IF NOT EXISTS public.matchdesk_language_reviews (
    review_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id text NOT NULL CHECK (length(btrim(tenant_id)) BETWEEN 1 AND 96),
    content_digest text NOT NULL CHECK (content_digest ~ '^[a-f0-9]{64}$'),
    language text NOT NULL CHECK (language IN ('es', 'fr')),
    verdict text NOT NULL CHECK (verdict IN ('approved', 'changes_requested')),
    reviewer_actor_id text NOT NULL CHECK (length(btrim(reviewer_actor_id)) BETWEEN 1 AND 128),
    note text NOT NULL DEFAULT '' CHECK (length(note) <= 500),
    recorded_by text NOT NULL,
    reviewed_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS matchdesk_language_reviews_lookup
    ON public.matchdesk_language_reviews (tenant_id, content_digest, language, review_id DESC);

CREATE TABLE IF NOT EXISTS public.matchdesk_publication_outbox (
    tenant_id text NOT NULL CHECK (length(btrim(tenant_id)) BETWEEN 1 AND 96),
    publication_id text NOT NULL,
    session_id text NOT NULL,
    output_id text NOT NULL,
    producer_generation bigint NOT NULL CHECK (producer_generation >= 1),
    binding_json jsonb NOT NULL,
    language text NOT NULL CHECK (language IN ('en', 'es', 'fr')),
    content_digest text NOT NULL CHECK (content_digest ~ '^[a-f0-9]{64}$'),
    persona text NOT NULL CHECK (persona IN ('analyst', 'casual_fan', 'broadcast_caption')),
    destination text NOT NULL CHECK (destination IN ('match_centre', 'social', 'broadcast_overlay')),
    producer_actor_id text NOT NULL CHECK (length(btrim(producer_actor_id)) BETWEEN 1 AND 128),
    publisher_actor_id text NOT NULL CHECK (length(btrim(publisher_actor_id)) BETWEEN 1 AND 128),
    review_id bigint REFERENCES public.matchdesk_language_reviews (review_id),
    reviewer_actor_id text,
    max_attempts integer NOT NULL CHECK (max_attempts BETWEEN 1 AND 10),
    status text NOT NULL CHECK (
        status IN ('queued', 'in_flight', 'failed', 'delivered', 'abandoned', 'withdrawn',
                   'unconfirmed')
    ),
    attempts integer NOT NULL CHECK (attempts BETWEEN 0 AND max_attempts),
    claim_digest text CHECK (claim_digest IS NULL OR claim_digest ~ '^[a-f0-9]{64}$'),
    claimed_until timestamptz,
    last_error text CHECK (last_error IS NULL OR length(last_error) <= 500),
    receipt text CHECK (receipt IS NULL OR length(receipt) BETWEEN 1 AND 200),
    queued_by text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, publication_id),
    -- One row per approved version and destination, also under jsonb equality (1 = 1.0).
    CONSTRAINT matchdesk_outbox_one_per_destination UNIQUE (tenant_id, destination, binding_json),
    -- The ID is the database's own hash of the binding and destination.
    CONSTRAINT matchdesk_outbox_computed_id CHECK (
        publication_id IS NOT DISTINCT FROM public.matchdesk_publication_id(binding_json, destination)
    ),
    -- The typed columns are the binding's own fields, never a second opinion.
    CONSTRAINT matchdesk_outbox_typed_binding CHECK (
        binding_json->>'language' IS NOT DISTINCT FROM language
        AND binding_json->>'content_digest' IS NOT DISTINCT FROM content_digest
        AND binding_json->>'persona' IS NOT DISTINCT FROM persona
    ),
    -- Four eyes: whoever releases content is not the producer who approved it, and nobody reviews
    -- the language of their own approval.
    CONSTRAINT matchdesk_outbox_second_person CHECK (
        lower(btrim(publisher_actor_id)) <> lower(btrim(producer_actor_id))
        AND (reviewer_actor_id IS NULL
             OR lower(btrim(reviewer_actor_id)) <> lower(btrim(producer_actor_id)))
    ),
    -- Non-English content points at the review that approved it.
    CONSTRAINT matchdesk_outbox_reviewed_language CHECK (
        (language = 'en' AND review_id IS NULL AND reviewer_actor_id IS NULL)
        OR (language <> 'en' AND review_id IS NOT NULL AND reviewer_actor_id IS NOT NULL)
    ),
    CONSTRAINT matchdesk_outbox_destination_persona CHECK (
        (destination = 'match_centre' AND persona IN ('analyst', 'casual_fan'))
        OR (destination = 'social' AND persona = 'casual_fan')
        OR (destination = 'broadcast_overlay' AND persona = 'broadcast_caption')
    ),
    CONSTRAINT matchdesk_outbox_claim_when_in_flight CHECK (
        (status = 'in_flight') = (claim_digest IS NOT NULL)
        AND (claim_digest IS NULL) = (claimed_until IS NULL)
    ),
    CONSTRAINT matchdesk_outbox_receipt_when_delivered CHECK (
        (status = 'delivered') = (receipt IS NOT NULL)
    )
);

-- Every claim ever issued, so any expired claim can still report what really happened.
CREATE TABLE IF NOT EXISTS public.matchdesk_publication_claims (
    claim_digest text PRIMARY KEY CHECK (claim_digest ~ '^[a-f0-9]{64}$'),
    tenant_id text NOT NULL,
    publication_id text NOT NULL,
    claimed_at timestamptz NOT NULL,
    recorded_by text NOT NULL,
    FOREIGN KEY (tenant_id, publication_id)
        REFERENCES public.matchdesk_publication_outbox (tenant_id, publication_id)
);

-- The one report each claim may make. A claim with no report whose lease has expired is the only
-- kind that may still report a late success.
CREATE TABLE IF NOT EXISTS public.matchdesk_publication_claim_reports (
    claim_digest text PRIMARY KEY REFERENCES public.matchdesk_publication_claims (claim_digest),
    outcome text NOT NULL CHECK (outcome IN ('delivered', 'failed', 'refused', 'late_delivery')),
    reported_at timestamptz NOT NULL
);

-- How a publication really ended when that is not an ordinary reported attempt: a success
-- reported late by an expired claim, or an operator's resolution of an unconfirmed send.
CREATE TABLE IF NOT EXISTS public.matchdesk_publication_settlements (
    settlement_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id text NOT NULL,
    publication_id text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('late_delivery', 'operator_delivered', 'operator_abandoned')),
    claim_digest text UNIQUE REFERENCES public.matchdesk_publication_claims (claim_digest),
    receipt text CHECK (receipt IS NULL OR length(receipt) BETWEEN 1 AND 200),
    evidence text CHECK (evidence IS NULL OR length(btrim(evidence)) BETWEEN 1 AND 500),
    operator_actor_id text CHECK (
        operator_actor_id IS NULL OR length(btrim(operator_actor_id)) BETWEEN 1 AND 128
    ),
    recorded_by text NOT NULL,
    recorded_at timestamptz NOT NULL,
    FOREIGN KEY (tenant_id, publication_id)
        REFERENCES public.matchdesk_publication_outbox (tenant_id, publication_id),
    CONSTRAINT matchdesk_settlement_late_receipt CHECK (
        kind <> 'late_delivery' OR (claim_digest IS NOT NULL AND receipt IS NOT NULL)
    ),
    CONSTRAINT matchdesk_settlement_operator_evidence CHECK (
        kind = 'late_delivery'
        OR (claim_digest IS NULL AND evidence IS NOT NULL AND operator_actor_id IS NOT NULL)
    )
);

-- An unconfirmed send is resolved by an operator at most once.
CREATE UNIQUE INDEX IF NOT EXISTS matchdesk_settlement_one_resolution
    ON public.matchdesk_publication_settlements (tenant_id, publication_id)
    WHERE kind <> 'late_delivery';

-- CREATE TABLE IF NOT EXISTS would silently keep an older shape. Refuse to continue on drift.
DO $shape$
DECLARE
    actual text;
BEGIN
    SELECT string_agg(attname || ' ' || format_type(atttypid, atttypmod), ', ' ORDER BY attnum)
    INTO actual FROM pg_catalog.pg_attribute
    WHERE attrelid = 'public.matchdesk_publication_outbox'::regclass AND attnum > 0
      AND NOT attisdropped;
    IF actual IS DISTINCT FROM 'tenant_id text, publication_id text, session_id text, '
        'output_id text, producer_generation bigint, binding_json jsonb, language text, '
        'content_digest text, persona text, destination text, producer_actor_id text, '
        'publisher_actor_id text, review_id bigint, reviewer_actor_id text, max_attempts integer, '
        'status text, attempts integer, claim_digest text, claimed_until timestamp with time zone, '
        'last_error text, receipt text, queued_by text, created_at timestamp with time zone, '
        'updated_at timestamp with time zone' THEN
        RAISE EXCEPTION 'Publication outbox does not have the 015 shape (%); recreate it in the disposable database', actual;
    END IF;
    SELECT string_agg(attname || ' ' || format_type(atttypid, atttypmod), ', ' ORDER BY attnum)
    INTO actual FROM pg_catalog.pg_attribute
    WHERE attrelid = 'public.matchdesk_language_reviews'::regclass AND attnum > 0
      AND NOT attisdropped;
    IF actual IS DISTINCT FROM 'review_id bigint, tenant_id text, content_digest text, '
        'language text, verdict text, reviewer_actor_id text, note text, recorded_by text, '
        'reviewed_at timestamp with time zone' THEN
        RAISE EXCEPTION 'Language reviews do not have the 015 shape (%); recreate them in the disposable database', actual;
    END IF;
    SELECT string_agg(attname || ' ' || format_type(atttypid, atttypmod), ', ' ORDER BY attnum)
    INTO actual FROM pg_catalog.pg_attribute
    WHERE attrelid = 'public.matchdesk_publication_claims'::regclass AND attnum > 0
      AND NOT attisdropped;
    IF actual IS DISTINCT FROM 'claim_digest text, tenant_id text, publication_id text, '
        'claimed_at timestamp with time zone, recorded_by text' THEN
        RAISE EXCEPTION 'Publication claims do not have the 015 shape (%)', actual;
    END IF;
    SELECT string_agg(attname || ' ' || format_type(atttypid, atttypmod), ', ' ORDER BY attnum)
    INTO actual FROM pg_catalog.pg_attribute
    WHERE attrelid = 'public.matchdesk_publication_claim_reports'::regclass AND attnum > 0
      AND NOT attisdropped;
    IF actual IS DISTINCT FROM 'claim_digest text, outcome text, '
        'reported_at timestamp with time zone' THEN
        RAISE EXCEPTION 'Publication claim reports do not have the 015 shape (%)', actual;
    END IF;
    SELECT string_agg(attname || ' ' || format_type(atttypid, atttypmod), ', ' ORDER BY attnum)
    INTO actual FROM pg_catalog.pg_attribute
    WHERE attrelid = 'public.matchdesk_publication_settlements'::regclass AND attnum > 0
      AND NOT attisdropped;
    IF actual IS DISTINCT FROM 'settlement_id bigint, tenant_id text, publication_id text, '
        'kind text, claim_digest text, receipt text, evidence text, operator_actor_id text, '
        'recorded_by text, recorded_at timestamp with time zone' THEN
        RAISE EXCEPTION 'Publication settlements do not have the 015 shape (%)', actual;
    END IF;
END;
$shape$;

REVOKE ALL ON public.matchdesk_language_reviews, public.matchdesk_publication_outbox,
    public.matchdesk_publication_claims, public.matchdesk_publication_claim_reports,
    public.matchdesk_publication_settlements FROM PUBLIC;

-- ---------------------------------------------------------------------------------------------
-- Backstop triggers. Only the guard owner can write, but the rules hold even for its functions.
-- ---------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.matchdesk_outbox_guard_insert()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
    IF NEW.status <> 'queued' OR NEW.attempts <> 0 OR NEW.receipt IS NOT NULL
       OR NEW.last_error IS NOT NULL OR NEW.claim_digest IS NOT NULL THEN
        RAISE EXCEPTION 'A publication starts queued, unattempted and without a receipt';
    END IF;
    NEW.queued_by := session_user;
    NEW.created_at := clock_timestamp();
    NEW.updated_at := NEW.created_at;
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.matchdesk_outbox_guard_insert() FROM PUBLIC;

DROP TRIGGER IF EXISTS matchdesk_outbox_insert ON public.matchdesk_publication_outbox;
CREATE TRIGGER matchdesk_outbox_insert
BEFORE INSERT ON public.matchdesk_publication_outbox
FOR EACH ROW EXECUTE FUNCTION public.matchdesk_outbox_guard_insert();

-- Allowed moves:
--   queued/failed -> in_flight (a claim) or withdrawn: no attempt is counted;
--   in_flight -> failed, delivered or abandoned (a reported outcome), or failed or unconfirmed (a
--   lease that expired unreported): exactly one attempt is counted;
--   failed/in_flight/unconfirmed -> delivered, and unconfirmed -> abandoned, only on a recorded
--   settlement (a late success from an expired claim, or an operator's resolution): no attempt.
-- Nothing leaves delivered, abandoned or withdrawn.
CREATE OR REPLACE FUNCTION public.matchdesk_outbox_guard_transition()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
    IF OLD.status IN ('delivered', 'abandoned', 'withdrawn')
       OR (OLD.status = 'unconfirmed' AND NEW.status NOT IN ('delivered', 'abandoned')) THEN
        RAISE EXCEPTION 'A % publication is final', OLD.status;
    END IF;
    IF (NEW.tenant_id, NEW.publication_id, NEW.session_id, NEW.output_id, NEW.producer_generation,
        NEW.binding_json, NEW.destination, NEW.producer_actor_id, NEW.publisher_actor_id,
        NEW.max_attempts, NEW.queued_by, NEW.created_at)
       IS DISTINCT FROM
       (OLD.tenant_id, OLD.publication_id, OLD.session_id, OLD.output_id, OLD.producer_generation,
        OLD.binding_json, OLD.destination, OLD.producer_actor_id, OLD.publisher_actor_id,
        OLD.max_attempts, OLD.queued_by, OLD.created_at)
       OR NEW.review_id IS DISTINCT FROM OLD.review_id
       OR NEW.reviewer_actor_id IS DISTINCT FROM OLD.reviewer_actor_id THEN
        RAISE EXCEPTION 'Only delivery status may change';
    END IF;
    IF NEW.status IN ('in_flight', 'withdrawn') THEN
        IF OLD.status NOT IN ('queued', 'failed') THEN
            RAISE EXCEPTION 'Only a queued or failed publication can be claimed or withdrawn';
        END IF;
        IF NEW.attempts <> OLD.attempts THEN
            RAISE EXCEPTION 'A claim or withdrawal is not a delivery attempt';
        END IF;
    ELSIF NEW.status IN ('delivered', 'abandoned') AND NEW.attempts = OLD.attempts THEN
        -- A settlement, not an attempt: it must already be on record.
        IF NEW.status = 'delivered' THEN
            IF OLD.status NOT IN ('failed', 'in_flight', 'unconfirmed') OR NOT EXISTS (
                SELECT 1 FROM public.matchdesk_publication_settlements st
                WHERE st.tenant_id = OLD.tenant_id AND st.publication_id = OLD.publication_id
                  AND st.kind IN ('late_delivery', 'operator_delivered')
            ) THEN
                RAISE EXCEPTION 'An attempt must be claimed before its outcome is recorded';
            END IF;
        ELSIF OLD.status <> 'unconfirmed' OR NOT EXISTS (
            SELECT 1 FROM public.matchdesk_publication_settlements st
            WHERE st.tenant_id = OLD.tenant_id AND st.publication_id = OLD.publication_id
              AND st.kind = 'operator_abandoned'
        ) THEN
            RAISE EXCEPTION 'An attempt must be claimed before its outcome is recorded';
        END IF;
    ELSIF NEW.status IN ('failed', 'delivered', 'abandoned', 'unconfirmed') THEN
        IF OLD.status <> 'in_flight' THEN
            RAISE EXCEPTION 'An attempt must be claimed before its outcome is recorded';
        END IF;
        IF NEW.attempts <> OLD.attempts + 1 THEN
            RAISE EXCEPTION 'Each outcome records exactly one delivery attempt';
        END IF;
    ELSE
        RAISE EXCEPTION 'A publication never returns to queued';
    END IF;
    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.matchdesk_outbox_guard_transition() FROM PUBLIC;

DROP TRIGGER IF EXISTS matchdesk_outbox_transition ON public.matchdesk_publication_outbox;
CREATE TRIGGER matchdesk_outbox_transition
BEFORE UPDATE ON public.matchdesk_publication_outbox
FOR EACH ROW EXECUTE FUNCTION public.matchdesk_outbox_guard_transition();

CREATE OR REPLACE FUNCTION public.matchdesk_language_review_guard_insert()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
    NEW.recorded_by := session_user;
    NEW.reviewed_at := clock_timestamp();
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.matchdesk_language_review_guard_insert() FROM PUBLIC;

DROP TRIGGER IF EXISTS matchdesk_language_review_insert ON public.matchdesk_language_reviews;
CREATE TRIGGER matchdesk_language_review_insert
BEFORE INSERT ON public.matchdesk_language_reviews
FOR EACH ROW EXECUTE FUNCTION public.matchdesk_language_review_guard_insert();

-- Nothing is deleted or truncated: reviews and publications are the audit trail.
CREATE OR REPLACE FUNCTION public.matchdesk_block_publication_history_mutation()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
    RAISE EXCEPTION 'MatchDesk publication history is append-only';
END;
$$;
REVOKE ALL ON FUNCTION public.matchdesk_block_publication_history_mutation() FROM PUBLIC;

DROP TRIGGER IF EXISTS matchdesk_outbox_no_delete ON public.matchdesk_publication_outbox;
CREATE TRIGGER matchdesk_outbox_no_delete
BEFORE DELETE OR TRUNCATE ON public.matchdesk_publication_outbox
FOR EACH STATEMENT EXECUTE FUNCTION public.matchdesk_block_publication_history_mutation();

DROP TRIGGER IF EXISTS matchdesk_claims_immutable ON public.matchdesk_publication_claims;
CREATE TRIGGER matchdesk_claims_immutable
BEFORE UPDATE OR DELETE OR TRUNCATE ON public.matchdesk_publication_claims
FOR EACH STATEMENT EXECUTE FUNCTION public.matchdesk_block_publication_history_mutation();

DROP TRIGGER IF EXISTS matchdesk_claim_reports_immutable
    ON public.matchdesk_publication_claim_reports;
CREATE TRIGGER matchdesk_claim_reports_immutable
BEFORE UPDATE OR DELETE OR TRUNCATE ON public.matchdesk_publication_claim_reports
FOR EACH STATEMENT EXECUTE FUNCTION public.matchdesk_block_publication_history_mutation();

DROP TRIGGER IF EXISTS matchdesk_settlements_immutable ON public.matchdesk_publication_settlements;
CREATE TRIGGER matchdesk_settlements_immutable
BEFORE UPDATE OR DELETE OR TRUNCATE ON public.matchdesk_publication_settlements
FOR EACH STATEMENT EXECUTE FUNCTION public.matchdesk_block_publication_history_mutation();

DROP TRIGGER IF EXISTS matchdesk_reviews_immutable ON public.matchdesk_language_reviews;
CREATE TRIGGER matchdesk_reviews_immutable
BEFORE UPDATE OR DELETE OR TRUNCATE ON public.matchdesk_language_reviews
FOR EACH STATEMENT EXECUTE FUNCTION public.matchdesk_block_publication_history_mutation();

-- ---------------------------------------------------------------------------------------------
-- Shared checks, run by the guard owner inside the entry points below. Policy refusals use the
-- dedicated SQLSTATE MDPUB so that delivery can tell them apart from faults: only a policy
-- refusal withdraws a publication; a fault (a missing privilege, a timeout) is raised as is.
-- ---------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.matchdesk_claim_digest(p_token uuid)
RETURNS text LANGUAGE sql IMMUTABLE STRICT SET search_path = pg_catalog, pg_temp AS $$
    SELECT encode(sha256(convert_to(p_token::text, 'UTF8')), 'hex');
$$;

CREATE OR REPLACE FUNCTION public.matchdesk_publication_preflight()
RETURNS void LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
    -- Under REPEATABLE READ or SERIALIZABLE a caller would keep reading the snapshot taken before
    -- it waited for the review lock, and miss a review committed in the meantime.
    IF pg_catalog.current_setting('transaction_isolation') <> 'read committed' THEN
        RAISE EXCEPTION 'Publication requires READ COMMITTED' USING ERRCODE = '0A000';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_auth_members m
        WHERE m.roleid = 'matchdesk_publication_guard_owner'::regrole
    ) THEN
        RAISE EXCEPTION 'Publication guard owner has role members' USING ERRCODE = '42501';
    END IF;
END;
$$;

-- Serialises review recording with queueing and claiming for one piece of content.
CREATE OR REPLACE FUNCTION public.matchdesk_lock_language_review(
    p_tenant text, p_content_digest text, p_language text
) RETURNS void LANGUAGE sql SET search_path = pg_catalog, pg_temp AS $$
    SELECT pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        'matchdesk-language-review' || chr(31) || p_tenant || chr(31) || p_content_digest
        || chr(31) || p_language, 0));
$$;

-- The producer approval in force for a case: locks the case row so a concurrent revision waits,
-- then returns the audit entry at the case's current generation if it approves this binding.
CREATE OR REPLACE FUNCTION public.matchdesk_current_approval(
    p_tenant text, p_session text, p_output text, p_binding jsonb,
    OUT producer_actor_id text, OUT generation bigint, OUT approved_binding jsonb
) LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    current_generation bigint;
    entry jsonb;
BEGIN
    SELECT c.generation INTO current_generation FROM public.matchdesk_producer_cases c
    WHERE c.tenant_id = p_tenant AND c.session_id = p_session AND c.output_id = p_output
    FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'No producer case for this output' USING ERRCODE = 'MDPUB';
    END IF;
    SELECT a.entry_json INTO entry FROM public.matchdesk_producer_audit a
    WHERE a.tenant_id = p_tenant AND a.session_id = p_session AND a.output_id = p_output
      AND a.generation = current_generation;
    IF entry IS NULL OR entry->>'action' IS DISTINCT FROM 'approved'
       OR entry->'binding' IS DISTINCT FROM p_binding THEN
        RAISE EXCEPTION 'The producer has not approved this exact version' USING ERRCODE = 'MDPUB';
    END IF;
    producer_actor_id := entry->>'actor_id';
    generation := current_generation;
    approved_binding := entry->'binding';
END;
$$;

-- The latest review of the content, which must approve it and not be the producer's own.
CREATE OR REPLACE FUNCTION public.matchdesk_current_language_approval(
    p_tenant text, p_content_digest text, p_language text, p_producer_actor_id text
) RETURNS public.matchdesk_language_reviews
LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    latest public.matchdesk_language_reviews%ROWTYPE;
BEGIN
    PERFORM public.matchdesk_lock_language_review(p_tenant, p_content_digest, p_language);
    SELECT * INTO latest FROM public.matchdesk_language_reviews r
    WHERE r.tenant_id = p_tenant AND r.content_digest = p_content_digest
      AND r.language = p_language
    ORDER BY r.review_id DESC LIMIT 1;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Content needs a recorded language review' USING ERRCODE = 'MDPUB';
    END IF;
    IF latest.verdict <> 'approved' THEN
        RAISE EXCEPTION 'The latest language review does not approve this content'
            USING ERRCODE = 'MDPUB';
    END IF;
    IF lower(btrim(latest.reviewer_actor_id)) = lower(btrim(p_producer_actor_id)) THEN
        RAISE EXCEPTION 'The language reviewer must not be the producer who approved'
            USING ERRCODE = 'MDPUB';
    END IF;
    RETURN latest;
END;
$$;

-- ---------------------------------------------------------------------------------------------
-- The entry points. SECURITY DEFINER, owned by the guard owner, schema-qualified.
-- ---------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.matchdesk_record_language_review(
    p_tenant text, p_content_digest text, p_language text, p_verdict text,
    p_reviewer_actor_id text, p_note text DEFAULT ''
) RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    new_id bigint;
BEGIN
    PERFORM public.matchdesk_publication_preflight();
    PERFORM public.matchdesk_lock_language_review(p_tenant, p_content_digest, p_language);
    INSERT INTO public.matchdesk_language_reviews
        (tenant_id, content_digest, language, verdict, reviewer_actor_id, note,
         recorded_by, reviewed_at)
    VALUES (p_tenant, p_content_digest, p_language, p_verdict, btrim(p_reviewer_actor_id),
            coalesce(p_note, ''), session_user, clock_timestamp())
    RETURNING review_id INTO new_id;
    RETURN new_id;
END;
$$;

-- Queue one approved version for one destination. Returns the database-computed publication ID
-- and its status; queueing again returns the existing row, whatever its status.
CREATE OR REPLACE FUNCTION public.matchdesk_queue_publication(
    p_tenant text, p_session text, p_output text, p_binding jsonb,
    p_destination text, p_publisher_actor_id text, p_max_attempts integer
) RETURNS TABLE (publication_id text, status text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    approval record;
    review public.matchdesk_language_reviews%ROWTYPE;
    v_binding jsonb;
    v_id text;
    v_language text;
BEGIN
    PERFORM public.matchdesk_publication_preflight();
    IF public.matchdesk_publication_id(p_binding, p_destination) IS NULL THEN
        RAISE EXCEPTION 'Publication needs a complete approval binding' USING ERRCODE = 'MDPUB';
    END IF;
    SELECT * INTO approval
    FROM public.matchdesk_current_approval(p_tenant, p_session, p_output, p_binding);
    -- From here on the producer audit's own binding is used, never the caller's spelling of it.
    v_binding := approval.approved_binding;
    v_id := public.matchdesk_publication_id(v_binding, p_destination);
    v_language := v_binding->>'language';
    IF v_id IS NULL THEN
        RAISE EXCEPTION 'The approved binding is not a complete 1.0 binding' USING ERRCODE = 'MDPUB';
    END IF;
    IF lower(btrim(p_publisher_actor_id)) = lower(btrim(approval.producer_actor_id)) THEN
        RAISE EXCEPTION 'The publisher must not be the producer who approved'
            USING ERRCODE = 'MDPUB';
    END IF;
    IF v_language <> 'en' THEN
        review := public.matchdesk_current_language_approval(
            p_tenant, v_binding->>'content_digest', v_language, approval.producer_actor_id);
    END IF;
    INSERT INTO public.matchdesk_publication_outbox AS o
        (tenant_id, publication_id, session_id, output_id, producer_generation, binding_json,
         language, content_digest, persona, destination, producer_actor_id, publisher_actor_id,
         review_id, reviewer_actor_id, max_attempts, status, attempts, queued_by,
         created_at, updated_at)
    VALUES
        (p_tenant, v_id, p_session, p_output, approval.generation, v_binding,
         v_language, v_binding->>'content_digest', v_binding->>'persona', p_destination,
         approval.producer_actor_id, btrim(p_publisher_actor_id),
         review.review_id, review.reviewer_actor_id, p_max_attempts, 'queued', 0, session_user,
         clock_timestamp(), clock_timestamp())
    ON CONFLICT DO NOTHING;
    RETURN QUERY
        SELECT o.publication_id, o.status FROM public.matchdesk_publication_outbox o
        WHERE o.tenant_id = p_tenant AND o.destination = p_destination
          AND o.binding_json = v_binding;
END;
$$;

-- Claim one attempt. Returns {"binding": ..., "claim_token": ...} to deliver, or NULL when the row
-- is final, is already being sent under a live lease, or has just been withdrawn because its
-- approval or language review no longer holds. An expired lease counts as a failed attempt first.
CREATE OR REPLACE FUNCTION public.matchdesk_claim_publication_attempt(
    p_tenant text, p_publication_id text, p_lease_seconds integer DEFAULT 300
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    entry_row public.matchdesk_publication_outbox%ROWTYPE;
    approval record;
    review public.matchdesk_language_reviews%ROWTYPE;
    token uuid;
BEGIN
    PERFORM public.matchdesk_publication_preflight();
    IF p_lease_seconds IS NULL OR p_lease_seconds NOT BETWEEN 5 AND 900 THEN
        RAISE EXCEPTION 'A delivery lease lasts between 5 and 900 seconds';
    END IF;
    SELECT * INTO entry_row FROM public.matchdesk_publication_outbox o
    WHERE o.tenant_id = p_tenant AND o.publication_id = p_publication_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown publication';
    END IF;
    IF entry_row.status = 'in_flight' THEN
        IF entry_row.claimed_until > clock_timestamp() THEN
            RETURN NULL;
        END IF;
        -- The sender may yet have succeeded: its claim stays on record so a late success can still
        -- be reported, and the row is never called abandoned when the outcome is unknown.
        UPDATE public.matchdesk_publication_outbox o
        SET status = CASE WHEN o.attempts + 1 >= o.max_attempts THEN 'unconfirmed' ELSE 'failed' END,
            attempts = o.attempts + 1, claim_digest = NULL, claimed_until = NULL,
            last_error = 'The previous attempt did not report back before its lease expired'
        WHERE o.tenant_id = entry_row.tenant_id AND o.publication_id = entry_row.publication_id
        RETURNING o.* INTO entry_row;
    END IF;
    IF entry_row.status IN ('delivered', 'abandoned', 'withdrawn', 'unconfirmed') THEN
        RETURN NULL;
    END IF;
    BEGIN
        SELECT * INTO approval FROM public.matchdesk_current_approval(
            entry_row.tenant_id, entry_row.session_id, entry_row.output_id, entry_row.binding_json);
        IF entry_row.language <> 'en' THEN
            review := public.matchdesk_current_language_approval(
                entry_row.tenant_id, entry_row.content_digest, entry_row.language,
                approval.producer_actor_id);
            IF lower(btrim(review.reviewer_actor_id)) <> lower(btrim(entry_row.reviewer_actor_id)) THEN
                RAISE EXCEPTION 'The approving language review changed' USING ERRCODE = 'MDPUB';
            END IF;
        END IF;
    EXCEPTION WHEN SQLSTATE 'MDPUB' THEN
        UPDATE public.matchdesk_publication_outbox o
        SET status = 'withdrawn', last_error = left(SQLERRM, 500)
        WHERE o.tenant_id = entry_row.tenant_id AND o.publication_id = entry_row.publication_id;
        RETURN NULL;
    END;
    -- Only a digest of the token is stored, so other logins that can read the outbox cannot
    -- record outcomes for this claim.
    token := pg_catalog.gen_random_uuid();
    INSERT INTO public.matchdesk_publication_claims
        (claim_digest, tenant_id, publication_id, claimed_at, recorded_by)
    VALUES (public.matchdesk_claim_digest(token), entry_row.tenant_id, entry_row.publication_id,
            clock_timestamp(), session_user);
    UPDATE public.matchdesk_publication_outbox o
    SET status = 'in_flight', claim_digest = public.matchdesk_claim_digest(token),
        claimed_until = clock_timestamp() + make_interval(secs => p_lease_seconds)
    WHERE o.tenant_id = entry_row.tenant_id AND o.publication_id = entry_row.publication_id;
    RETURN jsonb_build_object('binding', entry_row.binding_json, 'claim_token', token);
END;
$$;

-- Record the outcome of a claimed attempt: 'delivered' (with a receipt), 'failed' or 'refused'.
-- Failures that use up the row's attempt budget become 'abandoned'. Any earlier, expired claim
-- may still report 'delivered' (its attempt was counted at expiry) and nothing else; that is kept
-- as a settlement, and moves the row to delivered unless it already ended. Returns the new status,
-- or 'late_delivery_recorded' when the row had already ended.
CREATE OR REPLACE FUNCTION public.matchdesk_record_publication_attempt(
    p_tenant text, p_publication_id text, p_claim_token uuid, p_outcome text, p_receipt text,
    p_error text
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    entry_row public.matchdesk_publication_outbox%ROWTYPE;
    presented text := public.matchdesk_claim_digest(p_claim_token);
    next_status text;
BEGIN
    PERFORM public.matchdesk_publication_preflight();
    SELECT * INTO entry_row FROM public.matchdesk_publication_outbox o
    WHERE o.tenant_id = p_tenant AND o.publication_id = p_publication_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown publication';
    END IF;
    -- An expired claim (an earlier claim of this publication that never reported) can still
    -- report a success, whatever has happened to the row since: the content went out, so that is
    -- recorded. A claim reports once.
    IF presented IS NOT NULL AND EXISTS (
        SELECT 1 FROM public.matchdesk_publication_claim_reports cr
        WHERE cr.claim_digest = presented
    ) THEN
        RAISE EXCEPTION 'This claim has already reported its outcome';
    END IF;
    IF presented IS NOT NULL AND presented IS DISTINCT FROM entry_row.claim_digest
       AND EXISTS (
           SELECT 1 FROM public.matchdesk_publication_claims c
           WHERE c.claim_digest = presented AND c.tenant_id = entry_row.tenant_id
             AND c.publication_id = entry_row.publication_id
       ) THEN
        IF p_outcome IS DISTINCT FROM 'delivered' THEN
            RAISE EXCEPTION 'This claim expired; its attempt was already counted';
        END IF;
        INSERT INTO public.matchdesk_publication_claim_reports (claim_digest, outcome, reported_at)
        VALUES (presented, 'late_delivery', clock_timestamp());
        INSERT INTO public.matchdesk_publication_settlements
            (tenant_id, publication_id, kind, claim_digest, receipt, recorded_by, recorded_at)
        VALUES (entry_row.tenant_id, entry_row.publication_id, 'late_delivery', presented,
                p_receipt, session_user, clock_timestamp());
        IF entry_row.status IN ('failed', 'in_flight', 'unconfirmed') THEN
            UPDATE public.matchdesk_publication_outbox o
            SET status = 'delivered', receipt = p_receipt, last_error = NULL,
                claim_digest = NULL, claimed_until = NULL
            WHERE o.tenant_id = entry_row.tenant_id
              AND o.publication_id = entry_row.publication_id;
            RETURN 'delivered';
        END IF;
        RETURN 'late_delivery_recorded';
    END IF;
    IF entry_row.status IN ('delivered', 'abandoned', 'withdrawn', 'unconfirmed') THEN
        RAISE EXCEPTION 'A % publication is final', entry_row.status;
    END IF;
    IF entry_row.status <> 'in_flight' OR presented IS NULL
       OR entry_row.claim_digest IS DISTINCT FROM presented THEN
        RAISE EXCEPTION 'No attempt is in flight under this claim';
    END IF;
    next_status := CASE p_outcome
        WHEN 'delivered' THEN 'delivered'
        WHEN 'refused' THEN 'abandoned'
        WHEN 'failed' THEN CASE WHEN entry_row.attempts + 1 >= entry_row.max_attempts
                                THEN 'abandoned' ELSE 'failed' END
    END;
    IF next_status IS NULL THEN
        RAISE EXCEPTION 'An attempt is delivered, failed or refused';
    END IF;
    INSERT INTO public.matchdesk_publication_claim_reports (claim_digest, outcome, reported_at)
    VALUES (presented, p_outcome, clock_timestamp());
    UPDATE public.matchdesk_publication_outbox o
    SET status = next_status, attempts = o.attempts + 1, claim_digest = NULL, claimed_until = NULL,
        receipt = CASE WHEN next_status = 'delivered' THEN p_receipt END,
        last_error = CASE WHEN next_status = 'delivered' THEN NULL ELSE left(p_error, 500) END
    WHERE o.tenant_id = entry_row.tenant_id AND o.publication_id = entry_row.publication_id;
    RETURN next_status;
END;
$$;

-- An operator settles an unconfirmed send with outside evidence (the destination's own record):
-- 'delivered' or 'abandoned'. Once per publication. Returns the new status.
CREATE OR REPLACE FUNCTION public.matchdesk_resolve_unconfirmed_publication(
    p_tenant text, p_publication_id text, p_resolution text, p_evidence text,
    p_operator_actor_id text
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    entry_row public.matchdesk_publication_outbox%ROWTYPE;
BEGIN
    PERFORM public.matchdesk_publication_preflight();
    IF p_resolution IS NULL OR p_resolution NOT IN ('delivered', 'abandoned') THEN
        RAISE EXCEPTION 'An unconfirmed publication is resolved as delivered or abandoned';
    END IF;
    SELECT * INTO entry_row FROM public.matchdesk_publication_outbox o
    WHERE o.tenant_id = p_tenant AND o.publication_id = p_publication_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown publication';
    END IF;
    IF entry_row.status <> 'unconfirmed' THEN
        RAISE EXCEPTION 'Only an unconfirmed publication is resolved by an operator';
    END IF;
    INSERT INTO public.matchdesk_publication_settlements
        (tenant_id, publication_id, kind, evidence, operator_actor_id, recorded_by, recorded_at)
    VALUES (entry_row.tenant_id, entry_row.publication_id, 'operator_' || p_resolution,
            btrim(p_evidence), btrim(p_operator_actor_id), session_user, clock_timestamp());
    UPDATE public.matchdesk_publication_outbox o
    SET status = p_resolution,
        receipt = CASE WHEN p_resolution = 'delivered' THEN 'operator-confirmed' END,
        last_error = CASE WHEN p_resolution = 'abandoned' THEN left(btrim(p_evidence), 500)
                          ELSE NULL END
    WHERE o.tenant_id = entry_row.tenant_id AND o.publication_id = entry_row.publication_id;
    RETURN p_resolution;
END;
$$;

-- ---------------------------------------------------------------------------------------------
-- Ownership and privileges.
-- ---------------------------------------------------------------------------------------------
GRANT USAGE ON SCHEMA public TO matchdesk_publication_guard_owner;
GRANT SELECT ON public.matchdesk_producer_cases, public.matchdesk_producer_audit
    TO matchdesk_publication_guard_owner;
-- FOR SHARE needs UPDATE on one column. Only this NOLOGIN, member-less role holds it.
GRANT UPDATE (updated_at) ON public.matchdesk_producer_cases TO matchdesk_publication_guard_owner;
GRANT SELECT, INSERT ON public.matchdesk_language_reviews TO matchdesk_publication_guard_owner;
GRANT SELECT, INSERT, UPDATE ON public.matchdesk_publication_outbox
    TO matchdesk_publication_guard_owner;
GRANT SELECT, INSERT ON public.matchdesk_publication_claims,
    public.matchdesk_publication_claim_reports, public.matchdesk_publication_settlements
    TO matchdesk_publication_guard_owner;

ALTER FUNCTION public.matchdesk_publication_id(jsonb, text)
    OWNER TO matchdesk_publication_guard_owner;
ALTER FUNCTION public.matchdesk_claim_digest(uuid)
    OWNER TO matchdesk_publication_guard_owner;
ALTER FUNCTION public.matchdesk_publication_preflight()
    OWNER TO matchdesk_publication_guard_owner;
ALTER FUNCTION public.matchdesk_lock_language_review(text, text, text)
    OWNER TO matchdesk_publication_guard_owner;
ALTER FUNCTION public.matchdesk_current_approval(text, text, text, jsonb)
    OWNER TO matchdesk_publication_guard_owner;
ALTER FUNCTION public.matchdesk_current_language_approval(text, text, text, text)
    OWNER TO matchdesk_publication_guard_owner;
ALTER FUNCTION public.matchdesk_record_language_review(text, text, text, text, text, text)
    OWNER TO matchdesk_publication_guard_owner;
ALTER FUNCTION public.matchdesk_queue_publication(text, text, text, jsonb, text, text, integer)
    OWNER TO matchdesk_publication_guard_owner;
ALTER FUNCTION public.matchdesk_claim_publication_attempt(text, text, integer)
    OWNER TO matchdesk_publication_guard_owner;
ALTER FUNCTION public.matchdesk_record_publication_attempt(text, text, uuid, text, text, text)
    OWNER TO matchdesk_publication_guard_owner;
ALTER FUNCTION public.matchdesk_resolve_unconfirmed_publication(text, text, text, text, text)
    OWNER TO matchdesk_publication_guard_owner;

-- Nothing but the pure ID hash is executable by PUBLIC. The hash stays public because a CHECK
-- uses it (so a restore by a non-superuser still validates rows) and hosts compare IDs with it.
REVOKE ALL ON FUNCTION public.matchdesk_claim_digest(uuid),
    public.matchdesk_publication_preflight(),
    public.matchdesk_lock_language_review(text, text, text),
    public.matchdesk_current_approval(text, text, text, jsonb),
    public.matchdesk_current_language_approval(text, text, text, text),
    public.matchdesk_record_language_review(text, text, text, text, text, text),
    public.matchdesk_queue_publication(text, text, text, jsonb, text, text, integer),
    public.matchdesk_claim_publication_attempt(text, text, integer),
    public.matchdesk_record_publication_attempt(text, text, uuid, text, text, text),
    public.matchdesk_resolve_unconfirmed_publication(text, text, text, text, text)
    FROM PUBLIC;

GRANT USAGE ON SCHEMA public TO matchdesk_publisher, matchdesk_language_reviewer;
GRANT EXECUTE ON FUNCTION public.matchdesk_record_language_review(text, text, text, text, text, text)
    TO matchdesk_language_reviewer;
GRANT SELECT ON public.matchdesk_language_reviews TO matchdesk_language_reviewer;
GRANT EXECUTE ON FUNCTION public.matchdesk_publication_id(jsonb, text) TO PUBLIC;
GRANT EXECUTE ON FUNCTION
    public.matchdesk_queue_publication(text, text, text, jsonb, text, text, integer),
    public.matchdesk_claim_publication_attempt(text, text, integer),
    public.matchdesk_record_publication_attempt(text, text, uuid, text, text, text),
    public.matchdesk_resolve_unconfirmed_publication(text, text, text, text, text)
    TO matchdesk_publisher;
GRANT SELECT ON public.matchdesk_publication_outbox, public.matchdesk_publication_settlements
    TO matchdesk_publisher;

COMMIT;
