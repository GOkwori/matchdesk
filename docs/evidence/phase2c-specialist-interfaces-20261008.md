# Phase 2C scoped specialist execution interfaces qualification — 8 October 2026

Status: **TESTED** on development source
`e50758ca358f8d6bb8596e4a1a89eeeb0f752df7`.

This evidence covers P2-03 only: model-agnostic specialist execution interfaces and
host-enforced read-only tool scopes. It does not certify Agent Framework / Foundry
integration, live-model quality, Azure deployment, publication authority or production readiness.

## Authority boundary

The host, not a specialist runtime, owns the execution boundary:

- `SpecialistExecutor` is a model-agnostic protocol;
- requests must match the current running role in the P2-01 workflow state;
- responses are frozen proposals using existing `Claim` records and contain no
  approval or publication authority;
- the host rejects output that spoofs another specialist role;
- specialist tools expose immutable Phase 1/2 records only;
- mixed-match event snapshots fail closed.

The locked read-tool scopes are:

- tactical analyst: event lookup, windowed event reads and registered metrics;
- narrative composer: those deterministic reads plus evidence and verification records;
- editorial reviewer: the same deterministic/evidence/verification reads;
- audience adapter: evidence and verification records only, with no raw event or metric access.

No tool mutates deterministic events, evidence records, verification results, approvals
or publication state.

## Hosted qualification

All required hosted workflows passed on the exact implementation source:

| Workflow | Run | Result |
|---|---:|---|
| Foundation CI | 37834593314 | PASS |
| Dependency audit | 37834593361 | PASS |
| Source security | 37834593365 | PASS |
| Foundation integration | 37834593382 | PASS |

Foundation CI executed 247 tests on Python 3.12.15 with 98.57% measured total package
coverage. The new specialists module measured 99% coverage. Contract/document checks,
Ruff, formatter checks and strict mypy passed, and the frontend build remained green.

Foundation integration passed real HTTP/runtime and PostgreSQL restart checks, locked
Chromium regressions, exact runtime-image scans and the independent native-image verdict.

## Retained repair history

The first P2-03 candidate retained a real test failure caused by asserting a second-half
marker belonged to a first-half window, plus missing test-helper docstrings and
Ruff/formatter findings. Those were repaired from hosted diagnostics.

The next candidate passed all 247 behavior tests, contract/document checks and strict
typing but retained a style-only import-order/formatter failure. The exact style output
was applied without changing specialist authority semantics, producing the qualified
source above. No gate was disabled or waived.

## Boundaries

P2-03 provides interfaces and read scopes only. It does not invoke a model, implement a
Foundry runtime, persist agent state durably, create human approval, publish content or
provision Azure.

P2-04, live specialist runtime integration with Microsoft Agent Framework / Foundry,
is next but remains subject to the separate live-model, credential and cost approval
already defined by the backlog.
