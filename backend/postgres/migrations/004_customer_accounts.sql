-- ID3F: offline, operator-provisioned customer broker identity directory.
-- The runtime must receive SELECT-only rights, never INSERT/UPDATE/DELETE/DDL.
-- Explicit reviewed provisioning and account-linking audit are future gates.
-- No email, provider profile, roles, or raw access tokens are stored here.
CREATE TABLE IF NOT EXISTS matchdesk_customer_accounts (
    issuer text NOT NULL CHECK (length(issuer) BETWEEN 1 AND 512 AND issuer = btrim(issuer)),
    tenant_id text NOT NULL CHECK (length(tenant_id) BETWEEN 1 AND 96 AND tenant_id = btrim(tenant_id)),
    subject text NOT NULL CHECK (length(subject) BETWEEN 1 AND 256 AND subject = btrim(subject)),
    account_id text NOT NULL UNIQUE CHECK (
        length(account_id) BETWEEN 1 AND 128 AND account_id = btrim(account_id)
    ),
    state text NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'active', 'suspended')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (issuer, tenant_id, subject)
);
-- Account IDs cannot silently be shared across unrelated broker identities.
-- Deliberate linking will require a separate governed schema change and audit.
