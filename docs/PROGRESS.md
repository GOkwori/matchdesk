# Current progress

Date: 8 October 2026. Stage: Phase 1 in progress; Phase 1A synthetic engine TESTED.
Phase 0 gate: **VERIFIED / COMPLETED**.

The engineering foundation was merged through the protected `main` path and the
final post-merge source `773ba7cc2da60d14e5a1e3106b61fa202c93624b` passed all eight
required checks: foundation, web, runtime-browser, native-images, dependencies,
history-secrets, codeql-python and codeql-javascript-typescript. The dedicated
[Phase 0 closure record](evidence/phase0-closure-20261008.md) contains the exact
merge SHAs, workflow run IDs, controls and remaining boundaries.

## Phase 1 progress

P1-01, the deterministic synthetic match engine, is TESTED on development source
`3c8bd0299eb80a2553337a0d472d036e4114545a`. Four seeded normal scenarios and one
fault stream are implemented over the existing immutable `MatchEvent` contract.
The same scenario and seed produce identical bytes; different seeds change generated
content while preserving scenario rules. The fault stream keeps individual events
structurally valid while injecting duplicate, out-of-order, sequence-gap and reset
signals for later ingestion testing.

Hosted qualification passed Foundation CI, Dependency audit, Source security and
Foundation integration. Foundation CI ran 146 tests on Python 3.12.15 with 100% package
statement and branch coverage. See the
[Phase 1A qualification record](evidence/phase1a-synthetic-engine-20261008.md).

P1-02, ordered/idempotent ingestion and replay revision handling, is next.

## Historical native-image remediation before final qualification

Tested source: `c0e8f5c731e8688ceed37145e0f17c07b768df89`.
[Foundation CI 37765164071](https://github.com/GOkwori/matchdesk/actions/runs/37765164071)
passed 109 Python tests, unchanged schemas, static checks, 136 Python documentation
points and 59 document checks. TypeScript and the optimized web build passed.
The [integration run](https://github.com/GOkwori/matchdesk/actions/runs/37765163994)
passed nine real runtime groups and 24 Chromium cases, but failed the separate
native-images job. Dependency audit and source security passed on the same source.

This historical run introduced the gate that scans exact tested images with verified
scanner bytes and retains source/image/database identities, inventories and findings.
Thirty-one regression cases test its rejection paths. Removing unused pip/npm/Yarn/
Corepack from final service images reduced reported package/advisory occurrences from
1,078 to 1,010 using identical advisory data. At that point OS and PostgreSQL/gosu
findings remained and no exemption was applied. The database's next-update time was
already overdue at download. That failed verdict is retained as evidence; later
remediation and fresh qualification resolved the Phase 0 native-image blocker without
weakening the configured gate. See the
[native image report](evidence/native-image-remediation-20261008.md).

These numbers are occurrences, not distinct vulnerabilities or demonstrated exploits.
The all-severity policy remains strict, including unfixed and low-severity findings.
Any risk-policy change needs an explicit decision and evidence-backed dispositions.
[Repository controls](operations/repository-controls.md) reflect the approved
solo-maintainer policy. The live main ruleset is active with PR-only promotion,
strict required checks, resolved conversations, no bypass actors and history
safeguards. The final native-image gate is green on the Phase 0 main commit.

## Earlier foundation qualification

The foundation includes immutable version-1 contracts, strict synthetic-event
validation, content hashing, schema/health APIs, bounded request bodies, documented
boundary tests and a Next.js contract workbench. It is not the complete football
intelligence or editorial production application.

Earlier tested source: `e2ee20385f2d0da521dd9553eb5f9058d7b4b7e2`.
[Foundation CI 37758971639](https://github.com/GOkwori/matchdesk/actions/runs/37758971639)
passed 78 Python 3.12.15 tests, Ruff, formatting, strict mypy, schema snapshots,
117 Python documentation checks and 52 document checks. The implemented Python
package covered 250/250 statements and 70/70 branches with no exclusions. TypeScript
and the optimized Next.js build passed. These are foundation-only coverage results.

[Integration 37758971656](https://github.com/GOkwori/matchdesk/actions/runs/37758971656)
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

## Dependency and source-security remediation

The [earlier audit](evidence/dependency-audit-20261008.md) reported eight advisory IDs.
A coherent FastAPI/Starlette/AnyIO upgrade and pytest update now pass the
[dependency audit 37758971700](https://github.com/GOkwori/matchdesk/actions/runs/37758971700):
37 Python registry packages, no skips and zero known vulnerabilities; application and
browser-harness npm audits also report zero. HTTPX2 replaces the deprecated test client.
The first upgraded collection failure is retained; warnings remain errors.

[Source security 37758971691](https://github.com/GOkwori/matchdesk/actions/runs/37758971691)
passed CodeQL for Python and JavaScript/TypeScript with zero reported findings, and
history secret scanning with zero unresolved findings after 13 verified historical
file-digest classifications. CI recomputes every exception and detects a generated
non-working key control. No paths or rules are broadly excluded. See the
[qualification report](evidence/security-remediation-20261008.md) for measured scope,
artifact identities and retained failures; clean scans do not prove absence of risk.

## Approved solo-maintainer policy

George approved the solo-maintainer policy on 8 October 2026. The
[decision](decisions/ADR-0010-solo-maintainer-approval.md) removes the additional
approving-review requirement and last-push approval from the main import file.
It retains PR-only promotion, all eight checks, resolved conversations, no bypass
actors and history safeguards. Development remains the working branch.

Six new regression cases in `backend/tests/test_repository_policy.py` check the
versioned rule files. Their isolated local run passed on Python 3.13.5; that is not
hosted Python 3.12 qualification or live GitHub enforcement. The next hosted run
must execute these cases alongside the existing suite. No previous results above
are attributed to this policy change.

Exact-commit owner sign-off was obtained before the protected Phase 0 foundation
merge and again before the post-squash security remediation merge. The procedural
owner approval remains distinct from an additional GitHub approving review and does
not authorize automatic merging or deployment.

## Repository and release boundary

[PR #1](https://github.com/GOkwori/matchdesk/pull/1) is merged. The final Phase 0
`main` commit is `773ba7cc2da60d14e5a1e3106b61fa202c93624b`, after the narrowly
scoped post-squash history-secret repair in PR #14. Main and development protections
are active and independently read back through the repository ruleset API.

No release tag, live model execution, Azure resource provisioning or production
deployment is implied by Phase 0 closure. The isolated CI database and containers are
removed after testing; no ordinary local or production database was reset.

Screenshots remain inspection evidence rather than approved visual regression
baselines; three Chromium viewports are not cross-browser or full accessibility
qualification. Foundry agents, editorial publication, audience adaptation, Azure
deployment and live model evaluation remain later-phase work and must not be described
as operational before they are separately implemented and qualified.
