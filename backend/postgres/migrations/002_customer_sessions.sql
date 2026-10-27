-- P3-05 customer sessions: only hashes of 256-bit session secrets are stored.
-- Apply in a disposable/reviewed database migration; no runtime role is granted here.
-- Production requires independent identity trust, protected cookie/CSRF controls,
-- row-access review, backup/restore evidence, monitoring and owner approval.
CREATE TABLE IF NOT EXISTS matchdesk_customer_sessions (
    token_hash text PRIMARY KEY CHECK (token_hash ~ '^[a-f0-9]{64}$'),
    issuer text NOT NULL CHECK (length(btrim(issuer)) BETWEEN 1 AND 512),
    tenant_id text NOT NULL CHECK (length(btrim(tenant_id)) BETWEEN 1 AND 96),
    subject text NOT NULL CHECK (length(subject) BETWEEN 1 AND 256),
    account_id text NOT NULL CHECK (length(btrim(account_id)) BETWEEN 1 AND 128),
    realm text NOT NULL DEFAULT 'customer' CHECK (realm = 'customer'),
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    last_seen_at timestamptz NOT NULL,
    revoked boolean NOT NULL DEFAULT FALSE,
    CHECK (created_at <= last_seen_at AND last_seen_at <= expires_at),
    CHECK (created_at < expires_at AND expires_at <= created_at + interval '8 hours')
);

CREATE INDEX IF NOT EXISTS matchdesk_customer_session_identity
    ON matchdesk_customer_sessions (issuer, tenant_id, subject)
    WHERE revoked = FALSE;
