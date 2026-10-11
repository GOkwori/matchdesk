# ID3K disposable dual-principal catalog binding — 11 October 2026

**Status: TESTED in offline/disposable CI only.**
No live identity provider, authenticator, workload federation, or independent
MFA assertion has been qualified. This source only verifies a synthetic
cryptographic inspection policy; it cannot execute migration or publishing
operations and is not a production or customer release permission.

## Exact qualified source and hosted evidence

Source commit: [`8d970252c71920edbb8fe96dd1a699b0cbc7fd60`](https://github.com/GOkwori/matchdesk/commit/8d970252c71920edbb8fe96dd1a699b0cbc7fd60).

| Gate | Exact-source GitHub Actions run | Outcome |
| --- | --- | --- |
| Foundation CI | [38165623514](https://github.com/GOkwori/matchdesk/actions/runs/38165623514) | **PASS** — 1,123 Python 3.12.15 tests, 95.84% package coverage, Ruff lint/format, strict mypy, web build |
| Foundation integration | [38165623452](https://github.com/GOkwori/matchdesk/actions/runs/38165623452) | **PASS** — existing real disposable PostgreSQL ID3J read-only/elevation-denial/recovery, 24 browser tests and independent native-image verdict |
| Source security | [38165623486](https://github.com/GOkwori/matchdesk/actions/runs/38165623486) | **PASS** — history-secrets and Python/JavaScript-TypeScript CodeQL jobs |
| Dependency audit | [38165623494](https://github.com/GOkwori/matchdesk/actions/runs/38165623494) | **PASS** |

New `id3k_principal_catalog_binding.py` has **85% measured coverage**
(80 statements, eight missed; 24 branches, eight partial). This is not
100% ID3K coverage and is not a claim of complete threat coverage.
The 24 additional Python test cases exercised this new offline scope;
global coverage is **95.84%**.

## Verified synthetic-only controls

- A pinned, concrete single-tenant workforce issuer, separate human and
  app-only audience and client allowlists, bounded JWT issue/not-before/
  expiry checks, RSA/RS256 public-key signature verification, and rejection
  of token-supplied key URLs or unexpected signing headers.
- Two distinct principals: one *delegated* human token carrying a
  `MatchDesk.Catalog.Inspect` scope, and one app-only workload token with
  the exact synthetic `MatchDesk.Catalog.ReadOnly` role; cross-audience,
  client and identity substitution is denied.
- A **signed test `amr` claim containing `mfa`** is required for the
  delegated human. This test checks a token claim; it does *not* validate
  real Entra conditional-access enforcement, MFA session age or strength.
- A separate host-supplied `InspectionEntitlements` resolver is checked
  before and after inspection. Signed token claims alone do not supply
  read-only inspection rights.
- ID3K calls the ID3J catalog inspector twice and checks stable identity
  and catalog observations. ID3J's read-only session and exact disposable
  database/physical-role checks remain independently tested with actual
  PostgreSQL in the existing integration workflow.
- The ID3K unit regressions **mock the SQL cursor**, using new, temporary
  RSA keys. No test has authenticated real Entra identities *and* bound
  them to the same actual PostgreSQL session. A green ID3J integration
  job is not evidence of this combined capability.
- The `IdentityBoundCatalogReceipt` explicitly sets
  `execution_authorized=False` and
  `database_writes_authorized=False`. No execution callback, tool
  permission, SQL write or HTTP authentication route was activated.

Offline negative cases cover incorrect issuers/audiences/tenant/clients,
missing scope, absent MFA assertion, expired or overlong grants,
delegation/workload confusion, forged RSA signatures, missing or revoked
host entitlements, excessive database grants and invalid policy.

## Retained failed candidate — not waived

Commit [`ed9b1dc22760d80107d17d164e9c661c64d634d1`](https://github.com/GOkwori/matchdesk/commit/ed9b1dc22760d80107d17d164e9c661c64d634d1)
passed 1,123 Python tests, Python lint, strict typing, dependency audit and
source-security checks, but Foundation CI
[38165261488](https://github.com/GOkwori/matchdesk/actions/runs/38165261488)
**failed Ruff formatting** in the two ID3K files. Its integration run was
cancelled when a newer development push superseded that SHA. The precise
pinned Ruff formatting suggestion was committed without authorization
logic changes in `8d97025`. All four workflows then passed on that
new source, and neither the earlier failure nor cancellation is recast as
a successful qualification.

## GitHub Actions artifact references

The following artifact hashes are **GitHub-reported archive digests**;
they were read via the GitHub Actions API but were not independently
downloaded and byte-for-byte rehashed.

| Artifact | Artifact ID | GitHub-reported SHA-256 |
| --- | ---: | --- |
| `foundation-python-38165623514-1` | 11712321110 | `3e8bd5ba26bc0b4fb97b71c5a410457510e2c7cf332c5b3bd8e4382622aa42d1` |
| `foundation-web-38165623514-1` | 11711384861 | `0b191f279eb59e3c697325a6764c99007490ca46169b73dd38479f2ec893de06` |
| `integration-38165623452-1` | 11711619557 | `1f0f569e8970ac40f8aac46537786f0e5188a0e6e3ace5ca09860590f374bd6e` |
| `image-security-verdict-38165623452-1` | 11712081582 | `1fbedc520f062c87215089afa945b242e844e8b99b75a81362c646d808b3153d` |
| `history-secrets-38165623486-1` | 11711634356 | `ffc48039b23ee556ea7066fa1919f338ee03f526c343dce6f96e86fb32bd7fe6` |
| `dependency-audit-38165623494-1` | 11711369858 | `b80e11279b245c3fa9e503085e7089d43f211360ad0bf505ada04562f0e7742d` |

Artifacts and detailed CI job logs remain accessible from their linked
workflow runs, subject to the GitHub retention policy.

## Outstanding trust and release boundaries — BLOCKED

The CI key resolver is not a live JWKS/identity-trust service. The
workload token is not independently federated; the signed MFA assertion
is not independently proven by a live workforce authority; server grants
are synthetic; the database connection is supplied by a fixture at
the ID3K unit boundary. Neither ID3K nor ID3J checks a trusted exact
live cluster/tenant attestation, hardware-backed workload identity,
complete source and migration provenance or a real actor-approved
mutation boundary. The ID3K JWT `jti` is not backed by a replay ledger;
read-only inspection alone never permits mutation.

Before any protected production/customer action: independently verify
human and workload identities including MFA and session validity;
bind a real database/cluster and actual grants to the same protected
host actor; obtain authoritative source/migration/backup evidence,
atomic replay-resistant action-specific human authorization and immutable
audit; qualify restore/RTO/RPO; review costs and rollback; and run
separate sandbox UAT with explicit human approval.

**Still prohibited:** migrating existing/customer/production databases,
activating production/customer sign-in providers, publishing,
cloud expenditure, main promotion or treating any CI receipt as an
execution grant.
