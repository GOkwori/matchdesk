-- P3-05. This migration targets only the disposable/local database until approved.
-- Production still requires restricted DB roles, trusted OIDC and backup/restore evidence.
CREATE TABLE IF NOT EXISTS matchdesk_producer_cases (
    tenant_id text NOT NULL CHECK (length(btrim(tenant_id)) BETWEEN 1 AND 96),
    session_id text NOT NULL CHECK (length(btrim(session_id)) BETWEEN 1 AND 96),
    output_id text NOT NULL CHECK (length(btrim(output_id)) BETWEEN 1 AND 96),
    generation bigint NOT NULL CHECK (generation >= 1),
    case_json jsonb NOT NULL CHECK (jsonb_typeof(case_json) = 'object'),
    audit_digest text NOT NULL CHECK (audit_digest ~ '^[a-f0-9]{64}$'),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id, session_id, output_id)
);

CREATE TABLE IF NOT EXISTS matchdesk_producer_audit (
    tenant_id text NOT NULL,
    session_id text NOT NULL,
    output_id text NOT NULL,
    generation bigint NOT NULL CHECK (generation >= 1),
    entry_json jsonb NOT NULL CHECK (jsonb_typeof(entry_json) = 'object'),
    audit_digest text NOT NULL CHECK (audit_digest ~ '^[a-f0-9]{64}$'),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (tenant_id, session_id, output_id, generation),
    FOREIGN KEY (tenant_id, session_id, output_id)
        REFERENCES matchdesk_producer_cases (tenant_id, session_id, output_id)
        ON DELETE RESTRICT
);

-- Prevent ordinary application sessions from rewriting or deleting audit history.
-- A database owner can disable triggers; deploy with separate restricted roles.
CREATE OR REPLACE FUNCTION matchdesk_block_audit_mutations()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'MatchDesk producer audit is append-only';
END;
$$;

DROP TRIGGER IF EXISTS matchdesk_audit_is_immutable ON matchdesk_producer_audit;
CREATE TRIGGER matchdesk_audit_is_immutable
BEFORE UPDATE OR DELETE OR TRUNCATE ON matchdesk_producer_audit
FOR EACH STATEMENT EXECUTE FUNCTION matchdesk_block_audit_mutations();
