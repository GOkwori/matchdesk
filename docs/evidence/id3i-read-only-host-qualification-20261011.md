# ID3I disposable read-only execution-host preflight — 11 October 2026

**Status: TESTED for synthetic, offline/disposable CI only.**
This qualification establishes a *non-executing preflight contract*, not an
independently authenticated live execution host, trusted SQL privilege verifier,
production customer authentication, migration approval, or deployment authority.

## Exact qualified source and hosted checks

**Source:** [development cbb384528fe31f0e392359a3fcc48a30cea22821](https://github.com/GOkwori/matchdesk/commit/cbb384528fe31f0e392359a3fcc48a30cea22821)

| Required gate | Source-bound hosted run | Result |
| --- | --- | --- |
| Foundation CI | [38156941471](https://github.com/GOkwori/matchdesk/actions/runs/38156941471) | PASS; 1,074 Python 3.12.15 tests, 96.08% total coverage, contract/document checks, Ruff lint/format, strict mypy, frontend typecheck/build |
| Foundation integration | [38156941472](https://github.com/GOkwori/matchdesk/actions/runs/38156941472) | PASS; runtime/browser and native-images jobs |
| Source security | [38156941497](https://github.com/GOkwori/matchdesk/actions/runs/38156941497) | PASS; history-secret and both Python/JavaScript-TypeScript CodeQL jobs |
| Dependency audit | [38156941475](https://github.com/GOkwori/matchdesk/actions/runs/38156941475) | PASS |

The new ID3I module measured **100% statement and branch coverage**
(58 statements and eight branches, none missed) under this exact run.
The Python suite reported **1,074 passed** and the pinned formatter reported
108 formatted files. All listed jobs completed with a success conclusion;
a green workflow does not prove the absence of vulnerabilities.

## Implemented and exercised trust controls

- The disposable read-only preflight requires an evidence-bound ID3H CI source,
  the durable CI-only single-use approval store and a separate host context.
  Caller-supplied objects and arbitrary reservation-store implementations are
  rejected at construction for these guarded dependencies.
- The human operator and workload identities must be well-formed and distinct,
  the workload must match the observed release operator, and the approved
  action/environment remains restricted to ID3H disposable reconciliation.
- The **observed** target database fingerprint and workload identifier must
  match the release facts. The CI role name is restricted to a synthetic
  catalog reader; the inspection flags require catalog reads allowed and data
  writes, role management and migration-receipt edits disallowed.
- The delegated ID3H verifier validates the short-lived, Ed25519-signed scope
  against a pinned public key, re-observes seven private evidence-file digests
  and consumes a durable one-use approval before returning.
- The distinct signed reviewer cannot be the operator. Source, human identity,
  catalog grants and observed target are rechecked after the approval is spent.
  Denials after consumption do **not** restore the approval for replay.
- The receipt explicitly has both execution_authorized=False and
  database_writes_authorized=False. There is no migration connection,
  SQL executor, production identity integration, activated customer route or
  deployment action in this ID3I module.

The 16 parameterized and ordinary new test cases exercise positive non-execution,
one-use replay rejection, seven excessive/mismatched role or target conditions,
three invalid/colliding human identities, self-review, two post-consumption
identity/role drift cases, target drift and fake-dependency rejection.

## Retained unsuccessful candidate and precise repair

Source [e9f06127f2320935dc649532aba11c90308865eb](https://github.com/GOkwori/matchdesk/commit/e9f06127f2320935dc649532aba11c90308865eb)
ran [Foundation CI 38156767308](https://github.com/GOkwori/matchdesk/actions/runs/38156767308).
Its 1,074 tests, 96.08% coverage, lint and mypy passed, but the **overall
Foundation CI failed** because Ruff would reformat one invocation in
backend/tests/test_id3i_read_only_preflight.py. The hosted formatting suggestion
changed only that call's line wrapping. Source cbb3845 incorporated exactly
that formatting patch, without altering the ID3I security implementation.
The four required workflow groups then passed on the corrected source.

## Retained GitHub evidence artifacts (exact run)

| Artifact (run) | GitHub artifact ID | Reported archive SHA-256 |
| --- | ---: | --- |
| foundation-python-38156941471-1 | 11709185860 | adfd73f178f4b9b8feae649780381f10d8dbc8e41d84be22a9e26e527c62c34e |
| foundation-web-38156941471-1 | 11708686444 | 90ddcc65aac5249de7fbaedeea5a39b647df3e24ac3c54b652bdd4a317eef795 |
| integration-38156941472-1 | 11709025802 | 8763aedc8b4704a43f56026e4720779b77cb308c7b684d8f4f521ed2d1024f00 |
| image-security-verdict-38156941472-1 | 11708756395 | 18c4a9e8829411345af8eae8e6f73fdbf4b1b54c956b7c481cb1156168520f97 |
| history-secrets-38156941497-1 | 11708840819 | a5fdf3df7e5527b439e01bfc130860b7d52368acf81164ed8886906f850b3c64 |
| dependency-audit-38156941475-1 | 11708544382 | 59cff11ccb88670a89fff6e4979a375589c0df7e8ce56c0fd73571d75ff03005 |

The GitHub artifact API reported these digests and identifiers; this document
does not claim an independent archive download or byte-for-byte re-hash.
Full runtime logs and the remaining image-security/CodeQL artifacts are retained
in their linked GitHub workflow runs.

## Outstanding live security boundaries (BLOCKED)

**The CI context is a stub, not a real authentication or privilege authority.**
The synthetic human and workload observers, read-only catalog-access flags,
role name and database fingerprint have not been verified against a live
identity provider, federated workload attestation, or PostgreSQL system catalogs.
A real producer, customer, or migration operator cannot inherit these claims.

The historical ID3G/ID3H trust gaps remain: proof of prior migration 005 execution
in the *exact* database; exact source/SQL provenance; privilege inspection
under a real restricted role; independent restore acceptance and RTO/RPO;
immutable audit; cost approval; human reviewer authentication; and separately
enforced live, action-scoped execution authorization. A private CI file hash
cannot establish those external facts, and pre/post inspection is not an atomic
write-time authorization boundary.

A future, independently reviewed execution host must bind and revalidate
the genuine originating actor, workload, tenant/database, role and action at
the actual resource boundary, deny prompt/model/tool-supplied authorizations,
prevent replay and bypass, and fail closed on any outage or stale fact.
Real database mutation and live customer provider activation require their
own reviewed implementation, tests, human approval and cost governance.

**Not authorized:** migrations in existing/customer/production databases,
customer authentication activation, cloud spending, production deployment,
publishing, unrestricted agents or promotion to protected main.
