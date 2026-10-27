# Competition build — 21 October 2026

**Submission build:** `development` @ `ed9ff4ddddbb28ce3ec5e031a96bc1d350e7f170`, preserved as the branch
`release/submission-2026-10`.
**Hosted:** https://matchdesk-seven.vercel.app (Vercel production deployment `dpl_2JqC5MpNpA1sApJaFkPw9RRPaFXU`),
publicly reachable without a Vercel sign-in (checked 21 October 2026).
**Data:** one invented match, Northbridge FC 2–1 Riverside United, 1,421 synthetic events replayed to 67:12.

## What was delivered, by phase

| Phase | Pull requests | Result |
| --- | --- | --- |
| P0 Stabilise | #118 | Period-aware event windows, `/judge` session release, setup pin, dependency and secret-scan fixes |
| P1 Truthful verification | #119 | Sentence bound to its assertion (numbers and names), registered event facts (`goal_scorer.v1`, `sequence_gap.v1`), counted citations, evidence windows; exact Python/TypeScript parity |
| P2 Real agents | #119, #123–#131 | Four-specialist workflow with role-scoped traced tools, verification loop, rehearsal and Microsoft Foundry executors; run recorder and dispatch |
| P3 Interactive demo | #120 | Composer re-verifies sentences as you type, "Try to fool the verifier", seven-stop tour including the agents |
| P4 Ship | #122, #127, #132 | Submission docs, `/judge` retired, recorded live run shown beside the rehearsal |

## The recorded live run

Eight live runs were made on Microsoft Foundry through the registered "P2E live Foundry evaluation"
workflow (input `RUN_AGENT_WORKFLOW_LIVE`). Runs 1–7 each exposed a defect, which was fixed before the next:

| Run | Outcome | Fix |
| --- | --- | --- |
| 1 | Failed; cause not visible from the automation session | #124 failure annotations, longer turn deadline, provider errors retried |
| 2 | 19 and 28 tool calls; turns timed out | #125 tool loop bounded (8 calls, 4 rounds, 60 s) |
| 3 | One retry left no revision round | #126 shared retry and revision budget |
| 4 | Writer never told the recorded gap; IDs read as numbers | #128 |
| 5 | A single unfixable claim ended the run | #129 unverified claims withheld; prompts tightened |
| 6 | Hand-off exceeded its size bound | #130 bound raised; adapter output room |
| 7 | Audience versions returned as prose | #131 typed adapter output; trace published as annotations |
| 8 | **Completed** | #132 committed and shown |

Run 8: Actions run `39665579360` on `development` @ `8055758`. 4 specialist turns, 17 tool calls,
1 verification round, 25,731 tokens. The analyst's malformed first answer was rejected by the claim
contract and retried; the reviewer dropped an unchecked sentence; code verified Okafor's goal; the adapter
produced nine typed audience versions. The trace was rebuilt byte for byte from the run's annotations,
and every verdict in it is re-verified against the current verifier by the test suite.

## Checks at the submission build

- 1,288 Python tests; Ruff, formatting, strict mypy; documentation and docstring checks.
- 47-case verifier parity fixture, Python against TypeScript (50 web unit tests in all).
- 108 studio browser tests at three viewports: axe on every page, visual baselines, offline, security
  headers and CSP, performance and layout shift.
- Per-page JavaScript budget (AI insights 169.4 KB against 170 KB).
- Hosted CI on every pull request: Foundation CI, Foundation integration, Dependency audit, Source security.

## Known limits at submission

Producer approval and publishing are locked; there is no real sign-in or hosted backend; Spanish and
French are AI-assisted and await native-speaker review; manual assistive-technology testing and a
penetration test have not been done. See the [judging guide](../competition/judging-guide.md).
