-- Publication outbox and language reviews. Requires 001_producer_review.sql.
-- Targets disposable/local databases until the owner approves a hosted deployment.
--
-- The database is the authority, not a mirror of the application:
-- * Nobody writes these tables directly. Logins act only through four SECURITY DEFINER
--   functions owned by a NOLOGIN role with no members and the minimum table privileges.
-- * Queueing reads the producer audit itself: the latest audit entry for the case must approve
--   exactly the binding being queued, and the producer is taken from that entry, not the caller.
-- * Spanish and French need the latest language review of the exact content to approve. Reviews
--   are numbered by the database under a lock shared with queueing, so "latest" cannot be rigged.
-- * Before each delivery attempt the approval and review are checked again; a row whose approval
--   or review changed is withdrawn instead of delivered.
-- * Human actor IDs are asserted by the authenticated host (as in 001). The database records the
--   physical login that made each change next to them, so an asserted identity is attributable.
-- * The table owner can still disable triggers. Hosts must run as the capability roles below,
--   never as the owner.
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
    -- Logins are granted the capability roles; nobody may act as the function owner.
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_auth_members m
        JOIN pg_catalog.pg_roles r ON r.oid = m.roleid
        WHERE r.rolname = 'matchdesk_publication_guard_owner'
    ) THEN
        RAISE EXCEPTION 'Publication guard owner has role members' USING ERRCODE = '42501';
    END IF;
END;
$roles$;

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
    publication_id text NOT NULL CHECK (publication_id ~ '^[a-f0-9]{64}$'),
    session_id text NOT NULL,
    output_id text NOT NULL,
    producer_generation bigint NOT NULL CHECK (producer_generation >= 1),
    binding_json jsonb NOT NULL CHECK (jsonb_typeof(binding_json) = 'object'),
    language text NOT NULL CHECK (language IN ('en', 'es', 'fr')),
    content_digest text NOT NULL CHECK (content_digest ~ '^[a-f0-9]{64}$'),
    persona text NOT NULL CHECK (persona IN ('analyst', 'casual_fan', 'broadcast_caption')),
    destination text NOT NULL CHECK (destination IN ('match_centre', 'social', 'broadcast_overlay')),
    producer_actor_id text NOT NULL CHECK (length(btrim(producer_actor_id)) BETWEEN 1 AND 128),
    publisher_actor_id text NOT NULL CHECK (length(btrim(publisher_actor_id)) BETWEEN 1 AND 128),
    review_id bigint REFERENCES public.matchdesk_language_reviews (review_id),
    reviewer_actor_id text,
    max_attempts integer NOT NULL CHECK (max_attempts BETWEEN 1 AND 10),
    status text NOT NULL CHECK (status IN ('queued', 'failed', 'delivered', 'abandoned', 'withdrawn')),
    attempts integer NOT NULL CHECK (attempts BETWEEN 0 AND max_attempts),
    last_error text CHECK (last_error IS NULL OR length(last_error) <= 500),
    receipt text CHECK (receipt IS NULL OR length(receipt) BETWEEN 1 AND 200),
    queued_by text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (tenant_id, publication_id),
    -- One row per approved version and destination, whatever ID a caller proposes.
    CONSTRAINT matchdesk_outbox_one_per_destination UNIQUE (tenant_id, destination, binding_json),
    -- The typed columns are the binding's own fields, never a second opinion.
    CONSTRAINT matchdesk_outbox_typed_binding CHECK (
        binding_json->>'language' = language
        AND binding_json->>'content_digest' = content_digest
        AND binding_json->>'persona' = persona
    ),
    -- Four eyes: whoever releases content is not the producer who approved it.
    CONSTRAINT matchdesk_outbox_second_person CHECK (
        lower(btrim(publisher_actor_id)) <> lower(btrim(producer_actor_id))
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
    CONSTRAINT matchdesk_outbox_receipt_when_delivered CHECK (
        (status = 'delivered') = (receipt IS NOT NULL)
    )
);

