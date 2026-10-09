# Evidence index

Results are tied to source commits and execution environments. A passing build is not
an approval to deploy, and evidence from one source is not relabelled as another.

## Phase 2E failure/retry/recovery and model evaluation

- [P2-05 live Foundry model evaluation](phase2e-live-model-evaluation-20261009.md)
  records successful manual workflow run 37941568298 on development source
  `94fa73a37d69dbd03bf14820da63aeee5694383e`.
- The live run used 2,007 input tokens, 117 output tokens and 2,124 total tokens with
  8,187 ms measured latency, one proposed tactical claim, `store=False`, evaluation
  status `pass` and deterministic verification status `supported_inference`.
- Artifact `p2e-live-foundry-evidence` was retained as artifact ID `11621674108`
  with digest
  `sha256:20665b333b121aa85abe05b006b3e456fee43def3524ae9488c46ff291888958`.
- Exact-head deterministic qualification for the same P2-05 implementation passed
  Foundation CI 37937767196 (270 tests, 96.85% coverage), Dependency audit
  37937767422, Source security 37937767189 and Foundation integration 37937767394.

P2-05 is **TESTED** for its defined resilience and bounded live model-evaluation scope.
P2-06 Phase 2 review is next.

## Phase 2D Agent Framework / Foundry runtime adapter

- [Phase 2D Foundry runtime adapter qualification](phase2d-foundry-runtime-adapter-20261009.md)
  records the fail-closed async runtime adapter, bounded structured output, host-scoped
  read snapshots and retained live-qualification blockers on source
  `42894407299d4b0a0594f88d364dc8b92586a845`.
- Foundation CI 37880853903 passed 257 Python tests with 96.68% measured total package
  coverage; the new Foundry adapter module measured 81% because the real Microsoft
  client/network path was intentionally not executed.
- Dependency audit 37880853720, Source security 37880853746 and Foundation integration
  37880853750 also passed, including runtime/browser and the independent native-image
  verdict.
- A dependency-declaration attempt was correctly rejected by the locked-dependency gate
  because `uv.lock` had not been resolver-generated. No lock was guessed and no gate was weakened.
- [P2-04 live dependency-lock qualification](phase2d-live-dependency-lock-20261009.md)
  records the resolver-generated `agent-framework-foundry==1.14.1` /
  `azure-identity==1.26.0` graph. Exact source
  `726e49578c201b30896f15b8f7ac4d2073f162e2` passed Foundation CI 37896174178,
  Dependency audit 37896174208, Source security 37896174216 and Foundation integration
  37896174180. Foundation CI ran 258 tests and verified the required API surface against
  the actual installed Microsoft packages.

- [P2-04 live Foundry smoke qualification](phase2d-live-foundry-smoke-20261009.md)
  records successful manual workflow run 37923842661 on development source
  `f1ba3a9ae2b6e2e54de727761763085ee77776d8`, with 2,009 input tokens,
  104 output tokens, 2,113 total tokens, 6,763 ms latency, one tactical claim,
  `store=False`, and deterministic `supported_inference` verification.

P2-04 is **TESTED** for the bounded live-runtime scope. P2-05 is next.

## Phase 2C scoped specialist execution interfaces

- [Phase 2C specialist-interface qualification](phase2c-specialist-interfaces-20261008.md)
  records the model-agnostic SpecialistExecutor boundary, host-owned role permissions,
  frozen proposal envelopes and read-only deterministic tool scopes on source
  `e50758ca358f8d6bb8596e4a1a89eeeb0f752df7`.
- Foundation CI 37834593314 passed 247 Python tests with 98.57% measured total package
  coverage; the new specialists module measured 99% coverage.
- Dependency audit 37834593361, Source security 37834593365 and Foundation integration
  37834593382 also passed, including runtime/browser and the independent native-image
  verdict.
- Earlier candidates retain the real first-window assertion/docstring/style failure and
  the later style-only failure; no gate was disabled or waived.

P2-03 is TESTED. P2-04 live specialist runtime integration is next but still requires
the separately defined live-model, credential and cost approval.

## Phase 2B deterministic claim verification

- [Phase 2B claim-verification qualification](phase2b-claim-verification-20261008.md)
  records deterministic measured-claim recomputation, exact EvidenceRecord binding,
  supported tactical inference, fail-closed event-fact semantics and evidence-digest
  binding on source `6bff563d0d2b66eb9538513d0b77829872edccd1`.
- Foundation CI 37833033850 passed 235 Python tests with 98.56% measured total package
  coverage; the new verification module measured 87% coverage.
- Dependency audit 37833033906, Source security 37833035687 and Foundation integration
  37833034000 also passed, including runtime/browser and the independent native-image
  verdict.
- P2-02 does not parse arbitrary prose into facts or grant approval/publication authority.

P2-02 is TESTED. P2-03 specialist execution interfaces and scoped read tools is next.
Live Agent Framework / Foundry integration remains separately gated at P2-04.

## Phase 2A bounded orchestration control plane

- [Phase 2A orchestration control-plane qualification](phase2a-orchestration-control-plane-20261008.md)
  records the four locked specialist roles, typed workflow state, bounded role-local
  retries, controller timeout classification, deterministic verification hand-off and
  bounded restart recovery on source `fdb2acab1007a83377208406f9b3b69e2849aac2`.
- Foundation CI 37830905932 passed 226 Python tests with 99.32% measured total package
  coverage; the new orchestration module measured 100% statement and branch coverage.
- Dependency audit 37830906052, Source security 37830905951 and Foundation integration
  37830905979 also passed, including runtime/browser and the independent native-image
  verdict.
- Earlier P2-01 candidates retain the initial Ruff/formatter failure and the later
  formatter-only edge-coverage failure; no quality gate was disabled or waived.

P2-01 is TESTED. P2-02 deterministic claim verification is the next controlled Phase 2
work item. No live Agent Framework/Foundry runtime, model execution, Azure provisioning
or publication authority is implied by this evidence.

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

P2-04 strengthened live-smoke readiness: source `43de0b8b645de658aaefb502ea8025c94a9df3bc` passed all four hosted workflow groups; only real Foundry endpoint/model/authentication remains.
