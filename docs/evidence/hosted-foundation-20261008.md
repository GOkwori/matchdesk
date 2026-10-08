# First passing hosted foundation qualification

Date: 8 October 2026. Scope: dependency reproduction, Python checks and frontend build.
Result for this scope: **PASS**. Overall Phase 0 / production release: **NOT CERTIFIED**.

## Source and execution identity

- Source: `c6de02db7ef268f9f144c8e108a0cb2e079e3111`.
- Tree: `87a4d7606bcfb81abb1c9a01292ab7d51a0bb096`.
- [Foundation CI run 37751376812](https://github.com/GOkwori/matchdesk/actions/runs/37751376812), attempt 1, PR-triggered.
- Python job: 113225162229. Web job: 113225162413. Both completed successfully.
- Python 3.12.15, Node 22.16.0, npm 10.9.2, uv 0.10.0.
- JUnit suite timestamp: 2026-10-08T08:40:35.884905+00:00; suite duration 0.814 seconds.

Documentation/setup follow-ups after this source do not retroactively change its
results. Future HEAD qualification must be confirmed by its own run.

## Observed outcomes

| Check | Result |
|---|---|
| Committed lock presence and locked Python sync | PASS |
| Python regression suite | 77 passed, 0 failures, 0 errors, 0 skipped |
| Implemented Python package statement coverage | 250 / 250 (100%) |
| Implemented Python package branch coverage | 70 / 70 (100%) |
| Schema drift | Snapshots match |
| Docstring presence | 115 definitions in 19 Python files; 0 missing |
| Documentation checks | 42 documents; 0 reported errors |
| Ruff | All checks passed |
| Formatter | 19 files already formatted |
| Strict mypy | No issues in 7 source files |
| TypeScript with declaration-file checking | PASS |
| Next.js 16.4.0 optimized build | PASS; / and /_not-found prerendered |

The formatter-suggestion step was correctly skipped because no lint/format failure
occurred. It is a diagnostic artifact producer, not a skipped acceptance test.
The compile-only platform-types regression includes positive and negative assertions.
No coverage number above applies to future football or AI capabilities.

## Artifact integrity and retention

The actual archives were downloaded through the GitHub connection, checked against
GitHub's digests and inspected. Each source-commit.txt matched the source above.

| Artifact | ID | SHA-256 |
|---|---|---|
| foundation-python-37751376812-1 | 11537792406 | `9b44156973dbebc41bd8e5e071662a81e25dab02a3d50121dc046bf75074ff44` |
| foundation-web-37751376812-1 | 11537707823 | `72bd50f5e64ae22a2a94dd38523efd7968f38c5d56ed93e972137f2751d4166f` |

The Python archive contains JUnit, coverage JSON, lint/format/type logs, documentation
checks and dependency/source identities. The web archive contains installation,
type-check/build logs and source/dependency identities. This run used 30-day artifact
retention, expiring 7 November 2026. Subsequent runs use 60 days to extend through
judging; this report remains committed permanently. Archive hashes do not certify
security or correctness beyond the actual checks performed.

## Failures retained and corrected

[Run 37750545499](https://github.com/GOkwori/matchdesk/actions/runs/37750545499) on
`56b708990dd748649da5cc44f9f099f78a940aaf` failed before collecting tests because
Starlette 0.50.0 used an AnyIO alias deprecated by 4.15.1. TypeScript 5.8.3 could not
resolve the URLPattern declarations emitted by Next.js. Ruff also found formatting
and import ordering differences. Strict mypy had passed independently. These were
real observed failures; they were not replaced by a fabricated passing report.

The [compatibility decision](../decisions/ADR-0005-build-compatibility.md) describes
AnyIO 4.13.0 and TypeScript 6.0.3, the retained strict gates and the reviewed formatter
patch. Resolver run 37751193507 reproduced all fourteen reviewed source hashes.

## Explicit exclusions

No browser acceptance, integrated Compose/PostgreSQL execution, production image
qualification, complete dependency security audit, branch protection, live Foundry
call, Azure deployment, production promotion or owner certification occurred in this
scope. npm reported no vulnerabilities in its install audit, but that is not a whole
application security assessment. Readiness remains intentionally unavailable.
