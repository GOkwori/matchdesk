# Current progress

Date: 8 October 2026. Stage: Phase 0. Overall gate: **BLOCKED, not certified**.
Foundation build, runtime/browser, dependency audit and source-security checks pass
for the recorded source. **Native image security fails** on remaining findings and
an overdue advisory-database refresh. The foundation has not been merged.

## Latest native-image and regression qualification

Tested source: `c0e8f5c731e8688ceed37145e0f17c07b768df89`.
[Foundation CI 37765164071](https://github.com/GOkwori/matchdesk/actions/runs/37765164071)
passed 109 Python tests, unchanged schemas, static checks, 136 Python documentation
points and 59 document checks. TypeScript and the optimized web build passed.
The [integration run](https://github.com/GOkwori/matchdesk/actions/runs/37765163994)
passed nine real runtime groups and 24 Chromium cases, but failed the separate
native-images job. Dependency audit and source security passed on the same source.

The new gate scans the exact tested images with verified scanner bytes and retains
source/image/database identities, inventories and findings. Thirty-one regression
cases test its rejection paths. Removing unused pip/npm/Yarn/Corepack from final
service images reduced reported package/advisory occurrences from 1,078 to 1,010
using identical advisory data. OS and PostgreSQL/gosu findings remain; no exemption
has been applied. The database's next-update time was already overdue at download.
The verdict now exposes both causes rather than hiding findings behind the freshness
error. See the [native image report](evidence/native-image-remediation-20261008.md).

These numbers are occurrences, not distinct vulnerabilities or demonstrated exploits.
The all-severity policy remains strict, including unfixed and low-severity findings.
Any risk-policy change needs an explicit decision and evidence-backed dispositions.
[Repository-control files](operations/repository-controls.md) are prepared but not
activated; the two-branch policy and independent-review requirement need owner review.

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

## Repository and release boundary

[PR #1](https://github.com/GOkwori/matchdesk/pull/1) remains a draft. `main` remains the
licence-only bootstrap `d8e8d7eb0473f24399e3771e0bea36449c4d4502`. Both branches were
last observed unprotected and the administration read returned 403. No merge, release
tag, live model use, Azure resource or owner release approval has occurred. The
isolated CI database and containers are removed after testing; no ordinary local or
production database was reset.

## Remaining Phase 0 work

Remediate and disposition the remaining native-image findings, refresh advisory data,
activate reviewed repository protections and complete the final foundation review
using the [merge checklist](operations/foundation-merge-checklist.md). Recheck
all required workflows on the proposed merge head; a documentation follow-up is not
automatically the tested source above. A required independent approving review must
not be replaced by an author's self-approval or an assistant status message.

Screenshots are inspection evidence, not approved visual regression baselines;
three Chromium viewports are not cross-browser or full accessibility qualification.
The simulator, football analytics, Foundry agents, editorial publication and audience
adaptation remain future implementation. Their completion belongs to later milestones,
not to the foundation merge. No next-phase certification is recorded.
