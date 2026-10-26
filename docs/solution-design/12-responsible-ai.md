# Responsible AI and evidence limitations

Status (26 October 2026): the Azure demo has documented live Microsoft Foundry specialist runs and a bounded Ask planner. This chapter records current safeguards and residual limitations; it does not certify the public demo as production-ready. See the [judging guide](../competition/judging-guide.md), [verifier benchmark](../evidence/verifier-benchmark-20261024.md) and [agent-run evidence](../evidence/competition-build-20261022.md).

The four specialist roles (Tactical Analyst, Narrative Composer, Editorial Reviewer and Audience Adapter) propose text using read-scoped tools. The orchestrator controls handoffs and bounded revisions; a separate deterministic verifier recomputes factual claims before use. The public studio uses a recorded run or rehearsal unless an explicitly rate-limited live run is requested.
AI does not establish the score, calculate authoritative statistics or approve publication.

All supplied event examples are synthetic. A valid contract does not prove plausible
football, existence in a match, causal influence or empirical predictive quality.
The synthetic xG field is an illustrative feature until its formula and limits are published.

Separate measured facts, event facts and tactical interpretation in every output. Preserve
that distinction through translation. Report unsupported assertions, stale evidence,
model failures and language fallbacks visibly. Do not turn a labelled demonstration
fixture into a claim of spontaneous error detection.

The committed deterministic benchmark tests 810 deliberately false and 295 true claims across the server and browser verifiers; all passed in its defined scope. Documented live Foundry runs include malformed and unsupported outputs that were rejected or revised. These are not a broad evaluation of all natural model outputs, multilingual semantics, prompt attacks, provider failures or reset races. Spanish and French templates received owner-led editorial review, not native-speaker certification. A zero error count on a finite test set is not a guarantee of universal truth. A producer remains accountable for final release; the public demo does not operate real external publishing.
