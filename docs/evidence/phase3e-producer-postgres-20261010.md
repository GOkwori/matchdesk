# Phase 3E — PostgreSQL producer-case integrity qualification

Date: 10 October 2026. Status: **TESTED: disposable SQL behaviour only**.

Qualified source: `207a2921b4fa634dcf22b598f3a98d83a51043b2` on `development`.
**No promotion to main, Azure resource, live service, paid model call or publishing permission.**

## Tested implementation

- `backend/postgres/migrations/001_producer_review.sql` defines tenant/session/output-scoped case and audit tables, generation constraints and append-only audit DML trigger.
- `backend/src/matchdesk/domain/postgres_producer_store.py` implements an immutable audit-digest and parameterised PostgreSQL transaction/CAS adapter using a host-supplied connection factory.
- `backend/tests/test_postgres_producer_store.py` exercises the adapter with a transactional fake (13 cases); it does not instantiate a real DB driver.
- `e2e/producer-store-postgres.mjs` adds eight real PostgreSQL checks within the existing disposable CI Compose project; failed check returns nonzero and retains `artifacts/integration/producer-store-postgres.json`.

## Exact-head hosted gates

| Required workflow | Run ID | Result |
|---|---:|---|
| Foundation CI | [38023985097](https://github.com/GOkwori/matchdesk/actions/runs/38023985097) | PASS |
| Dependency audit | [38023985161](https://github.com/GOkwori/matchdesk/actions/runs/38023985161) | PASS |
| Source security | [38023985199](https://github.com/GOkwori/matchdesk/actions/runs/38023985199) | PASS |
| Foundation integration | [38023985147](https://github.com/GOkwori/matchdesk/actions/runs/38023985147) | PASS |

Foundation CI: **464/464 Python tests passed**, strict Ruff lint/format and mypy checks, contract and documentation checks, and the frontend build passed. Python package coverage was **96.46%**; `producer_commands.py` reported **100%**, `postgres_producer_store.py` **98%** combined statement/branch measure. This is not separate measured function coverage.

The live disposable PostgreSQL step completed **8/8 PASS**, validating migration reapplication, initial transaction, generation CAS with audit, stale and foreign-tenant where-clause rejection, rollback after duplicate audit insert, immutable audit UPDATE/DELETE/TRUNCATE, two concurrent SQL writers with one winner, and surviving a real database-container restart. The browser checks, container/image inventory and independent native-image verdict passed on the same exact source.

## Security/operational limits

- The SQL smoke checks exercise real PostgreSQL statements, **not a live Python storage adapter connected through a pinned PostgreSQL driver**. The adapter's transactional methods are separately fake-tested.
- The database smoke uses the disposable database's owner credentials. Tenant isolation was tested in exact SQL predicates, **not PostgreSQL row-level security or least-privilege runtime-role enforcement**.
- The DML trigger blocks ordinary audit modifications, but a database owner can change its triggers and schema; immutable history is not independently signed or externally anchored.
- `HostVerifiedActor` is a host-verified-identity contract, **not** a token verifier. There is no OIDC issuer/audience/JWKS integration, authenticated producer API, durable production connection, backup/restore qualification, or HTTP publication adapter.
- `main` remains protected. No content publication, product readiness assertion or real user identity action was performed.

## Next qualification boundary

Add a reviewed/pinned PostgreSQL driver with a resolver-generated lock, provision least-privilege database connection roles in disposable tests, execute the **actual Python store** against PostgreSQL including network/transaction/restart behaviour, and integrate trusted OIDC validation under a separately reviewed issuer/audience/session policy. Keep producer mutation endpoints closed until these gates and human approval pass.
