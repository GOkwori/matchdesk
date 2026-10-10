-- P3-05-ID3A: one-time, encrypted External ID OIDC login attempts.
-- Schema only; application role receives no DDL, DELETE or other-table rights.
-- Only SHA-256 state/binding digests and AES-256-GCM ciphertext reach storage.
-- No provider activation, live login, publishing or paid infrastructure.
CREATE TABLE IF NOT EXISTS matchdesk_oidc_login_attempts (
    state_hash text PRIMARY KEY CHECK (state_hash ~ '^[a-f0-9]{64}$'),
    binding_hash text NOT NULL CHECK (binding_hash ~ '^[a-f0-9]{64}$'),
    issuer text NOT NULL CHECK (length(btrim(issuer)) BETWEEN 1 AND 512),
    client_id text NOT NULL CHECK (length(btrim(client_id)) BETWEEN 1 AND 160),
    redirect_uri text NOT NULL CHECK (length(btrim(redirect_uri)) BETWEEN 1 AND 2048),
    issued_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    secret_iv bytea NOT NULL CHECK (octet_length(secret_iv) = 12),
    secret_ciphertext bytea NOT NULL CHECK (octet_length(secret_ciphertext) = 103),
    consumed_at timestamptz,
    CHECK (issued_at < expires_at AND expires_at <= issued_at + interval '5 minutes'),
    CHECK (consumed_at IS NULL OR consumed_at >= issued_at)
);
CREATE INDEX IF NOT EXISTS matchdesk_oidc_attempt_expiry
    ON matchdesk_oidc_login_attempts (expires_at)
    WHERE consumed_at IS NULL;