-- CREATE TABLE IF NOT EXISTS would silently keep an older shape. Refuse to continue on drift.
DO $shape$
BEGIN
    IF (SELECT count(*) FROM pg_catalog.pg_attribute
        WHERE attrelid = 'public.matchdesk_publication_outbox'::regclass AND attnum > 0
          AND NOT attisdropped
          AND attname IN ('producer_generation', 'review_id', 'max_attempts', 'queued_by')) <> 4
       OR (SELECT count(*) FROM pg_catalog.pg_attribute
           WHERE attrelid = 'public.matchdesk_language_reviews'::regclass AND attnum > 0
             AND NOT attisdropped AND attname = 'recorded_by') <> 1 THEN
        RAISE EXCEPTION 'Publication tables do not have the 015 shape; recreate them in the disposable database';
    END IF;
END;
$shape$;

REVOKE ALL ON public.matchdesk_language_reviews, public.matchdesk_publication_outbox FROM PUBLIC;

-- ---------------------------------------------------------------------------------------------
-- Backstop triggers. Only the guard owner can write, but the rules hold even for its functions.
-- ---------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.matchdesk_outbox_guard_insert()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
    IF NEW.status <> 'queued' OR NEW.attempts <> 0 OR NEW.receipt IS NOT NULL
       OR NEW.last_error IS NOT NULL THEN
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

CREATE OR REPLACE FUNCTION public.matchdesk_outbox_guard_transition()
RETURNS trigger LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
BEGIN
    IF OLD.status IN ('delivered', 'abandoned', 'withdrawn') THEN
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
    IF NEW.status = 'withdrawn' THEN
        IF NEW.attempts <> OLD.attempts THEN
            RAISE EXCEPTION 'A withdrawal is not a delivery attempt';
        END IF;
    ELSIF NEW.status NOT IN ('failed', 'delivered', 'abandoned') THEN
        RAISE EXCEPTION 'An attempt ends failed, delivered or abandoned';
    ELSIF NEW.attempts <> OLD.attempts + 1 THEN
        RAISE EXCEPTION 'Each update records exactly one delivery attempt';
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

DROP TRIGGER IF EXISTS matchdesk_reviews_immutable ON public.matchdesk_language_reviews;
CREATE TRIGGER matchdesk_reviews_immutable
BEFORE UPDATE OR DELETE OR TRUNCATE ON public.matchdesk_language_reviews
FOR EACH STATEMENT EXECUTE FUNCTION public.matchdesk_block_publication_history_mutation();

-- ---------------------------------------------------------------------------------------------
-- Shared checks, run by the guard owner inside the functions below.
-- ---------------------------------------------------------------------------------------------

-- Serialises review recording with queueing and delivery for one piece of content.
CREATE OR REPLACE FUNCTION public.matchdesk_lock_language_review(
    p_tenant text, p_content_digest text, p_language text
) RETURNS void LANGUAGE sql SET search_path = pg_catalog, pg_temp AS $$
    SELECT pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        'matchdesk-language-review' || chr(31) || p_tenant || chr(31) || p_content_digest
        || chr(31) || p_language, 0));
$$;
REVOKE ALL ON FUNCTION public.matchdesk_lock_language_review(text, text, text) FROM PUBLIC;

-- The producer approval in force for a case: locks the case row so a concurrent revision waits,
-- then returns the audit entry at the case's current generation if it approves this binding.
CREATE OR REPLACE FUNCTION public.matchdesk_current_approval(
    p_tenant text, p_session text, p_output text, p_binding jsonb,
    OUT producer_actor_id text, OUT generation bigint
) LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    current_generation bigint;
    entry jsonb;
BEGIN
    SELECT c.generation INTO current_generation FROM public.matchdesk_producer_cases c
    WHERE c.tenant_id = p_tenant AND c.session_id = p_session AND c.output_id = p_output
    FOR SHARE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'No producer case for this output' USING ERRCODE = '42501';
    END IF;
    SELECT a.entry_json INTO entry FROM public.matchdesk_producer_audit a
    WHERE a.tenant_id = p_tenant AND a.session_id = p_session AND a.output_id = p_output
      AND a.generation = current_generation;
    IF entry IS NULL OR entry->>'action' IS DISTINCT FROM 'approved'
       OR entry->'binding' IS DISTINCT FROM p_binding THEN
        RAISE EXCEPTION 'The producer has not approved this exact version' USING ERRCODE = '42501';
    END IF;
    producer_actor_id := entry->>'actor_id';
    generation := current_generation;
