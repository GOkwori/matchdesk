# Current progress

Date: 8 October 2026. Stage: Phase 0. Overall gate: **BLOCKED, not certified**.
Foundation build and built-runtime/browser checks: **PASS for the recorded scope**.
Dependency advisory audit: **FAIL; Python remediation required**.

## Implemented and tested

The foundation includes immutable version-1 contracts, strict synthetic-event
validation, content hashing, schema/health APIs, bounded request bodies, documented
boundary tests and a Next.js contract workbench. It is not the complete football
intelligence or editorial production application.

Tested source: `15996afa3219020c44dc1ff8f353e87d93e921e6`.
[Foundation CI 37755579407](https://github.com/GOkwori/matchdesk/actions/runs/37755579407)
passed 77 Python 3.12.15 tests, Ruff, formatting, strict mypy, schema snapshots,
115 Python documentation checks and 47 document checks. The implemented Python
package covered 250/250 statements and 70/70 branch opportunities. TypeScript and the
optimized Next.js build passed. These are foundation-only coverage results.

[Integration 37755579408](https://github.com/GOkwori/matchdesk/actions/runs/37755579408)
passed nine runtime groups and 24 Chromium browser cases across three viewport sizes.
The actual standalone web server forwards to the API. Invalid input, oversized bodies,
keyboard operation, controlled transport failures and stale-response handling are tested.
Database probes established commit/rollback, uniqueness, password enforcement and row
survival after a container restart. API restart recovery also passed. Application event
persistence, database migrations and backup restoration are not implemented or qualified.

## Corrections and retained evidence

The earlier compatibility work and local Python 3.13.5 results remain historical
records. The [evidence index](evidence/INDEX.md) distinguishes each source and execution.
Normal setup reproduces genuine committed Python/npm locks; deliberate resolution is
separate. Temporary candidate-resolution workflows have been removed.

The first runtime attempt exposed trusted PostgreSQL loopback TCP and an ambiguous
browser error locator. New database volumes now initialise TCP authentication with
SCRAM; the negative-password assertion remains. Existing volumes are not automatically
changed or deleted. Browser assertions now target the named result panel rather than
Next's independent route announcer. A revision guard prevents a delayed validation
response from accepting edited input. Failed artifacts and the fixes remain documented.

## Security blocker

[Dependency audit 37755579414](https://github.com/GOkwori/matchdesk/actions/runs/37755579414)
reported eight distinct advisory IDs in AnyIO 4.13.0, Starlette 0.50.0 and pytest 9.0.2.
Application and browser-harness npm audits reported zero known vulnerabilities.
The [audit record](evidence/dependency-audit-20261008.md) preserves affected versions,
scanner-reported fixes and the required compatible upgrade/retest sequence. No
advisories are ignored, and a green functional run does not override this failure.

## Repository and release boundary

[PR #1](https://github.com/GOkwori/matchdesk/pull/1) remains a draft. `main` remains the
licence-only bootstrap `d8e8d7eb0473f24399e3771e0bea36449c4d4502`. Both branches were
last observed unprotected. No merge, release tag, live model use, Azure resource or
owner release approval has occurred. The disposable CI database and containers were
removed after testing; no ordinary local or production database was reset.

## Remaining Phase 0 work

First resolve the Python advisories using a compatible framework/dependency upgrade
and rerun all three workflows. Then complete image/OS scanning, secret scanning,
static application security analysis, repository protections and the remaining phase
review. Screenshots are inspection evidence, not approved visual regression baselines;
three Chromium viewports are not cross-browser or full accessibility qualification.
The simulator, football analytics, Foundry agents, editorial publication and audience
adaptation remain future implementation. No next-phase certification is recorded.
