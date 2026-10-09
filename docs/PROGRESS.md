# Current progress

Date: 9 October 2026. Stage: Phase 2 in progress; P2-01 through P2-03 TESTED; P2-04 adapter + dependency lock qualified / live smoke blocked.
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

Hosted P1-01 qualification passed Foundation CI, Dependency audit, Source security and
Foundation integration. Foundation CI ran 146 tests on Python 3.12.15 with 100% package
statement and branch coverage. See the
[Phase 1A qualification record](evidence/phase1a-synthetic-engine-20261008.md).

P1-02, ordered/idempotent ingestion and replay revision handling, is TESTED on
development source `d7567779580d731e61feb02302627975887bf616`. The in-memory
`ReplayIngestor` separates arrival order from football sequence, treats exact
duplicates as idempotent no-ops, buffers future sequences, exposes gaps, flushes
contiguous buffered events when a gap closes, rejects stale/colliding identities and
advances a deterministic replay revision on a distinct late sequence-zero reset.

Hosted P1-02 qualification passed Foundation CI, Dependency audit, Source security and
Foundation integration. Foundation CI ran 161 tests on Python 3.12.15 with 100% package
statement and branch coverage. See the
[Phase 1B qualification record](evidence/phase1b-temporal-ingestion-20261008.md).

P1-03, the roster/score/possession reducer, is TESTED on development source
`b02ec6138a385dadbc5f2e166cd448d532d9e054`. The reducer validates registered/current
roster membership, substitutions, possession ownership, strict sequence input, exact
duplicate idempotency, goal-to-shot reference truth and exactly-once scoring.

Hosted P1-03 qualification passed Foundation CI, Dependency audit, Source security and
Foundation integration. Foundation CI ran 184 tests on Python 3.12.15 with 100% package
statement and branch coverage. See the
[Phase 1C qualification record](evidence/phase1c-football-state-reducer-20261008.md).

P1-04, registered football metrics, is TESTED on development source
`829f92033ffb4a8713a42711f8c383151f670d6a`. The registry exposes exactly six
versioned deterministic formulas: `shots.v1`, `goals.v1`, `pass_accuracy.v1`,
`synthetic_xg.v1`, `final_third_entries.v1` and `possession_time.v1`.
Independent hand-calculated tests establish count, ratio, xG, final-third and clipped
possession-window expectations. Unknown formulas, mixed-match inputs and unordered
input fail closed. The MetricAssertion contract now accepts versioned metric IDs.

Hosted P1-04 qualification passed Foundation CI, Dependency audit, Source security and
Foundation integration. Foundation CI ran 195 tests on Python 3.12.15. The implemented
package measured 99.26% total coverage across 625 statements and 186 branches; Ruff,
formatter checks and strict mypy passed, and the frontend build remained green. The
first candidate run retained a formatting-only failure after its tests, Ruff lint and
mypy had already passed; the exact formatter output was then qualified successfully.
See the [Phase 1D qualification record](evidence/phase1d-registered-metrics-20261008.md).

P1-05, deterministic moment detection, is TESTED on development source
`ad51a072b71d360839e031cbf8cd905634c2428a`. The detector exposes five explicit
moment types: goal, big chance, momentum swing, pressing spell and counter-attack goal.
The rules are deterministic and event-bound: goal markers remain distinct from
goal-valued shots; big chances use an inclusive synthetic-xG threshold of 0.35;
momentum swings require two same-team goals in one period within five minutes;
pressing spells require four successful attacking-half regains within 60 seconds
followed by a shot within 30 seconds of the fourth regain; counter-attack goals require
recovery-to-goal in one possession within 15 seconds.

Hosted P1-05 qualification passed Foundation CI, Dependency audit, Source security and
Foundation integration. Foundation CI ran 207 tests on Python 3.12.15 with 99.19%
measured total package coverage. Ruff, formatter checks and strict mypy passed, the
frontend build remained green, and integration passed runtime/browser plus independent
native-image security. The first candidate run retained a formatter-only failure after
its tests, repository checks, Ruff lint and mypy had passed; the exact formatter output
was then qualified successfully. See the
[Phase 1E qualification record](evidence/phase1e-moment-detection-20261008.md).

P1-06 technical review passed on closure head
`a0642e265aa90d81dfc094c4e75b1f42d64440dc`. Foundation CI, Dependency audit,
Source security and Foundation integration all passed on that exact head. The owner
explicitly approved the exact pair against base
`9dd644376148397a73e27b1508372cc7d6bd83c0`, and PR #24 was squash-merged through
protected `main` as `e3693da3edf54a155478bc9d38fc279e4051c3ab`.

Phase 1 is therefore **VERIFIED / COMPLETED** for the deterministic-engine scope.
The [Phase 1 closure review](evidence/phase1-closure-review-20261008.md) preserves the
qualification matrix, promotion-integrity proof and remaining later-phase boundaries.
Phase 2 may now begin, but Phase 1 closure does not authorize Azure provisioning,
live-model activation, production deployment or publication authority.

## Phase 2 progress

P2-01, the bounded deterministic orchestration control plane, is TESTED on development
source `fdb2acab1007a83377208406f9b3b69e2849aac2`. It locks the four specialist
roles `tactical_analyst`, `narrative_composer`, `editorial_reviewer` and
`audience_adapter` into an explicit sequence over typed `WorkflowState`.

