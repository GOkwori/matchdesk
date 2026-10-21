# MatchDesk judge golden path — offline synthetic qualification

**State: deterministic offline golden path, kept as a command-line check. The earlier opt-in localhost judge screen (`/judge`), its loopback API and its in-memory sessions were retired on 21 October 2026: they needed a Python host on the viewer's own machine, so they could not run on the hosted studio, and the studio's guided tour now covers the same walkthrough on the canonical match. See the [judging guide](judging-guide.md).**

The local runner uses only pre-existing deterministic MatchDesk domain components. It recomputes synthetic events, detects match moments, queries the registered first-half goal metric, binds an evidence-backed commentary claim, deliberately submits a false numerical claim for rejection, and creates nine scripted English/Spanish/French × analyst/casual-fan/caption audience variants.

The scripted specialist output is **not** a model execution. The nine translated examples have **not** been independently reviewed for meaning or language quality. No producer is authenticated, nothing is approved, no broadcast is published and no paid service or external data feed is contacted.

From the repository root, with the approved locked Python environment installed:

```bash
PYTHONPATH=backend/src python scripts/judge_demo.py
PYTHONPATH=backend/src python -m pytest backend/tests/test_judge_golden_path.py
```

The runner prints JSON only to stdout; it does not create a session. For repeated inspection, re-run the command against the same pinned Git SHA; compare the sorted JSON values and record the source SHA with the actual test output.

The deliberate false claim must return `needs_revision`; the good claim must be `verified`; every audience variant must retain the exact evidence digest and remain `NOT_RUN` for human language review. The `producer_review` fields must remain `authenticated: false`, `approval_enabled: false` and `publication_enabled: false`.

Before presenting as competition-ready, separately qualify the browser golden path, its opt-in localhost access policy, exact-source CI, a human demo rehearsal and the submission content. The original seven Batch 1 PNGs, independent WCAG 2.2 AA assessment, live workforce identity and protected `main` promotion are still distinct gates.
