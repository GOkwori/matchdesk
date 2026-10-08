# AI evaluation methodology

Status: planned; no live or recorded agent suite is implemented in Phase 0.

The eventual dataset includes at least 60 labelled moments, 40 seeded false claims and
30 multilingual fact-preservation cases. Include wrong numbers, player/team identities,
time windows, invented events, unsupported causal language and omitted factual claims.

Evaluate natural model output separately from controlled injected errors. Store exact
model deployment/version, prompts, tools, source revision, cost, latency and dataset digest.
Use deterministic query outcomes for numerical facts; semantic review complements rather
than overrides them. Translation checks must detect meaning changes, not merely count
matching numbers and names. Report precision, recall and failure examples.

Provider failures, malformed responses, budget exhaustion, stale state and retries need
explicit outcomes. A template is labelled a template; cached output is labelled cached.
No result is reported for an evaluation that has not run.