The controller owns per-role attempt budgets, timeout classification, terminal blocked
and fallback states, bounded restart recovery and the verification hand-off. Editorial
review cannot advance directly to audience adaptation: the workflow first enters
`awaiting_verification`. A failed verification can request narrative/editorial revision
only while both role-local attempt budgets remain; exhausted revision budget falls back
instead of looping. Specialists cannot advance themselves or expand their own authority.

Hosted P2-01 qualification passed Foundation CI 37830905932, Dependency audit
37830906052, Source security 37830905951 and Foundation integration 37830905979 on the
exact source above. Foundation CI executed 226 tests on Python 3.12.15 with 99.32%
measured total package coverage. The new orchestration module reached 100% statement
and branch coverage. Ruff, formatting and strict mypy passed, the frontend build
remained green, and runtime/browser plus independent native-image qualification passed.
See the
[Phase 2A qualification record](evidence/phase2a-orchestration-control-plane-20261008.md).

No Agent Framework or Foundry runtime, live model, Azure resource, publication authority
or durable workflow persistence is claimed by P2-01.

P2-02, deterministic claim verification, is TESTED on development source
`6bff563d0d2b66eb9538513d0b77829872edccd1`. Measured claims are recomputed through
the registered Phase 1 metric engine; claim evidence must be bound by the exact
EvidenceRecord and present in accepted event input. Tactical prose can become only
`supported_inference`; event-fact prose without a registered semantic assertion returns
`needs_revision` rather than false verification. Verification results bind to the exact
EvidenceRecord content digest.

Hosted P2-02 qualification passed Foundation CI 37833033850, Dependency audit
37833033906, Source security 37833035687 and Foundation integration 37833034000.
Foundation CI ran 235 tests on Python 3.12.15 with 98.56% measured total package
coverage; the verifier module measured 87%. Ruff, formatting and strict mypy passed,
and runtime/browser plus independent native-image qualification passed. See the
[Phase 2B qualification record](evidence/phase2b-claim-verification-20261008.md).

P2-03, specialist execution interfaces and scoped read tools, is TESTED on
development source `e50758ca358f8d6bb8596e4a1a89eeeb0f752df7`. The host owns the
specialist role boundary and read-tool permission matrix. Tactical analysis can read
accepted events, windows and registered metrics; narrative/editorial roles additionally
read evidence and verification records; audience adaptation can read only evidence and
verification records. Requests must match the current P2-01 workflow role, responses
are frozen non-authoritative proposals using existing Claim records, and mixed-match
tool snapshots fail closed.

Hosted P2-03 qualification passed Foundation CI 37834593314, Dependency audit
37834593361, Source security 37834593365 and Foundation integration 37834593382.
Foundation CI ran 247 tests on Python 3.12.15 with 98.57% measured total package
coverage; the specialists module measured 99%. Contract/document checks, Ruff,
formatting and strict mypy passed, and runtime/browser plus independent native-image
qualification passed. See the
[Phase 2C qualification record](evidence/phase2c-specialist-interfaces-20261008.md).

P2-04 live specialist runtime integration has progressed to an **adapter-qualified /
live-qualification-blocked** state. The fail-closed Agent Framework / Foundry adapter is
qualified on source `42894407299d4b0a0594f88d364dc8b92586a845`. It adds an async
specialist boundary, explicit activation and endpoint/model configuration, bounded
structured RuntimeProposal output, a 1,200-token output ceiling, `store=False`,
role-specific instructions and host-produced P2-03 read snapshots. It does not grant
approval or publication authority.

Hosted adapter qualification passed Foundation CI 37880853903, Dependency audit
37880853720, Source security 37880853746 and Foundation integration 37880853750.
Foundation CI ran 257 tests on Python 3.12.15 with 96.68% measured total package
coverage; the Foundry adapter module measured 81% because the real Microsoft client
construction/network path was intentionally not executed. See the
[Phase 2D adapter record](evidence/phase2d-foundry-runtime-adapter-20261009.md).

P2-04 is not TESTED. The dependency-lock blocker is now RESOLVED: the repository pins
`agent-framework-foundry==1.14.1` and `azure-identity==1.26.0`, with a matching
resolver-generated `uv.lock`. Exact source
`726e49578c201b30896f15b8f7ac4d2073f162e2` passed Foundation CI 37896174178,
Dependency audit 37896174208, Source security 37896174216 and Foundation integration
37896174180, including runtime/browser and independent native-image qualification.
Foundation CI ran 258 tests and verified the required API surface directly against the
installed pinned Microsoft packages.

The sole remaining P2-04 blocker is a real Foundry project endpoint, deployed model name
and authenticated credential context for one bounded live specialist smoke test. The
versioned `scripts/p2d_live_foundry_smoke.py` harness now requires actual input/output/
total token telemetry, latency, deployed model identity, structured output and a
P2-02 `supported_inference` result for at least one evidence-bound tactical claim.
Source `43de0b8b645de658aaefb502ea8025c94a9df3bc` passed Foundation CI
37898724453, Dependency audit 37898724620, Source security 37898724364 and Foundation
integration 37898724344 with those controls. The existing 1,200-token ceiling and
`store=False` remain locked.
No Foundry/Azure resource was provisioned by this work and no live model invocation is
claimed yet. P2-05 remains PLANNED until P2-04 live qualification completes.

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
