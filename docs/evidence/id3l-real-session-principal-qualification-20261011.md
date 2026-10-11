# ID3L disposable PostgreSQL session / dual-principal binding — 11 October 2026

**Status: TESTED in a disposable CI database, with synthetic signed identities only.**
The qualification demonstrates an offline cryptographic identity/authorization
contract against the *same actual PostgreSQL connection*, **not** a deployed
identity provider, verified Entra MFA/workload federation, physical-cluster
attestation, customer migration approval, or mutation authority.

## Exact qualified implementation and hosted results

Qualified source: [`4004a3e54eb91bb080c2a89e7257b09ce860c3d8`](https://github.com/GOkwori/matchdesk/commit/4004a3e54eb91bb080c2a89e7257b09ce860c3d8).
All four required GitHub workflow groups completed successfully on that exact SHA:

| Required workflow | Exact-source Actions run | Outcome |
| --- | --- | --- |
| Foundation CI | [38166677483](https://github.com/GOkwori/matchdesk/actions/runs/38166677483) | **PASS** — 1,123 Python tests; 95.84% total package coverage; ID3K module at 85%; Ruff lint/format, strict mypy, frontend checks |
| Foundation integration | [38166677532](https://github.com/GOkwori/matchdesk/actions/runs/38166677532) | **PASS** — same real disposable PostgreSQL connection with synthetic human/workload identity binding, elevation denial and permission restoration; 36 Chromium tests; independent native-image security verdict |
| Source security | [38166677468](https://github.com/GOkwori/matchdesk/actions/runs/38166677468) | **PASS** — secret-history, Python CodeQL and JavaScript/TypeScript CodeQL |
| Dependency audit | [38166677556](https://github.com/GOkwori/matchdesk/actions/runs/38166677556) | **PASS** |

The Python total is unchanged from ID3K because the new ID3L test harness
runs inside the hosted *integration* workflow, not the unit suite. CI still
retains the failing-candidate history for ID3J/ID3K in their separate records.

## Real-session evidence, exact observable markers

In the `runtime-browser` job of Foundation integration 38166677532,
the `Qualify ID3J effective privileges on a real disposable PostgreSQL role`
step ran the ID3L harness and checked its output for these exact markers:

1. `MATCHDESK_ID3L_REAL_POSTGRESQL_DUAL_PRINCIPAL_PASS` — before elevation.
2. `MATCHDESK_ID3L_ELEVATED_ROLE_REJECTED` — after the **real CI
   database CREATE privilege** was granted to the physical read-only role.
3. `MATCHDESK_ID3L_REAL_POSTGRESQL_DUAL_PRINCIPAL_PASS` — after revocation
   and renewed inspection.

The existing independent ID3J checks also emitted two
`MATCHDESK_ID3J_CATALOG_READ_ONLY_PASS` markers and
`MATCHDESK_ID3J_REAL_POSTGRESQL_NEGATIVE_PASS`.

The same disposable `matchdesk_id3j_ci` database and restricted
`matchdesk_id3j_reader_ci` PostgreSQL login are used throughout that
workflow step, not a production target. The harness keeps its database
connection open with autocommit enabled while ID3K calls the ID3J
read-only catalog inspector twice. It checks `pg_backend_pid()`,
`current_database()`, `current_user` and `session_user` before and
after inspections, requiring the *same* backend session identity.

The harness creates **two separate disposable RSA private keys in memory**.
It signs short-lived delegated-human and app-only workload sample JWTs
under a synthetic exact-tenant issuer; a pinned in-process public-key
resolver checks the tokens. A synthetic host-owned entitlement resolver
must allow the inspected human; signed claims alone never confer access.
The human sample JWT includes a signed `amr` MFA *claim*, not independent
proof of actual user MFA or Conditional Access.

Actual negative integration probes require denial for revoked host
entitlement, entitlement revocation between the two checks, missing human
MFA claim, workload token presented to the human audience, an
attacker-signed JWT and a genuinely elevated PostgreSQL role.
The harness rechecks successfully after restoring the permitted state.
A denied probe only passes if it raises `ReleaseDenied`; an unrelated
database or Python exception cannot be quietly counted as an expected
authorization denial.

The `IdentityBoundCatalogReceipt` still states
`execution_authorized=False` and `database_writes_authorized=False`.
Neither the script nor ID3K adds a database migration executor,
publishing action, privileged HTTP route, or permission to mutate data.

## GitHub-retained artifact evidence

The following archive digest values and IDs are **as reported by GitHub
Actions**, not from an independently performed download or byte-for-byte
archive rehash.

| Artifact name | Artifact ID | GitHub-reported SHA-256 |
| --- | ---: | --- |
| `foundation-python-38166677483-1` | 11712791251 | `6a72d457dd9509a953982c1f27952723d634c631f4589cbd2264155d234fc8e7` |
| `foundation-web-38166677483-1` | 11712132616 | `41d2f430163eea1460966b5bd9a8290688243b7c8b079979335636419a9154d7` |
| `integration-38166677532-1` | 11712981075 | `2b5dca34f99f273e2b112a2b4c5437dc97386cd9a50cd4be4b6f469a6887ffa8` |
| `image-security-verdict-38166677532-1` | 11712891362 | `fd9124b887da6bbac45e3493fcfa83f1dfa45a6b2dec4478166dc72f8e6d4c0f` |
| `history-secrets-38166677468-1` | 11712387301 | `e4bfbb8c05b322226b30a74cb409836c65fe1ae82b6d90de528af8f7fe6d6762` |
| `dependency-audit-38166677556-1` | 11712272065 | `aeeb8dcf6a5aa47543bccaf47413a3e2207df5b38489d8a273bb1b90def750d8` |

The complete source-scanning and container-image inventories, runtime logs
and Chromium evidence remain attached to the linked workflow runs for
their configured retention window.

## Trust boundary and remaining blockers

This proves **real database catalog observations combined with independently
signed *synthetic* tokens inside one isolated CI process**. It does not
prove independent identity issuance, tenant lookup, hardware-backed or
federated workload attestation, real Entra sign-in, a fresh MFA policy
evaluation or an unforgeable origin binding between the app-only JWT
and the PostgreSQL connection. The host holds the keys and entitlement
fixture itself. The `jti` token claim is not backed by a real revocation
or replay ledger for these offline inspection tokens.

A live release requires the separately reviewed execution and identity
architecture: verified workload and human principals from independently
configured trusted sources; exact independently attested cluster and
tenant target; protected migration source/history and backup evidence;
repeatable recovery/RTO/RPO; fresh action-scoped single-use human approval;
least-privilege write-time authorization *enforced by the resource*
and auditable execution; explicit cost, rollback and operator sign-off.

Passing **ID3L does not qualify any existing/production/customer database
migration**, customer-provider activation, privileged producer mutation,
real publication, cloud expenditure, production deployment or `main`
promotion. All such actions remain **BLOCKED**.
