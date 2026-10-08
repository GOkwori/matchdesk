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

Phase 1 may now begin. Optional AI or cloud work must not displace the deterministic
truth layer.

| ID | Work | Status | Acceptance evidence |
|---|---|---|---|
| P1-01 | Build seeded synthetic match engine | NEXT | Four normal scenarios plus one fault scenario; reproducible bytes and valid invariants |
| P1-02 | Implement ordered/idempotent ingestion and replay revision handling | PLANNED | Duplicate/out-of-order/gap/reset regressions |
| P1-03 | Implement roster, score and possession reducer | PLANNED | Exactly-once scoring and ownership invariants |
| P1-04 | Implement registered football metrics | PLANNED | Independent expected-value tests for each formula ID |
| P1-05 | Implement deterministic moment detectors | PLANNED | Goal, big chance, momentum swing, pressing spell and counter-attack goal |
| P1-06 | Review Phase 1 | PLANNED | Source-bound evidence and explicit owner decision |

No Microsoft Agent Framework, Foundry, publication or Azure deployment work is
classified as Phase 1 completion evidence unless the deterministic engine gate is met.
