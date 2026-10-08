# Foundation dependency remediation and source-security qualification

Recorded: 8 October 2026. Tested source:
`e2ee20385f2d0da521dd9553eb5f9058d7b4b7e2`.

**Recorded build, integration, dependency and source-security scope: PASS.**
**Foundation merge and production release: not approved.** Native container/OS scans,
repository protections and final foundation review remain outstanding. This report is
a later documentation change, not the source commit that produced the results below.

## Executed workflows

| Workflow | Run, attempt 1 | Result |
|---|---|---|
| Foundation CI | [37758971639](https://github.com/GOkwori/matchdesk/actions/runs/37758971639) | PASS |
| Foundation integration | [37758971656](https://github.com/GOkwori/matchdesk/actions/runs/37758971656) | PASS |
| Dependency audit | [37758971700](https://github.com/GOkwori/matchdesk/actions/runs/37758971700) | PASS |
| Source security | [37758971691](https://github.com/GOkwori/matchdesk/actions/runs/37758971691) | PASS |

All four refer to the same commit above. Source identity was checked in the downloaded
artifacts, and each archive was checked against GitHub's reported SHA-256 digest.

## Dependency remediation

The earlier eight advisory IDs are preserved in the [failed audit](dependency-audit-20261008.md).
The current graph replaces FastAPI 0.128.2 with 0.142.4, Starlette 0.50.0 with 1.7.0,
AnyIO 4.13.0 with 4.15.1 and pytest 9.0.2 with 9.0.3. The supported test client is
HTTPX2 2.13.1 instead of legacy HTTPX 0.28.1. These are real resolver-produced lockfiles,
not forced dependency overrides or hand-written lock approximations.

[ADR-0007](../decisions/ADR-0007-patched-asgi-dependencies.md) records the decision.
The [first upgraded test run](asgi-upgrade-first-run-20261008.md) failed at collection
because the new Starlette client deprecated legacy HTTPX. That failure remains in the
record. The correction changes the test dependency and adds one explicit compatibility
regression; it does not filter warnings, patch the upstream client or relax assertions.

The completed audit inspected **37 locked Python registry packages**, with no skipped
packages and zero known vulnerabilities reported. Application and browser-harness npm
audits also reported zero known vulnerabilities. No advisory ignore list or automatic
forced fix was used. This closes the observed dependency findings on this scanned
candidate; it does not establish that unknown vulnerabilities cannot exist.

## Tests, builds and comments

Python 3.12.15 ran **78 tests**, with no failures, errors or skips. The previously tested
77 cases remain and one supported-client regression was added. The implemented Python
package covered 250/250 statements and 70/70 branches, with no excluded statements.
This is coverage of the current small foundation, not the planned football/AI product.

Ruff, formatting, strict mypy, unchanged schema snapshots and the optimized Next.js
build passed. The comment checker examined 117 definitions across 20 Python files
with no missing docstrings; 52 documentation checks passed. Human comment review
remains necessary because presence checks do not prove explanatory quality.

Nine real HTTP/container/PostgreSQL groups passed, from 09:47:35.786 to
09:47:49.117 UTC. They cover the existing runtime isolation, HTTP contract/limits,
same-origin forwarding, password enforcement, transaction/uniqueness checks, database
row survival after restart and API restart recovery. They are not application event
persistence, migration or backup-restoration tests.

The browser run began at 09:48:16.969 UTC and completed **24 cases with zero failures,
errors, skips or flaky cases**. The three profiles are desktop/tablet/mobile Chromium
viewports, not three browser engines. The suite includes controlled faults and the
stale-response/input-edit race. Retries remain disabled; screenshots are inspection
artifacts, not approved pixel baselines or a full accessibility audit.

## Static analysis and secret-scan review

CodeQL 2.27.1 ran the security-extended suite for Python and JavaScript/TypeScript.
Both SARIF reports contain zero findings. Extraction diagnostics and metrics show
actual analyzed code, not an empty result substituted for analysis. Query packs were
python-queries 1.8.11 and javascript-queries 2.4.6 with their full revisions retained
in SARIF. Uploading a result is not itself treated as a pass: a separate gate inspects
reported findings and fails if findings or invalid output are present.

Gitleaks 8.30.1 scanned 18 reachable commits and reported zero unresolved findings
after **13 individually verified historical digest classifications**. The initial
13 findings and failed scan are preserved in the
[classification record](secret-scan-classification-20261008.md). CI re-reads each exact
historical line and recomputes its documented source-file SHA-256 before generating
an exception. No path, extension or scanner rule is excluded wholesale. A generated,
non-working key outside the checkout was detected using the same exception file.
The synthetic control and all scanner output are redacted. This is not a claim that
all possible credential exposure has been ruled out.

## Verified retained artifacts

| Scope | Artifact ID | SHA-256 |
|---|---|---|
| Python | 11541163699 | `e58e7a0f74b4b50c36ebef156af93768b794316e74a9726d1b6bd06b3fcb76d9` |
| Runtime/browser | 11541556816 | `17d58dfc119af4249cf0e1951976062a92528dc63de4e6dd533af3d5fa8c5187` |
| Dependency audit | 11541650583 | `3d0bab2caab30126c8072ead40a9f7c4260c910a123d313da25a07ec3a50788b` |
| CodeQL Python | 11541347927 | `737695c893184c62edc7cdd4c982d6dcacc06344f905bcd3c24df284cb537481` |
| CodeQL JavaScript/TypeScript | 11540939562 | `e769beb6255f52cc72889b9595f144d59ede2cd304b059bcd7f23d94b6f6fe73` |
| History secrets | 11541102961 | `db75e5517492aa792bf1b204b370fd2486d486bc70ec9854c40d8f9cc6877949` |

Artifacts are retained through 7 December 2026; this summary remains in Git history.
Earlier passing patched-source runs 37757794897, 37757794926 and 37757794971 refer to
`fa1510a1f110ce97a606f83fbfa0c61e5e9a965c` and remain distinct earlier evidence.

## Merge boundary

The [foundation merge checklist](../operations/foundation-merge-checklist.md) separates
an engineering baseline from production release. The repository administration read
returned HTTP 403, so protections have not been configured by this work. `main` remains
`d8e8d7eb0473f24399e3771e0bea36449c4d4502` and PR #1 remains draft. No merge, release
tag, Azure resource, model call or owner release approval occurred. Runtime scans and
repository controls must be completed before presenting the foundation as merge-ready.
