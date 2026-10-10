# Phase 3F — restricted real Psycopg and audit reconciliation

Date: 10 October 2026. Status: **TESTED for isolated storage/audit security**.

Qualified implementation: `9c6cb30b53d5d1fc1186ff2a758db807057c4a99` on
`development`. No protected `main` promotion or production deployment.

## Scope

- A resolver-produced `psycopg[binary]==3.3.6` dependency lock and bounded host-owned connection factory.
- Actual Python `PostgresProducerCaseStore` through Psycopg against the disposable PostgreSQL service using an explicit restricted runtime role.
- Tenant/session/output-scoped case creation, read/reverification, optimistic compare-and-swap, append-only audit insertion and complete rollback on audit insertion failure.
- Two competing Python producer decisions: precisely one SQL CAS winner and one new audit entry.
- Reconnection and complete audit reconstruction after PostgreSQL restart.
- Restricted role rejects database DELETE, schema modification and owner-role impersonation.
- The storage load now reads cases and independent audit rows from one REPEATABLE READ transaction, validates every generation/entry/cumulative digest, and rejects missing, forged or unexpected audit entries.

The detached audit-table tampering negative path was tested in the actual disposable database. Five new unit cases cover analogous offline corruption. PostgreSQL owner can still modify tables/triggers; this is not cryptographic nonrepudiation or proof of secure production operation.

## Exact-source hosted verification

| Required group | Run | Verdict |
|---|---|---|
| Foundation CI | [38032825378](https://github.com/GOkwori/matchdesk/actions/runs/38032825378) | PASS |
| Dependency audit | [38032825394](https://github.com/GOkwori/matchdesk/actions/runs/38032825394) | PASS |
| Source security | [38032825398](https://github.com/GOkwori/matchdesk/actions/runs/38032825398) | PASS |
| Foundation integration | [38032825383](https://github.com/GOkwori/matchdesk/actions/runs/38032825383) | PASS |

Foundation CI ran **477/477 Python tests** with **96.7% aggregate package combined
statement/branch coverage**, displayed as 97% by coverage.py; the storage adapter measured **98%** and strict mypy, Ruff, docs/contract and frontend checks passed. The integration runner passed restricted real Psycopg operations, rollback/CAS, database restart, browser regressions and independent native-image security.

Historical failure: audit reconciliation candidate `f7447aa5cf1ea52642eaadba9397457b13e11dc6` passed 477 functional tests and strict typing but failed Ruff formatting; the reviewed nonfunctional correction was committed in `9c6cb30`. The earlier incorrect state-name assertion in `d53506b` was repaired without changing runtime semantics, before the passing source.

## Remaining governance gates

The `HostVerifiedActor` contract is **not OIDC authentication**. A server-owned allowlisted issuer/audience/client/tenant policy, signed access-token verification, trusted session-entitlement lookup, actor binding and authenticated producer command endpoint are not implemented. Entra app registration, signing metadata/JWKS rotation and real human identities require separate configuration and validation. Do not promote agent content or client-supplied role claims to publication authority. Publication delivery/outbox, security review, backup/restore and Phase 3 owner approval are still outstanding. P3-05 remains IN PROGRESS.
