# Evidence index

Results are tied to source commits and execution environments. A passing build is not
an approval to deploy, and evidence from one source is not relabelled as another.

## Phase 1 closure review

- [Phase 1 closure review](phase1-closure-review-20261008.md) records the P1-01 through
  P1-05 hosted qualification matrix, squash-promotion tree-integrity checks, current
  main/development tree equivalence, technical acceptance result and remaining scope
  boundaries.
- Technical review result: **PASS** for the deterministic-engine scope.
- Exact closure head `a0642e265aa90d81dfc094c4e75b1f42d64440dc` passed all required
  hosted workflows, was explicitly owner-approved against base
  `9dd644376148397a73e27b1508372cc7d6bd83c0`, and was squash-merged through
  protected main as `e3693da3edf54a155478bc9d38fc279e4051c3ab`.
- P1-06 is **COMPLETE** and Phase 1 is **VERIFIED / COMPLETED** for the deterministic-engine scope.

## Phase 1E deterministic moment detection

- [Phase 1E moment detection qualification](phase1e-moment-detection-20261008.md)
  records five explicit deterministic moment types and their positive/negative scenario
  regressions on source `ad51a072b71d360839e031cbf8cd905634c2428a`.
- Foundation CI run 37823057928 passed 207 Python tests with 99.19% measured total
  package coverage, Ruff, formatter checks and strict mypy.
- Dependency audit 37823057957, Source security 37823057917 and Foundation integration
  37823057960 also passed, including runtime-browser and native-images.
- Foundation CI run 37822980154 is retained as the first formatting-only failure:
  tests, repository/document checks, Ruff lint and mypy passed before the formatter
  correctly rejected one source file.

P1-05 is TESTED only. P1-06 Phase 1 review remains the next controlled work item.

## Phase 1D registered football metrics

- [Phase 1D registered metrics qualification](phase1d-registered-metrics-20261008.md)
  records the six versioned deterministic formula IDs, their explicit semantics and
  independent hand-calculated expected-value tests on source
  `829f92033ffb4a8713a42711f8c383151f670d6a`.
- Foundation CI run 37820755767 passed 195 Python tests with 99.26% total package
  coverage, Ruff, formatter checks and strict mypy.
- Dependency audit 37820755749, Source security 37820755700 and Foundation integration
  37820755710 also passed, including runtime-browser and native-images.
- Foundation CI run 37820637200 is retained as the first formatting-only failure:
  its tests, Ruff lint and mypy passed before the formatter correctly rejected two files.

P1-04 is TESTED only. Deterministic moment detection remains the next Phase 1 work.

## Phase 1C football-state reducer

- [Phase 1C football-state reducer qualification](phase1c-football-state-reducer-20261008.md)
  records roster/current-player validation, substitutions, possession ownership,
  validated goal→shot references and exactly-once scoring on source
  `b02ec6138a385dadbc5f2e166cd448d532d9e054`.
- Foundation CI run 37815702746 passed 184 Python tests with 100% package statement
  and branch coverage, Ruff, formatter checks and strict mypy.
- Dependency audit 37815703145, Source security 37815703924 and Foundation integration
  37815702741 also passed, including runtime-browser and native-images.

P1-03 is TESTED only. Registered metrics and deterministic moment detection remain
later Phase 1 work.

## Phase 1B temporal ingestion

- [Phase 1B temporal ingestion qualification](phase1b-temporal-ingestion-20261008.md)
  records ordered/idempotent replay ingestion, explicit gap handling and replay-reset
  revision behaviour on source `d7567779580d731e61feb02302627975887bf616`.
- Foundation CI run 37812734147 passed 161 Python tests with 100% package statement
  and branch coverage, Ruff, formatter checks and strict mypy.
- Dependency audit 37812734051, Source security 37812734238 and Foundation integration
  37812734182 also passed, including runtime-browser and native-images.

P1-02 is TESTED. The ingestor is an in-memory deterministic domain component;
durable event persistence is not yet implemented.

## Phase 1A synthetic engine

- [Phase 1A synthetic engine qualification](phase1a-synthetic-engine-20261008.md)
  records the four seeded normal scenarios, one fault stream, deterministic byte
  generation and hosted qualification on source
  `3c8bd0299eb80a2553337a0d472d036e4114545a`.
