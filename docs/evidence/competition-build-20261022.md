# Competition build — 22 October 2026

**Submission build:** `development` @ `76de6c478219c84897ded3efef19169070dcb56b`; the branch
`release/submission-2026-10` was fast-forwarded to it from `ed9ff4d` once every hosted check passed.
**Hosted:** https://matchdesk-seven.vercel.app (Vercel production deployment `dpl_9Y4CU7N1tp26A8u1Ygfb5RTcjtN8`,
built from `release/submission-2026-10` @ `76de6c4`), publicly reachable without a Vercel sign-in (checked
22 October 2026).
**Previous build:** [21 October record](competition-build-20261021.md).

## What changed since 21 October

| Pull requests | Result |
| --- | --- |
| #133, #134 | WCAG 2.2 keyboard and target-size fixes; complete Spanish and French fan story |
| #136 | Producer-authority work integrated into `development` |
| #137 | Azure deployment planned as infrastructure as code with costs; nothing provisioned |
| #139, #141, #142 | Publication outbox behind the approval gate and a human ES/FR language-review gate, PostgreSQL migration 015, hardened after independent review |
| #138, #140, #143 | Image security gate names its findings; musl patched in the API and web images; heading audit waits for the page |
| #144 | Ask MatchDesk: questions answered by registered metrics and checked by the verifier, plus guidance |
| #145 | Sentence binding extended to the statistic word, negation, team, time window, clock and recorded detail, in Python and the browser port; Ask declines qualifiers no metric records |
| #146 | Judging guide states the verifier's limits; traceability R4/R5 brought up to date; unchecked variant tone labelled |

## Live runs on the stricter verifier

Three further live runs of the four specialists on Microsoft Foundry, through the registered "P2E live
Foundry evaluation" workflow (input `RUN_AGENT_WORKFLOW_LIVE`), all on `development` @ `76de6c4`:

| Run | Actions run | Turns | Tool calls | Rounds | Tokens | What happened |
| --- | --- | --- | --- | --- | --- | --- |
| 9 | `39806888935` | 4 | 23 | 1 | 43,018 | The analyst's malformed `sequence_gap` fact was rejected by the claim contract and retried; both claims reaching the verifier passed |
| 10 | `39807346186` | 4 | 30 | 1 | 31,353 | The writer's malformed facts were rejected twice and retried. The verifier sent back "A header made by Okafor preceded the goal … with 1 second interval" (recorded gap 0 s); the revision budget was spent, so code withheld it and only the verified claim went on |
| 11 | `39807699763` | 6 | 29 | 2 | 54,537 | The verifier sent back "Northbridge had a cumulative synthetic expected goals (xG) of 2.54 by the time they scored their second goal": the number was right, but the sentence also anchored the window to a goal, which the new binding rejects. The writer revised it and the revision verified |

Across the three runs, 6 claims reached the verifier on first submission and 2 were sent back (one wrong
number, one sentence saying more than its assertion); 3 malformed answers were stopped by the claim
contract before verification. All three runs completed within policy, and no unverified claim reached the
audience versions. 128,908 tokens in total.

These figures come from each run's summary annotation. The full traces were not retrieved: GitHub
truncates each annotation at 4,096 characters, and these traces were larger than one annotation, while
artifact downloads are not reachable from the automation session. The committed live trace on AI insights
remains run 8 of 21 October, which the test suite re-verifies against the current verifier.

## Checks at this build

- 1,583 Python tests at 94.7% coverage; Ruff, formatting, strict mypy; documentation and docstring checks.
- 76-case verifier parity fixture, Python against TypeScript; 173 web unit tests in all.
- Studio browser tests at three viewports, including Ask MatchDesk, offline use, axe on every page and
  visual baselines; hosted runtime-browser check green.
- Per-page JavaScript budget: largest page (AI insights) 166.4 KB against 170 KB.
- Hosted CI green on `76de6c4`: Foundation CI, integration and runtime-browser, CodeQL, dependency audit,
  history secret scan, native images.

## Known limits

Unchanged from 21 October, plus the verifier limits now stated in the
[judging guide](../competition/judging-guide.md#what-the-verifier-does-not-check). No video yet.
