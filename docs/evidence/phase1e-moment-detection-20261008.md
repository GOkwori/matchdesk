# Phase 1E deterministic moment detection qualification — 8 October 2026

Status: **TESTED** on development source
`ad51a072b71d360839e031cbf8cd905634c2428a`.

This evidence covers P1-05 only: deterministic moment classification over accepted,
sequence-ordered MatchEvent records. It does not certify agent orchestration,
narrative generation, evidence verification, publication authority, Azure deployment
or production readiness.

## Detector semantics

The Phase 1E detector exposes five explicit moment types:

- `goal`: every accepted goal marker;
- `big_chance`: a shot with explicit synthetic xG greater than or equal to 0.35;
- `momentum_swing`: two goals by the same team in the same period within five minutes;
- `pressing_spell`: four successful attacking-half regains within 60 seconds,
  followed by a shot within 30 seconds of the fourth regain;
- `counter_attack_goal`: a completed recovery-to-goal sequence by one team in one
  possession within 15 seconds.

Successful pressing regains are winning tackles, interceptions or recoveries at
`x >= 50`. Counter-attack evidence is restricted to the same team, period and
possession from recovery through goal. Unknown or missing football facts are not inferred.

Moment input must belong to one match and be in strictly increasing event sequence.
Mixed-match or unordered input fails closed. Moment identities and evidence event IDs
are deterministic; no language model participates in classification.

## Scenario and negative tests

The qualified tests establish:

- the counter-attack scenario produces a goal, a big chance and a counter-attack goal;
- counter-attack evidence binds recovery, pass, carry, shot and goal in the same possession;
- the pressing scenario binds exactly four attacking-half regains and the terminal shot;
- the momentum scenario identifies the two home goals four minutes apart;
- the late-winner scenario exposes each accepted goal marker as an independent goal moment;
- the 0.35 big-chance threshold is inclusive and 0.349 does not qualify;
- goal moments and big-chance shot moments remain separate semantic records;
- slow, opponent, incomplete-pattern, detached-possession and over-15-second sequences
  do not receive the corresponding stronger classification;
- empty input produces no inferred moment;
- mixed-match and unordered inputs fail closed;
- coincident detector results retain stable ordering.

## Hosted qualification

All required hosted workflows passed on the exact source above:

| Workflow | Run | Result |
|---|---:|---|
| Foundation CI | 37823057928 | PASS |
| Dependency audit | 37823057957 | PASS |
| Source security | 37823057917 | PASS |
| Foundation integration | 37823057960 | PASS |

Foundation CI executed 207 tests on Python 3.12.15. The implemented `matchdesk`
package measured 748 statements with four uncovered statements and 236 branches with
four partial branches; total measured coverage was 99.19%. The new moments module
reported 123 statements, one uncovered statement, 50 branches and one partial branch,
for 99% measured coverage. Ruff lint, formatter checks and strict mypy passed; the
frontend build remained green.

Foundation integration passed the real HTTP/runtime and PostgreSQL restart checks,
locked Chromium regressions, complete scans of exact runtime-tested image IDs and the
independent native-image verdict. Dependency and source-security gates passed on the
same source.

## Retained first attempt

Foundation CI run 37822980154 is retained as the first Phase 1E candidate failure.
Its 207 tests, repository/document checks, Ruff lint and strict mypy passed, but the
formatter gate correctly rejected one unformatted source file. The exact Ruff
formatting suggestion was applied without changing detector semantics, producing
source `ad51a072b71d360839e031cbf8cd905634c2428a`, which passed all four workflows.

## Boundaries

These detectors classify only explicit synthetic-event patterns. They do not establish
tactical truth beyond the documented rules, infer intent, create narrative claims,
persist moments durably or authorize publication.

P1-06, Phase 1 review with source-bound evidence and explicit owner decision, is next.
