-- Publication outbox and language reviews. Defence in depth for backend/src/matchdesk/domain/publication.py:
-- the database enforces the same rules, so a bug or a bypass in the application cannot publish
-- unreviewed Spanish or French, let a producer publish their own approval, send twice, or rewrite
-- history. Targets disposable/local databases until the owner approves a hosted deployment.

CREATE TABLE IF NOT EXISTS matchdesk_language_reviews (
    review_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id text NOT NULL CHECK (length(btrim(tenant_id)) BETWEEN 1 AND 96),
    content_digest text NOT NULL CHECK (content_digest ~ '^[a-f0-9]{64}$'),
    language text NOT NULL CHECK (language IN ('es', 'fr')),
    verdict text NOT NULL CHECK (verdict IN ('approved', 'changes_requested')),
    reviewer_actor_id text NOT NULL CHECK (length(btrim(reviewer_actor_id)) BETWEEN 1 AND 128),
    note text NOT NULL DEFAULT '' CHECK (length(note) <= 500),
    reviewed_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS matchdesk_language_reviews_lookup
    ON matchdesk_language_reviews (tenant_id, content_digest, language, review_id DESC);

CREATE TABLE IF NOT EXISTS matchdesk_publication_outbox (
    publication_id text PRIMARY KEY CHECK (publication_id ~ '^[a-f0-9]{64}$'),
    tenant_id text NOT NULL CHECK (length(btrim(tenant_id)) BETWEEN 1 AND 96),
    binding_json jsonb NOT NULL CHECK (
        jsonb_typeof(binding_json) = 'object'
        AND binding_json->>'language' IN ('en', 'es', 'fr')
        AND binding_json->>'content_digest' ~ '^[a-f0-9]{64}$'
    ),
    destination text NOT NULL CHECK (destination IN ('match_centre', 'social', 'broadcast_overlay')),
    producer_actor_id text NOT NULL CHECK (length(btrim(producer_actor_id)) BETWEEN 1 AND 128),
    publisher_actor_id text NOT NULL CHECK (length(btrim(publisher_actor_id)) BETWEEN 1 AND 128),
    reviewer_actor_id text CHECK (reviewer_actor_id IS NULL OR length(btrim(reviewer_actor_id)) BETWEEN 1 AND 128),
    status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'failed', 'delivered', 'abandoned')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 10),
    last_error text CHECK (last_error IS NULL OR length(last_error) <= 500),
    receipt text CHECK (receipt IS NULL OR length(receipt) <= 200),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    -- Four eyes: whoever releases content is not the producer who approved it.
    CONSTRAINT matchdesk_outbox_second_person CHECK (publisher_actor_id <> producer_actor_id),
    -- Non-English content names the person who reviewed its language.
    CONSTRAINT matchdesk_outbox_reviewed_language CHECK (
        binding_json->>'language' = 'en' OR reviewer_actor_id IS NOT NULL
    ),
    CONSTRAINT matchdesk_outbox_receipt_when_delivered CHECK (
        (status = 'delivered') = (receipt IS NOT NULL)
    )
);

-- Insert: Spanish or French needs the LATEST review of this exact content to be an approval by
-- the named reviewer.
CREATE OR REPLACE FUNCTION matchdesk_outbox_require_review()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    latest matchdesk_language_reviews%ROWTYPE;
BEGIN
    IF NEW.status <> 'queued' OR NEW.attempts <> 0 OR NEW.receipt IS NOT NULL THEN
        RAISE EXCEPTION 'A publication starts queued, unattempted and without a receipt';
    END IF;
    IF NEW.binding_json->>'language' IN ('es', 'fr') THEN
        SELECT * INTO latest FROM matchdesk_language_reviews
        WHERE tenant_id = NEW.tenant_id
          AND content_digest = NEW.binding_json->>'content_digest'
          AND language = NEW.binding_json->>'language'
        ORDER BY review_id DESC LIMIT 1;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'Content needs a recorded language review';
        END IF;
        IF latest.verdict <> 'approved' OR latest.reviewer_actor_id <> NEW.reviewer_actor_id THEN
            RAISE EXCEPTION 'The latest language review does not approve this content';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS matchdesk_outbox_review_gate ON matchdesk_publication_outbox;
CREATE TRIGGER matchdesk_outbox_review_gate
BEFORE INSERT ON matchdesk_publication_outbox
FOR EACH ROW EXECUTE FUNCTION matchdesk_outbox_require_review();

-- Update: only delivery bookkeeping may change, one attempt at a time, and terminal rows are final.
CREATE OR REPLACE FUNCTION matchdesk_outbox_guard_transition()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.status IN ('delivered', 'abandoned') THEN
        RAISE EXCEPTION 'A % publication is final', OLD.status;
    END IF;
    IF NEW.publication_id <> OLD.publication_id OR NEW.tenant_id <> OLD.tenant_id
       OR NEW.binding_json <> OLD.binding_json OR NEW.destination <> OLD.destination
       OR NEW.producer_actor_id <> OLD.producer_actor_id OR NEW.publisher_actor_id <> OLD.publisher_actor_id
       OR NEW.reviewer_actor_id IS DISTINCT FROM OLD.reviewer_actor_id OR NEW.created_at <> OLD.created_at THEN
        RAISE EXCEPTION 'Only delivery status may change';
    END IF;
    IF NEW.status NOT IN ('failed', 'delivered', 'abandoned') THEN
        RAISE EXCEPTION 'An attempt ends failed, delivered or abandoned';
    END IF;
    IF NEW.attempts <> OLD.attempts + 1 THEN
        RAISE EXCEPTION 'Each update records exactly one delivery attempt';
    END IF;
    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS matchdesk_outbox_transition ON matchdesk_publication_outbox;
CREATE TRIGGER matchdesk_outbox_transition
BEFORE UPDATE ON matchdesk_publication_outbox
FOR EACH ROW EXECUTE FUNCTION matchdesk_outbox_guard_transition();

-- Nothing is deleted or truncated: reviews and publications are the audit trail.
CREATE OR REPLACE FUNCTION matchdesk_block_publication_history_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'MatchDesk publication history is append-only';
END;
$$;

DROP TRIGGER IF EXISTS matchdesk_outbox_no_delete ON matchdesk_publication_outbox;
CREATE TRIGGER matchdesk_outbox_no_delete
BEFORE DELETE OR TRUNCATE ON matchdesk_publication_outbox
FOR EACH STATEMENT EXECUTE FUNCTION matchdesk_block_publication_history_mutation();

DROP TRIGGER IF EXISTS matchdesk_reviews_immutable ON matchdesk_language_reviews;
CREATE TRIGGER matchdesk_reviews_immutable
BEFORE UPDATE OR DELETE OR TRUNCATE ON matchdesk_language_reviews
FOR EACH STATEMENT EXECUTE FUNCTION matchdesk_block_publication_history_mutation();
