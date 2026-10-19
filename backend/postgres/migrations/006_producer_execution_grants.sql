-- DEV/CI-only P3-05 execution-grant schema. Not a live identity bootstrap.
-- Only a separately trusted issuer may insert grants or revoke them.
-- A restricted writer needs SELECT and UPDATE(consumed_at), never issuance rights.
CREATE TABLE IF NOT EXISTS matchdesk_producer_execution_grants (
    grant_id uuid PRIMARY KEY,
    tenant_id text NOT NULL CHECK (length(btrim(tenant_id)) BETWEEN 1 AND 96),
    actor_subject text NOT NULL CHECK (length(btrim(actor_subject)) BETWEEN 1 AND 128),
    actor_issuer text NOT NULL CHECK (length(btrim(actor_issuer)) BETWEEN 1 AND 256),
    action text NOT NULL CHECK (action IN ('create', 'edit', 'reverify', 'approve', 'reject')),
    session_id text NOT NULL CHECK (length(btrim(session_id)) BETWEEN 1 AND 96),
    output_id text NOT NULL CHECK (length(btrim(output_id)) BETWEEN 1 AND 96),
    expected_generation bigint NOT NULL CHECK (expected_generation >= 0),
    binding_digest text NOT NULL CHECK (binding_digest ~ '^[a-f0-9]{64}$'),
    issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    consumed_at timestamptz,
    CHECK ((action = 'create') = (expected_generation = 0)),
    CHECK (expires_at > issued_at AND expires_at <= issued_at + interval '5 minutes')
);

-- Never grant access through PUBLIC; ordinary case-writing roles are not issuers.
REVOKE ALL ON matchdesk_producer_execution_grants FROM PUBLIC;
