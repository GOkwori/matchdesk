# ID3H controlled migration and customer-authentication release gate

Status: **DEVELOPMENT REHEARSAL ONLY — LIVE EXECUTION BLOCKED**.
Baseline: 11 October 2026. This is an operator decision and evidence protocol,
not migration approval, an executable production runner or an authorization grant.

## Scope and explicit exclusions

The [federation architecture](../decisions/ADR-0011-federated-authentication.md)
separates customer accounts from privileged workforce identities. The default
FastAPI application deliberately mounts neither customer router. The `deploy`
Makefile target fails closed. Passing CI does not allow a real customer login,
cloud provisioning, a migration on any existing non-disposable database,
publishing, or a change to protected `main`.

The currently committed
[`005_customer_account_revocation.sql`](../../backend/postgres/migrations/005_customer_account_revocation.sql)
has Git blob `78c2403f528f42492472b921ef221ec3187cebde`. **It revokes
every previously unrevoked customer session each time it is run.** Reapplying
it in an existing environment is an irreversible sign-out event, not a harmless
idempotent migration. Do not blindly run it to create a missing receipt.

The [review-only guarded candidate](../../qualification/id3h/005_customer_account_revocation_once_REVIEW_ONLY.sql)
has Git blob `52e2f4c4730fc2ae12f8bae180a895f193d59784`.
The [legacy catalog preflight](../../qualification/id3h/legacy_catalog_preflight_REVIEW_ONLY.sql),
[backup/restore rehearsal](../../qualification/id3h/disposable_backup_restore.sh)
and [legacy clone rehearsal](../../qualification/id3h/disposable_legacy_receipt_reconciliation.sh)
are qualification material. They are **not approved deployment commands**.
Git blobs and green checks attest only to their stated testing scope; they do
not authenticate a real operator, target database or historical installation.

## Mandatory hold points

| Gate | Required independently inspectable evidence | Disposition |
| --- | --- | --- |
| Source identity | Exact intended commit and SQL SHA; all four workflows on that head with no skipped required steps | NOT YET RELEASE-AUTHORIZED |
| Target isolation | Approved tenant, environment, database identity, actual database role and minimum privileges; no production secrets in repository | BLOCKED |
| Historical provenance | Trusted migration history, execution timestamp, source SHA and operator/change record proving original 005 backfill completed in this exact database | BLOCKED |
| Catalog integrity | Read-only legacy preflight, five enabled correct triggers, owner/function definitions, no unauthorised EXECUTE or extra grants; independently reviewed output | DEVELOPMENT-TESTED, TARGET UNVERIFIED |
| Session impact | Pre/post counts, legal retention constraints, maintenance window, expected sign-outs, customer notice and incident response plan | BLOCKED |
| Backup and recovery | Recent encrypted backup identity and integrity, off-host isolation, exercised restore to an approved clone, measured and accepted RTO/RPO | DISPOSABLE REHEARSAL ONLY |
| Cost governance | Pricing and spending envelope for any new infrastructure, free alternatives, cleanup plan and explicit owner cost consent | NO PROVISIONING AUTHORIZED |
| Human decision | Explicit owner sign-off tied to exact source, target database fingerprint, migration mode, backup, timing and risk; independently enforced by trusted execution host | NOT GRANTED |
| Customer sign-in | Separate reviewed issuer/audience, External ID provider configurations, privacy, MFA/step-up, monitoring, negative-case UAT and rollback | NOT ACTIVATED |

No supplied spreadsheet, comment, prompt, model verdict, CI-generated receipt,
catalog match or editable JSON field may grant execution authority. A future
deployment runner must independently authenticate the operator, verify an
unexpired approval for the **same** action, target and source at execution,
and deny on provider, evidence or authorization outages. Approval is an
external trust boundary; this document cannot substitute for it.

## Operator decision path (non-executable)

1. **Classify the database:** new installation, proven legacy 005 installation
   without receipt, already receipt-protected, or uncertain. Unknown state is
   BLOCKED. Classify using trusted release history **and** direct read-only
   catalog inspection. A matching trigger/function fingerprint alone cannot
   establish that the old bulk revocation actually ran.
