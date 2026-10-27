# ID3J real PostgreSQL read-only catalog gate — 11 October 2026

**Status: TESTED — restricted, disposable PostgreSQL catalog inspection only.**
This is a source-bound qualification of a non-executing privilege-inspection
slice. It does not certify an authenticated live execution host, human identity
provider, customer tenant, migration provenance, restore recovery, or deployment.

## Exact tested source and required hosted gates

Qualified [development source `22e25bd2f19d98357751b0b110ee30d999b54867`](https://github.com/GOkwori/matchdesk/commit/22e25bd2f19d98357751b0b110ee30d999b54867).

| Gate | GitHub Actions run | Outcome |
| --- | --- | --- |
| Foundation CI | [38164404494](https://github.com/GOkwori/matchdesk/actions/runs/38164404494) | **PASS** — 1,099 Python 3.12.15 tests, 96.11% package coverage, 100% ID3J module coverage (29 statements, two branches); Ruff lint/format, strict mypy, frontend checks |
| Foundation integration | [38164404479](https://github.com/GOkwori/matchdesk/actions/runs/38164404479) | **PASS** — real disposable PostgreSQL ID3J positive/negative/restore checks, previous ID3H/ID3G regressions, 24 Chromium tests, and independent native image verdict |
| Source security | [38164404495](https://github.com/GOkwori/matchdesk/actions/runs/38164404495) | **PASS** — history-secret, Python CodeQL and JavaScript/TypeScript CodeQL jobs |
| Dependency audit | [38164404507](https://github.com/GOkwori/matchdesk/actions/runs/38164404507) | **PASS** |

The hosted integration log includes two separate
`MATCHDESK_ID3J_CATALOG_READ_ONLY_PASS` receipts and
`MATCHDESK_ID3J_REAL_POSTGRESQL_NEGATIVE_PASS`, on the same exact source.
The 24 browser tests completed without retrying failures away. A passing scan
does not guarantee that there are no vulnerabilities.

## Qualified implementation and negative cases

- The workflow provisions an **isolated, disposable** PostgreSQL database
  `matchdesk_id3j_ci`; it does not use the existing customer data as a target.
  A freshly generated, masked CI password creates a dedicated
  `matchdesk_id3j_reader_ci` login with no superuser, role creation,
  database creation, role inheritance, replication or RLS-bypass capability.
- The SQL catalog query reads current database, current/session role,
  `pg_roles`, role membership and effective database, schema, table,
  column, sequence and application-routine permissions. Its session is
  constrained with `SET TRANSACTION READ ONLY`.
- Every observed value is validated against an exact expected CI database,
  physical role and strict boolean flags. Unknown, unavailable, malformed
  or elevated observations **deny by default**.
- The disposable workflow demonstrates a successful baseline inspection,
  grants actual database `CREATE` capability as a negative probe,
  requires inspection to reject the elevated role, revokes that capability
  and requires a subsequent successful inspection.
- Python regressions exercise wrong physical role/database/session, excess
  grants, missing/invalid catalog rows, driver outage and the non-executing
  receipt: `execution_authorized=False` and
  `database_writes_authorized=False`.
- The query uses `CASE` guards around relation-kind-specific functions.
  SQL `WHERE` predicates alone cannot guarantee evaluation order.

This integration does **not** combine live database observations with the
synthetic ID3H/ID3I identities or establish trusted external tenant identity.
It is real PostgreSQL privilege evidence for **one isolated CI scope**, not
a tested production operator.

## Retained unsuccessful candidates — no waivers

- [3c4e85e](https://github.com/GOkwori/matchdesk/commit/3c4e85e4c10e97bf7fd781d410ac8fe301da3183):
  Foundation CI [38160520108](https://github.com/GOkwori/matchdesk/actions/runs/38160520108)
  failed Ruff import ordering; integration was cancelled.
- [1df663c](https://github.com/GOkwori/matchdesk/commit/1df663cf7d6771f95d81eab2df6bd95290115909):
  three gates passed; integration [38160804907](https://github.com/GOkwori/matchdesk/actions/runs/38160804907)
  correctly denied the initial real-database probe.
- [e77e836](https://github.com/GOkwori/matchdesk/commit/e77e836f89fadccf24a25ba4b4f3f2ce56769c59):
  integration [38162273202](https://github.com/GOkwori/matchdesk/actions/runs/38162273202)
  identified PostgreSQL `WrongObjectType` / SQLSTATE `42809`.
- [72c424e](https://github.com/GOkwori/matchdesk/commit/72c424e944eda54247f6d081fb8d75fd47a94955):
  integration [38163144909](https://github.com/GOkwori/matchdesk/actions/runs/38163144909)
  showed the exact error `"pg_statistic" is not a sequence`, arising
  because the SQL planner evaluated a sequence-only permission function
  against a non-sequence `pg_class` row.
- Source `22e25bd2f19d98357751b0b110ee30d999b54867` guards table/column and sequence probes using
  explicit kind-specific `CASE` expressions. All four hosted gates passed.

## Retained GitHub Actions artifacts

| Artifact | Artifact ID | GitHub-reported archive SHA-256 |
| --- | ---: | --- |
| `foundation-python-38164404494-1` | 11711297858 | `b1664aad70ff5243ce41d82bc65af3cd1afe6dab59ba2e6e388707c38ba71a77` |
| `foundation-web-38164404494-1` | 11711148463 | `f28f151420a83fc4527cceed99fa3ff1acc2d467df9c53706e1d56512a8f6ec9` |
| `integration-38164404479-1` | 11711148697 | `5fb8b65de35787a52935673faa706b7c3f3fed56c9b939c22416c125877cae61` |
| `image-security-verdict-38164404479-1` | 11711662314 | `c1148220b51a4d6440fa680dd78ae075d6f9f2567c5027e5ee3d6687ef23a038` |
| `history-secrets-38164404495-1` | 11711716851 | `7ae67df457667ee8b9ab77d1936c4f07d91d3f94c0fccc3d3d14abddbc75c63f` |
| `dependency-audit-38164404507-1` | 11711014340 | `5461407a9b74ab2dee8e32554ec712e740fcc8794787465c7456074f78a2e6f0` |

These archive hashes and identifiers were read from the GitHub Actions
artifact API. No independent archive download/re-hash is claimed.
Full retained artifacts, including source analysis and raw runtime evidence,
remain linked from their respective workflow runs.

## Remaining ID3J and release blockers

**Unqualified**: independent workforce/human authentication (including MFA),
workload federation/attestation, independently pinned server/cluster and
tenant/database identity, the exact source and migration provenance,
database privilege and target checks bound to a verified actor and a
fresh action-scoped approval at the mutation boundary, RTO/RPO and
independent restore acceptance, write-time replay-safe enforcement,
cost authorization, and complete customer/producer sandbox UAT.

The `TrustedReadOnlyHostContext` and `EvidenceBoundCIHostSource` are not
implemented as real live identity authorities; there is no real migration
executor or live action integration in this ID3J slice. A read-only
catalog receipt is never an execution capability. Prompts, model reasoning
and tool-supplied policy claims are not authorization boundaries.

**Never inferred from this PASS**: approval to execute any existing/customer/
production migration, enable providers, publish content, incur Azure spend,
deploy to production, or promote the protected `main` branch.
