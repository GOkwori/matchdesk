# Phase 1D registered football metrics qualification — 8 October 2026

Status: **TESTED** on development source
`829f92033ffb4a8713a42711f8c383151f670d6a`.

This evidence covers P1-04 only: deterministic, registered football metrics over
accepted immutable MatchEvent records. It does not certify deterministic moment
detectors, durable database persistence, agents, publication, Azure deployment or
production readiness.

## Implemented scope

The metric registry exposes exactly six versioned formula IDs:

- `shots.v1`: count shot events for the requested subject and half-open match window;
- `goals.v1`: count accepted goal markers, not goal-valued shot events;
- `pass_accuracy.v1`: completed passes divided by attempted passes, returning zero
  when the subject has no pass attempts;
- `synthetic_xg.v1`: sum the explicit synthetic xG values attached to matching
  shot events;
- `final_third_entries.v1`: count completed pass, carry or dribble movements
  crossing from `x < 200/3` to `x >= 200/3`;
- `possession_time.v1`: team share of event-derived attributable time intervals
  inside the requested window.

Metric inputs must belong to one match and arrive in strictly increasing sequence
order. Unknown formula IDs fail closed. The MetricAssertion contract now accepts
versioned metric identifiers such as `shots.v1`; structural validity alone still
does not prove that a formula is registered.

`possession_time.v1` is deliberately an event-derived observed-time share, not an
authoritative provider possession statistic. Consecutive accepted events define
observed intervals. Each interval is attributed to the team on the earlier event,
clipped to the half-open query window. Teamless markers contribute no owned time and
a window with no attributable interval returns zero.

## Independent expected-value tests

The Phase 1D fixture is explicitly hand-calculated rather than generated from the
implementation under test. It establishes:

- home shots = 2;
- home goals = 1;
- home synthetic xG = 0.7;
- home pass accuracy = 2/3;
- home-08 pass accuracy = 1.0;
- home final-third entries = 2 and away final-third entries = 1;
- full-window possession share = home 34/59 and away 25/59;
- clipped 12s–20s possession share = home 3/8 and away 5/8;
- zero-denominator pass accuracy returns zero;
- upper window bounds are exclusive;
- player-scoped possession time, mixed-match input, unordered input and unknown
  formula IDs fail closed.

## Hosted qualification

All required hosted workflows passed on the exact source above:

| Workflow | Run | Result |
|---|---:|---|
| Foundation CI | 37820755767 | PASS |
| Dependency audit | 37820755749 | PASS |
| Source security | 37820755700 | PASS |
| Foundation integration | 37820755710 | PASS |

Foundation CI executed 195 tests on Python 3.12.15. The implemented `matchdesk`
package reported 625 statements with three uncovered statements and 186 branches
with three partial branches; total measured coverage was 99.26%. The new metrics
module reported 95% coverage. Ruff lint, formatter checks and strict mypy passed,
and the frontend build remained green.

Foundation integration passed the real runtime/HTTP and PostgreSQL restart checks,
the locked Chromium regressions and the independent native-image security gate.
Dependency and source-security workflows also passed on the same source.

## Retained first attempt

Foundation CI run 37820637200 is retained as the first Phase 1D candidate failure.
Its 195 tests, Ruff lint and strict mypy had already passed, but the formatter gate
correctly rejected two unformatted files. The exact formatter output was applied,
producing source `829f92033ffb4a8713a42711f8c383151f670d6a`, which then passed
all four required workflows above. No check was suppressed or waived.

## Boundaries

These formulas operate over accepted in-memory event records. P1-04 does not provide
durable metric persistence, correction-driven downstream evidence recomputation,
moment detection, model inference, publication authority or cloud deployment.

P1-05, deterministic moment detectors for goal, big chance, momentum swing,
pressing spell and counter-attack goal, is the next implementation work item.
