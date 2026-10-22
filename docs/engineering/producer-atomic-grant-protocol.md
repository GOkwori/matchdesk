# Producer action-grant atomicity — design gate (P4 / Issue #61)

Status: **DESIGN / NOT IMPLEMENTED / NOT AUTHORIZED FOR LIVE WRITES**.

## Observed risk

In draft PR #89, the HTTP router calls `grants.authorize(...)` before the separate
`PostgresProducerCaseStore.create` or `replace_if_generation` transaction.
The existing PostgreSQL compare-and-swap and append-only audit tests protect case
versions, but cannot prove that a grant revoked after the Boolean decision is
still valid at the physical write. This is a time-of-check/time-of-use window.
No live Entra actor, workforce step-up verifier or grant issuer is qualified.

## Required execution protocol

A trusted host must issue an opaque, unpredictable, single-use grant whose durable
record binds *all* of the following: verified issuer and actor, tenant, session,
output ID, action, exact content/evidence/item-version binding, expected case
generation, issue time, expiry, revocation state and consuming command ID. Grant
payloads and bearer material must never be accepted from a browser as authority,
logged, reused, or returned in producer result receipts.

For a privileged create, edit, reverify, approve or reject, the trusted writer
must perform the following **inside one database transaction**:

1. Resolve an independently authenticated workload identity and check the
   database role; do not derive access from request headers or model text.
2. Lock the exact scope-bound grant row using `SELECT ... FOR UPDATE` (or a
   rigorously equivalent serializable conditional mutation) and verify issuer,
   actor, tenant, session, output, action, content/evidence binding, expected
   generation, expiry and non-revoked/non-consumed status. Fail closed on any
   missing or ambiguous field.
3. Perform the current case generation/digest compare-and-swap and insert the
   append-only audit entry. No write may proceed if the grant lock/check fails.
4. Mark the **same exact grant** consumed by the command identifier before commit.
   If case CAS or audit append fails, roll back the **entire** transaction, including
   grant consumption. Retried commands cannot commit twice.
5. Return a minimal receipt only after durable commit. Never interpret an
   intermediate model, UI, agent or host authorization flag as proof of commit.

Revocation and consumption must acquire the same grant row lock and use the same
database authority path. Revocation committed first => mutation denied. Mutation
committed first => later revocation cannot undo the committed action; this must
be represented honestly in audit evidence and UI. Expiry is checked against
database time inside the transaction, not client time. A provider grant refresh
must not silently supersede a revoked grant. Publication requires a **separate**
human-approved execution protocol and is not in scope here.

## Mandatory disposable qualification

Use only isolated PostgreSQL with scoped test principals and synthetic outputs.
Inject a deterministic barrier after initial authorization to cover:
- revoke-before-writer-lock; expired and already-consumed grants;
- wrong actor, tenant, session, action, output, digest and case generation;
- two concurrent writers racing the same grant and target;
- audit insertion fault/rollback, crash before commit and repeat after restart;
- revocation racing consumption in both lock orders; no forged HTTP identity.

For each case assert both the case generation/audit chain **and** grant state.
A claim of atomicity requires real database transaction evidence, not a mocked
resolver returning true or a detached unit test. Preserve exact source SHA,
run IDs and failures. Do not allow the restricted producer writer to bypass
grant checks using direct case DML: enforce this with database roles or an
audited narrowly scoped SECURITY DEFINER function with locked search_path
and independently reviewed privileges.

## Integration hold

The current PR #89 Boolean resolver plus separate store method **does not
implement** the above protocol. Treat it as default-disabled DEV scaffolding.
Do not enable real workforce mutations, merge a falsely 'fixed' grant claim,
or activate paid identity/model infrastructure based on this document alone.

Next implementation must be a separately reviewed migration, protected writer
adapter and executable real-Psycopg integration tests, followed by the secure
Next.js BFF and genuine Entra MFA/manual operator qualification.
