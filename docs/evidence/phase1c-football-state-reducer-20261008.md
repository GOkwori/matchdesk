# Phase 1C football-state reducer qualification — 8 October 2026

Status: **TESTED** on development source
`b02ec6138a385dadbc5f2e166cd448d532d9e054`.

This evidence covers P1-03 only: deterministic roster, score, possession and
goal-reference reduction over accepted MatchEvent records. It does not certify
registered metrics, moment detectors, durable database persistence, agents,
publication, Azure deployment or production readiness.

## Implemented scope

The reducer consumes sequence-ordered accepted events and enforces football-state
truth intentionally left outside the boundary schema:

- exactly two registered teams per match;
- unique registered player identity across teams;
- active-player validation for ordinary player events;
- substitution updates from active outgoing player to registered inactive substitute;
- one team owner per possession ID for the replay revision;
- strict increasing sequence order at reducer input;
- exact duplicate event content is an idempotent no-op;
- event-ID reuse with changed content fails closed;
- goal markers require a previously accepted linked shot;
- the linked event must be a goal-valued shot from the same team and possession;
- one linked shot can increment score exactly once.

Normal Phase 1A simulator scenarios reduce successfully. The late-winner scenario
reduces deterministically to home 2, away 1.

## Hosted qualification

All required hosted workflows passed on the exact source above:

| Workflow | Run | Result |
|---|---:|---|
| Foundation CI | 37815702746 | PASS |
| Dependency audit | 37815703145 | PASS |
| Source security | 37815703924 | PASS |
| Foundation integration | 37815702741 | PASS |

Foundation CI executed 184 tests on Python 3.12.15. The implemented `matchdesk`
package reported 538/538 statements and 152/152 branches covered, with 100% total
coverage. Ruff, formatter checks and strict mypy passed. The frontend build remained
green.

Foundation integration passed the existing runtime/browser checks and independent
native-image gate. No contract schema version, dependency lock, database schema,
Azure resource, model/AI runtime, publication authority or security threshold changed.

## Boundaries

The reducer is an in-memory deterministic domain component. It does not yet provide
database durability, replay persistence, metric calculation, moment detection or
correction-driven recomputation of downstream evidence.

P1-04, registered football metrics with explicit formula IDs and independent
expected-value tests, is the next implementation work item.
