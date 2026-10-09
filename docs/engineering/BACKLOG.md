# Delivery backlog

## Phase 0 — engineering foundation

Status: **VERIFIED / COMPLETED** on 8 October 2026.

| ID | Work | Status | Acceptance evidence |
|---|---|---|---|
| F0-01 | Establish target GitHub repository access | COMPLETE | Repository imported and protected workflow established |
| F0-02 | Resolve dependency locks and exact frontend type pins | COMPLETE | Reviewed `uv.lock` and `package-lock.json`; frozen installs qualified |
| F0-03 | Run target Python 3.12 and static checks | COMPLETE | Hosted pytest, Ruff and mypy passed |
| F0-04 | Generate/check contracts and execute Next.js build | COMPLETE | Contract drift checks, type checks and production build passed |
| F0-05 | Execute Docker topology and browser flow | COMPLETE | Runtime, persistence and Chromium checks passed |
| F0-06 | Add and qualify scans/branch protections | COMPLETE | Dependency, CodeQL, secret-history and native-image gates passed; rulesets active |
| F0-07 | Review and merge Phase 0 | COMPLETE | Exact-SHA owner approval, protected PR merge and post-merge qualification recorded |

Final Phase 0 `main`: `773ba7cc2da60d14e5a1e3106b61fa202c93624b`.

See [Phase 0 closure evidence](../evidence/phase0-closure-20261008.md).

## Phase 1 — deterministic football engine

Phase 1 is **VERIFIED / COMPLETED**. P1-01 through P1-05 are TESTED and P1-06 is COMPLETE following exact-head owner approval and protected merge. Optional AI
or cloud work must not displace the deterministic truth layer.

| ID | Work | Status | Acceptance evidence |
|---|---|---|---|
| P1-01 | Build seeded synthetic match engine | TESTED | Four normal scenarios plus one fault scenario; reproducible bytes and valid invariants |
| P1-02 | Implement ordered/idempotent ingestion and replay revision handling | TESTED | Duplicate/out-of-order/gap/reset regressions; exact-head hosted qualification |
| P1-03 | Implement roster, score and possession reducer | TESTED | Exactly-once scoring, roster, substitution, possession and goal-reference invariants |
| P1-04 | Implement registered football metrics | TESTED | Six versioned formula IDs with independent hand-calculated expected-value tests |
| P1-05 | Implement deterministic moment detectors | TESTED | Five explicit moment types with positive/negative scenario regressions |
| P1-06 | Review Phase 1 | COMPLETE | Technical review PASS; exact closure candidate qualified, owner-approved and merged through protected main |

No Microsoft Agent Framework, Foundry, publication or Azure deployment work is
classified as Phase 1 completion evidence unless the deterministic engine gate is met.

P1-01 qualification: [Phase 1A synthetic engine evidence](../evidence/phase1a-synthetic-engine-20261008.md).

P1-02 qualification: [Phase 1B temporal ingestion evidence](../evidence/phase1b-temporal-ingestion-20261008.md).

P1-03 qualification: [Phase 1C football-state reducer evidence](../evidence/phase1c-football-state-reducer-20261008.md).

P1-04 qualification: [Phase 1D registered metrics evidence](../evidence/phase1d-registered-metrics-20261008.md).

P1-05 qualification: [Phase 1E moment detection evidence](../evidence/phase1e-moment-detection-20261008.md).

P1-06 review: [Phase 1 closure review](../evidence/phase1-closure-review-20261008.md).

Final Phase 1 status `main`: `8e110607c6877efca431debe7f8b69b5f53db9d9`.


## Phase 2 — bounded agent orchestration and verification

Phase 2 technical review passed, the exact closure head was qualified and owner-approved, and PR #36 was promoted through protected main. P2-06 is awaiting one clean post-merge qualification point because the squash merge commit did not emit main push runs.

| ID | Work | Status | Acceptance evidence |
|---|---|---|---|
| P2-01 | Implement typed bounded orchestration control plane | TESTED | Four locked specialist roles; typed state; bounded retries/timeouts/recovery; deterministic verification hand-off; 100% orchestration module statement/branch coverage |
| P2-02 | Implement deterministic claim verifier | TESTED | Recompute measured claims; bind exact evidence; support tactical inference without upgrading prose to fact |
| P2-03 | Implement specialist execution interfaces and scoped read tools | TESTED | Host-owned role scopes, immutable proposal envelopes and read-only deterministic tools |
| P2-04 | Integrate four specialist runtimes with Agent Framework / Foundry | TESTED | Adapter + locked dependencies qualified; live run 37923842661 passed with bounded token usage, retained evidence and `supported_inference` verification |
| P2-05 | Qualify end-to-end retries, timeouts, recovery and model evaluation | TESTED | Exact-head CI qualified deterministic resilience/evaluation paths; live run 37941568298 passed with one evidence-bound tactical claim, `supported_inference` and retained non-secret evidence |
| P2-06 | Review Phase 2 | POST-MERGE QUALIFICATION PENDING | Exact closure head qualified and owner-approved; PR #36 merged as `aedc840432ca0a868aa091a81ee60c93bb935db4`; clean post-merge qualification still required |

P2-01 qualification: [Phase 2A orchestration control-plane evidence](../evidence/phase2a-orchestration-control-plane-20261008.md).

P2-02 qualification: [Phase 2B claim-verification evidence](../evidence/phase2b-claim-verification-20261008.md).

P2-03 qualification: [Phase 2C specialist-interface evidence](../evidence/phase2c-specialist-interfaces-20261008.md).

P2-04 adapter qualification/blocker: [Phase 2D Foundry runtime adapter evidence](../evidence/phase2d-foundry-runtime-adapter-20261009.md).

P2-04 dependency-lock qualification: [Phase 2D live dependency lock evidence](../evidence/phase2d-live-dependency-lock-20261009.md).

Phase 2 does not authorize producer publication, Azure deployment or production readiness.
