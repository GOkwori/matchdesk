# AI evaluation methodology

Status (26 October 2026): deterministic verifier benchmark and recorded Microsoft Foundry evaluations exist. They are bounded evidence for the competition demo, not a completed broad natural-model quality, security or multilingual evaluation. See [verifier benchmark](../evidence/verifier-benchmark-20261024.md), [competition build](../evidence/competition-build-20261022.md) and [judging guide](../competition/judging-guide.md).

The existing verifier benchmark derives 1,105 cases from 79 recorded, verified demo claims: 810 deliberately false cases and 295 true originals/rewordings. All receive the expected verdict in its defined scope on Python and TypeScript. This is not a substitute for an independently labeled natural-model evaluation set. A broader set of at least 60 labeled moments, 40 seeded false claims and 30 multilingual fact-preservation cases remains a proposed next evaluation milestone. Include wrong numbers, player/team identities,
time windows, invented events, unsupported causal language and omitted factual claims.

Evaluate natural model output separately from controlled injected errors. Store exact
model deployment/version, prompts, tools, source revision, cost, latency and dataset digest.
Use deterministic query outcomes for numerical facts; semantic review complements rather
than overrides them. Translation checks must detect meaning changes, not merely count
matching numbers and names. Report precision, recall and failure examples.

Provider failures, malformed responses, budget exhaustion, stale state and retries need
explicit outcomes. A template is labelled a template; cached output is labelled cached.
No result is reported for an evaluation that has not run.