2. **Freeze and prepare:** approve a maintenance window and session policy;
   prevent new customer writes while reconciling; prepare backup, tested restore,
   cutover plan, customer communications, telemetry and a named incident owner.
   Set measured acceptable RTO/RPO rather than inferring values from CI.
3. **New installation:** do not use the repeatedly disruptive 005 file.
   Independently review the guarded candidate, migration privilege design,
   initial schema and safe migration ledger before designing a dedicated
   release artifact. A test on disposable PostgreSQL is not deployment sign-off.
4. **Proven legacy installation:** only when reliable *historical* evidence
   proves 005 already revoked pre-trigger sessions, qualify a receipt-only
   reconciliation against a restored clone. Recheck schema/role fingerprints,
   current session state, ledger absence and target identity under a common
   write-excluding transaction. Record exactly one receipt and verify that
   newly issued active sessions survive. The clone rehearsal demonstrates
   mechanics; it does not prove historical state in a separate database.
5. **Uncertain/compromised installation:** do not seed a receipt. Escalate for
   independent incident review. If an explicit decision requires a fresh
   revocation cutover, treat it as a disruptive migration with customer
   reauthentication, backup/restore plan and separate owner approval.
6. **Already protected installation:** verify ledger ownership/grants,
   immutable receipt policy, trigger integrity and expected active sessions.
   Do not invoke either backfill or reconciliation again.
7. **Execution boundary (future):** revalidate target and source just before
   mutation; require a tightly scoped operator role and an externally enforced
   human approval. Disallow runtime DB roles from editing migration receipts,
   creating DB roles, disabling triggers or replaying migrations. Disable on
   ambiguity, stale evidence, approval mismatch or competing operations.
8. **Post-change review:** compare pre/post inventory, verify security
   boundaries and new sessions without exposing tokens, monitor revocation and
   account failures, then document the exact command, approved change ID,
   immutable source and database evidence. Do not conflate HTTP liveness with
   readiness or identity-provider activation.

### Failure and recovery

Stop on *any* SQL error, concurrent-writer surprise, role/trigger change,
unexpected session count, incomplete backup, unknown prior 005 execution,
unapproved spend or missing human approval. Do not retry a failed deployment
blindly: repeating legacy 005 can invalidate newer sessions.

A database restore may reintroduce previously revoked bearer state. It must
never be used as an automatic "rollback" of a security revocation. Any restore
requires independent incident authority, reconciliation of post-backup changes
and a fresh account/session invalidation assessment before exposing traffic.
The CI restore proves data and trigger behavior on disposable clones only; it
does **not** measure service recovery time or authorise a production restore.

## Required private evidence record

Store the following in a protected, auditable release system, not this public
repository: source commit and SQL hashes; exact target/database fingerprint;
separately retrieved migration-history record; preflight object/grant
fingerprints; current session counts and expected invalidations; encrypted
backup identifier and independently reviewed restore results; RTO/RPO;
maintenance and incident plan; cost approval where applicable; scoped operator
and reviewer identities; human decision and its expiry; command transcript
with secrets redacted; and the post-change verification/cleanup record.

The **default outcome is BLOCKED** until a future independently authenticated
release workflow can enforce those controls. No auto-approval is generated by
a test, document or AI assistant.

## Development evidence and next decisions

The isolated workflow
[`integration.yml`](../../.github/workflows/integration.yml)
exercises ID3G revocation, the read-only legacy catalog, negative-case trigger
and privilege tampering, guarded replay refusal, a database backup/restore,
and receipt-only reconciliation on a disposable clone. Every run must be tied
to its own commit and independent CI results. These results cannot be applied
to an arbitrary existing customer database.

Before proposing any live provider configuration, independently assess the
per-provider methods in [ADR-0011](../decisions/ADR-0011-federated-authentication.md).
Google, Apple, Facebook, personal Microsoft, organisational Entra and local
email require separate sandbox acceptance and cost/privacy review; a unified
sign-in screen does not prove any provider is available.

**Next phase:** specify the trusted execution-host approval mechanism,
production-appropriate database privileges, independently verified historical
migration provenance, monitored release and restore acceptance. Each remains
outside the scope of the current development branch.