END;
$$;
REVOKE ALL ON FUNCTION public.matchdesk_current_approval(text, text, text, jsonb) FROM PUBLIC;

-- The latest review of the content, which must approve it.
CREATE OR REPLACE FUNCTION public.matchdesk_current_language_approval(
    p_tenant text, p_content_digest text, p_language text
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
        RAISE EXCEPTION 'Content needs a recorded language review' USING ERRCODE = '42501';
    END IF;
    IF latest.verdict <> 'approved' THEN
        RAISE EXCEPTION 'The latest language review does not approve this content'
            USING ERRCODE = '42501';
    END IF;
    RETURN latest;
END;
$$;
REVOKE ALL ON FUNCTION public.matchdesk_current_language_approval(text, text, text) FROM PUBLIC;

-- ---------------------------------------------------------------------------------------------
-- The four entry points. SECURITY DEFINER, owned by the guard owner, schema-qualified.
-- ---------------------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.matchdesk_record_language_review(
    p_tenant text, p_content_digest text, p_language text, p_verdict text,
    p_reviewer_actor_id text, p_note text DEFAULT ''
) RETURNS bigint
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    new_id bigint;
BEGIN
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

CREATE OR REPLACE FUNCTION public.matchdesk_queue_publication(
    p_tenant text, p_publication_id text, p_session text, p_output text, p_binding jsonb,
    p_destination text, p_publisher_actor_id text, p_max_attempts integer
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    approval record;
    review public.matchdesk_language_reviews%ROWTYPE;
    v_language text := p_binding->>'language';
    existing text;
BEGIN
    IF p_binding IS NULL OR jsonb_typeof(p_binding) <> 'object' OR v_language IS NULL THEN
        RAISE EXCEPTION 'Publication needs a complete approval binding';
    END IF;
    SELECT * INTO approval
    FROM public.matchdesk_current_approval(p_tenant, p_session, p_output, p_binding);
    IF lower(btrim(p_publisher_actor_id)) = lower(btrim(approval.producer_actor_id)) THEN
        RAISE EXCEPTION 'The publisher must not be the producer who approved'
            USING ERRCODE = '42501';
    END IF;
    IF v_language <> 'en' THEN
        review := public.matchdesk_current_language_approval(
            p_tenant, p_binding->>'content_digest', v_language);
    END IF;
    INSERT INTO public.matchdesk_publication_outbox
        (tenant_id, publication_id, session_id, output_id, producer_generation, binding_json,
         language, content_digest, persona, destination, producer_actor_id, publisher_actor_id,
         review_id, reviewer_actor_id, max_attempts, status, attempts, queued_by,
         created_at, updated_at)
    VALUES
        (p_tenant, p_publication_id, p_session, p_output, approval.generation, p_binding,
         v_language, p_binding->>'content_digest', p_binding->>'persona', p_destination,
         approval.producer_actor_id, btrim(p_publisher_actor_id),
         review.review_id, review.reviewer_actor_id, p_max_attempts, 'queued', 0, session_user,
         clock_timestamp(), clock_timestamp())
    ON CONFLICT ON CONSTRAINT matchdesk_outbox_one_per_destination DO NOTHING
    RETURNING publication_id INTO existing;
    IF existing IS NULL THEN
        -- Already queued: return the original publication rather than a second one.
        SELECT o.publication_id INTO existing FROM public.matchdesk_publication_outbox o
        WHERE o.tenant_id = p_tenant AND o.destination = p_destination
          AND o.binding_json = p_binding;
    END IF;
    RETURN existing;
END;
$$;

-- Claim one attempt. Returns the binding to deliver, or NULL when the row is final or has just
-- been withdrawn because its approval or language review no longer holds.
CREATE OR REPLACE FUNCTION public.matchdesk_begin_publication_attempt(
    p_tenant text, p_publication_id text
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    entry_row public.matchdesk_publication_outbox%ROWTYPE;
    approval record;
    review public.matchdesk_language_reviews%ROWTYPE;
BEGIN
    SELECT * INTO entry_row FROM public.matchdesk_publication_outbox o
    WHERE o.tenant_id = p_tenant AND o.publication_id = p_publication_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown publication';
    END IF;
    IF entry_row.status IN ('delivered', 'abandoned', 'withdrawn') THEN
        RETURN NULL;
    END IF;
    BEGIN
        SELECT * INTO approval FROM public.matchdesk_current_approval(
            entry_row.tenant_id, entry_row.session_id, entry_row.output_id, entry_row.binding_json);
        IF entry_row.language <> 'en' THEN
            review := public.matchdesk_current_language_approval(
                entry_row.tenant_id, entry_row.content_digest, entry_row.language);
            IF lower(btrim(review.reviewer_actor_id)) <> lower(btrim(entry_row.reviewer_actor_id)) THEN
                RAISE EXCEPTION 'The approving language review changed' USING ERRCODE = '42501';
            END IF;
        END IF;
    EXCEPTION WHEN insufficient_privilege THEN
        UPDATE public.matchdesk_publication_outbox
        SET status = 'withdrawn', last_error = left(SQLERRM, 500)
        WHERE tenant_id = entry_row.tenant_id AND publication_id = entry_row.publication_id;
        RETURN NULL;
    END;
    RETURN entry_row.binding_json;
END;
$$;

-- Record the outcome of one attempt: 'delivered' (with a receipt), 'failed' or 'refused'.
-- Failures past the row's attempt budget become 'abandoned'. Returns the new status.
CREATE OR REPLACE FUNCTION public.matchdesk_record_publication_attempt(
    p_tenant text, p_publication_id text, p_outcome text, p_receipt text, p_error text
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    entry_row public.matchdesk_publication_outbox%ROWTYPE;
    next_status text;
BEGIN
    SELECT * INTO entry_row FROM public.matchdesk_publication_outbox o
    WHERE o.tenant_id = p_tenant AND o.publication_id = p_publication_id
    FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Unknown publication';
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
    UPDATE public.matchdesk_publication_outbox
    SET status = next_status, attempts = entry_row.attempts + 1,
        receipt = CASE WHEN next_status = 'delivered' THEN p_receipt END,
        last_error = CASE WHEN next_status = 'delivered' THEN NULL ELSE left(p_error, 500) END
    WHERE tenant_id = entry_row.tenant_id AND publication_id = entry_row.publication_id;
    RETURN next_status;
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

ALTER FUNCTION public.matchdesk_lock_language_review(text, text, text)
    OWNER TO matchdesk_publication_guard_owner;
ALTER FUNCTION public.matchdesk_current_approval(text, text, text, jsonb)
    OWNER TO matchdesk_publication_guard_owner;
ALTER FUNCTION public.matchdesk_current_language_approval(text, text, text)
    OWNER TO matchdesk_publication_guard_owner;
ALTER FUNCTION public.matchdesk_record_language_review(text, text, text, text, text, text)
    OWNER TO matchdesk_publication_guard_owner;
ALTER FUNCTION public.matchdesk_queue_publication(text, text, text, text, jsonb, text, text, integer)
    OWNER TO matchdesk_publication_guard_owner;
ALTER FUNCTION public.matchdesk_begin_publication_attempt(text, text)
    OWNER TO matchdesk_publication_guard_owner;
ALTER FUNCTION public.matchdesk_record_publication_attempt(text, text, text, text, text)
    OWNER TO matchdesk_publication_guard_owner;

REVOKE ALL ON FUNCTION public.matchdesk_record_language_review(text, text, text, text, text, text),
    public.matchdesk_queue_publication(text, text, text, text, jsonb, text, text, integer),
    public.matchdesk_begin_publication_attempt(text, text),
    public.matchdesk_record_publication_attempt(text, text, text, text, text)
    FROM PUBLIC;

GRANT USAGE ON SCHEMA public TO matchdesk_publisher, matchdesk_language_reviewer;
GRANT EXECUTE ON FUNCTION public.matchdesk_record_language_review(text, text, text, text, text, text)
    TO matchdesk_language_reviewer;
GRANT SELECT ON public.matchdesk_language_reviews TO matchdesk_language_reviewer;
GRANT EXECUTE ON FUNCTION
    public.matchdesk_queue_publication(text, text, text, text, jsonb, text, text, integer),
    public.matchdesk_begin_publication_attempt(text, text),
    public.matchdesk_record_publication_attempt(text, text, text, text, text)
    TO matchdesk_publisher;
GRANT SELECT ON public.matchdesk_publication_outbox TO matchdesk_publisher;

COMMIT;
