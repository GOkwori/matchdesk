# Phase 1B temporal ingestion qualification — 8 October 2026

Status: **TESTED** on development source
`d7567779580d731e61feb02302627975887bf616`.

This evidence covers P1-02 only: ordered/idempotent event ingestion and replay
revision handling. It does not certify the later football reducer, registered metrics,
moment detectors, database persistence, agents, publication or production readiness.

## Implemented scope

The Phase 1B domain ingestor consumes already-valid `MatchEvent` records and keeps
arrival order separate from football event sequence. It provides:

- exact-event idempotency: re-sending identical event content is a no-op;
- explicit rejection when one event ID is reused with different immutable content;
- buffering of future sequences rather than silently reordering or discarding them;
- explicit reporting of all visible sequence gaps;
- contiguous flush when missing predecessors later arrive;
- fail-closed handling for stale unseen sequences and sequence collisions;
- match isolation so one ingestor cannot mix different match IDs;
- deterministic replay IDs and revisions;
- a distinct late sequence-zero marker as a replay-reset boundary that increments the
  revision and removes stale accepted/pending state from the prior replay generation.

The ingestor deliberately does **not** validate roster membership, score, possession
truth or goal-reference semantics. Those responsibilities remain with P1-03 and later
deterministic layers.

The Phase 1A fault stream is used directly in regression tests. Before its reset it
exposes duplicate arrival, out-of-order arrival and the deliberate missing sequence.
The reset then advances the replay to revision 2 and clears stale pending events.

## Hosted qualification

All required hosted workflows passed on the exact source above:

| Workflow | Run | Result |
|---|---:|---|
| Foundation CI | 37812734147 | PASS |
| Dependency audit | 37812734051 | PASS |
| Source security | 37812734238 | PASS |
| Foundation integration | 37812734182 | PASS |

Foundation CI executed 161 tests on Python 3.12.15. The implemented `matchdesk`
package reported 421/421 statements and 96/96 branches covered, with 100% total
coverage. Ruff, formatter checks and strict mypy passed. The frontend build remained
green.

Foundation integration passed the existing runtime/browser checks and independent
native-image gate. No contract schema version, dependency lock, database schema,
Azure resource, model/AI runtime, publication authority or security threshold changed.

## Boundaries

P1-02 is an in-memory deterministic domain component. It does not yet provide a
database-backed durable event store, crash recovery or multi-process concurrency.
Those concerns must be qualified separately before production claims.

P1-03, the roster/score/possession reducer with exactly-once scoring and event-reference
truth, is the next implementation work item.