- Foundation CI run 37809719421 passed 146 Python tests with 100% package statement
  and branch coverage, Ruff, formatter checks and strict mypy.
- Dependency audit 37809719414, Source security 37809719549 and Foundation integration
  37809719410 also passed, including runtime-browser and native-images.

P1-01, P1-02 and P1-03 are TESTED; registered metrics and moment detection remain later
Phase 1 work.

## Phase 0 closure

- [Phase 0 closure evidence](phase0-closure-20261008.md) records the protected
  foundation merge, the post-squash history-secret remediation, final main commit
  `773ba7cc2da60d14e5a1e3106b61fa202c93624b`, active repository controls and the
  final passing post-merge qualification across all eight required checks.
- [Native scans and first runtime remediation](native-image-remediation-20261008.md)
  remains historical evidence for the earlier image-security blocker and remediation path.
- [First native scan and retained failures](native-images-first-run-20261008.md)
  preserves the first native scan failure.

No blanket vulnerability exemptions were added. The final Phase 0 main commit passed
the native-image gate, and repository protections are active. Phase 0 closure is not
a production deployment approval.

## Earlier dependency and source-security qualification

- [Patched dependencies, runtime and source-security results](security-remediation-20261008.md):
  source `e2ee20385f2d0da521dd9553eb5f9058d7b4b7e2`; four workflows passed. The report
  contains exact runs, artifact identities, 78 Python tests, nine runtime groups,
  24 Chromium cases and the scope of the passing scans.
- [First ASGI upgrade failure and supported-client correction](asgi-upgrade-first-run-20261008.md)
  preserves the test collection failure without suppressing the warning.
- [Patched ASGI candidates](patched-python-candidates-20261008.json) and
  [supported-client candidates](test-client-candidate-20261008.json) retain resolver provenance.
- [Secret-scan classification](secret-scan-classification-20261008.md) and its
  [exact reviewed digest record](secret-scan-reviewed-digests-20261008.json) preserve
  the initial 13 findings and narrow, recomputed non-secret classifications.

The native gate was not part of these earlier runs; they remain genuine for their
measured scope and do not override the later image findings above.

## Earlier built runtime, browser and security

- [Passing hosted runtime and browser qualification](hosted-integration-20261008.md):
  source `15996afa3219020c44dc1ff8f353e87d93e921e6`, integration run 37755579408;
  nine runtime groups and 24 Chromium cases passed.
- [Dependency advisory failure](dependency-audit-20261008.md): the same source,
  run 37755579414; eight distinct Python advisory IDs across three packages.
  This historical failure is resolved only for the later scanned graph above.
- [First failed integration attempt](integration-first-run-20261008.md): source
  `3b0ae4ae9569ebe97c0bae286720515ea50731ed`, run 37755125431; original assertions
  and failed evidence retained through the authentication/locator corrections.

Reports identify verified artifact digests, measured outcomes and what was not tested.
Screenshots do not establish approved visual baselines. Database probe results do not
establish application persistence, migrations or production disaster recovery.

## Hosted foundation

- [First passing Python and frontend qualification](hosted-foundation-20261008.md):
  source `c6de02db7ef268f9f144c8e108a0cb2e079e3111`, run 37751376812.
- [Initial dependency resolution](dependency-resolution-20261008.md) and its
  [raw manifest](dependency-resolution-20261008.json) preserve the first candidates.
- [Corrected dependency and formatting manifest](dependency-compatibility-20261008.json)
  records exact file identities from resolver run 37751193507.
- [Formatting review](formatting-review-20261008.json) records the checked source and
  unchanged functional AST, import bindings, docstrings and comments.
- [GitHub import and first hosted CI failure](github-import-20261008.md) records the
  exact imported tree and missing-lock failure.

The passing report links the earlier compatibility failure and exact artifact hashes.
Downloaded archives were checked against GitHub's reported SHA-256 digests. Raw hosted
artifacts contain JUnit, coverage and logs; durable report summaries remain in this repo.

## Historical local evidence

Dated subdirectories contain local commands, JUnit/coverage, source hashes and gate
status. `latest.json` identifies the latest **local collection**, not the latest hosted
build. Early attempt logs remain under `initial-attempts`; they are not attributed to
later source. Python 3.13.5 results are supplementary to hosted Python 3.12 qualification.
No cloud deployment, live model execution or production certification is implied.
