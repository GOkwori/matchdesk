# Phase 1A synthetic match engine qualification — 8 October 2026

Status: **TESTED** on development source
`3c8bd0299eb80a2553337a0d472d036e4114545a`.

This evidence covers P1-01 only: the deterministic synthetic match engine. It does
not certify ingestion, reducers, registered metrics, moment detectors, agents,
publication, Azure deployment or production readiness.

## Implemented scope

The Phase 1A engine adds four seeded normal scenarios and one deliberately faulty
stream using the existing immutable `MatchEvent` contract:

- `late_winner`
- `momentum_swing`
- `pressing_spell`
- `counter_attack_goal`
- `fault_stream`

Normal scenarios retain contiguous sequence identity, unique event IDs, valid
period semantics and one-to-one shot-to-goal linkage. Scenario-specific facts are
machine-checkable rather than narrative expectations.

The fault stream keeps each individual event structurally valid while injecting
stream-level defects for the later ingestion layer:

- duplicate event;
- out-of-order sequence;
- sequence gap;
- replay-reset signal.

The same scenario name and seed produce identical compact UTF-8 JSON bytes. A
different seed changes generated content while preserving scenario rules.

## Hosted qualification

All required hosted workflows passed on the exact source above:

| Workflow | Run | Result |
|---|---:|---|
| Foundation CI | 37809719421 | PASS |
| Dependency audit | 37809719414 | PASS |
| Source security | 37809719549 | PASS |
| Foundation integration | 37809719410 | PASS |

Foundation CI executed 146 tests on Python 3.12.15. The implemented `matchdesk`
package reported 332/332 statements and 76/76 branches covered, with 100% total
coverage. Ruff, formatter checks and strict mypy passed. The frontend build remained
green.

Foundation integration passed the existing runtime/browser checks and the independent
native-image gate. No application contract, dependency lock, database schema, Azure
resource, security threshold or AI/model integration changed in this milestone.

## Boundaries

P1-01 is not the full deterministic intelligence layer. The following remain planned:

- ordered/idempotent ingestion and replay revision handling;
- roster, score and possession reduction;
- registered football metrics;
- deterministic moment detection;
- agent orchestration and evidence verification.

P1-02 is the next implementation work item.
