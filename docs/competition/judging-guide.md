# Judging guide

MatchDesk runs on one invented match, Northbridge FC 2–1 Riverside United, replayed to
67:12 from a seeded log of 1,421 synthetic events. Nothing is live, real or published.

## The three-minute path

Open [matchdesk-seven.vercel.app](https://matchdesk-seven.vercel.app) (or run it yourself, below)
and choose **Start the 3-minute guided demo**. The tour has
seven stops:

1. **Overview.** The score, the replay slider, and a "try to fool the verifier" panel.
2. **The 58′ goal.** Why it was detected and which events prove it.
3. **AI insights.** A recorded live run of the four specialists on Microsoft Foundry,
   step by step: tool calls, a malformed answer rejected by the claim contract and
   retried, an unchecked sentence dropped by the reviewer, Okafor's goal verified by
   code, and nine audience versions. Switch to **Rehearsal** to watch the verifier send
   a 60% possession claim back and the revision pass.
4. **Evidence.** The 58% claim recomputed from all events, in the server and again in
   your browser; claim 59% and it is rejected.
5. **Review queue.** Draft D-031 is blocked by an unchecked interpretation and a
   season-history claim the log cannot support.
6. **Composer.** Remove or mark those sentences and the draft becomes eligible. Edit a
   sentence (change 58% to 60%) and it fails as you type.
7. **Fan story.** The verified story in English, Spanish or French, with its checks.

## What is real and what is staged

| Part | Status |
| --- | --- |
| Event log, metrics, moment detection | Deterministic code over synthetic data |
| Claim verification (numbers, names, citations, event facts) | Real; the same verifier runs in Python and, ported exactly, in the browser |
| Four-specialist workflow | Real orchestration, role-scoped tools and verification loop. AI insights shows a live run recorded on Microsoft Foundry on 21 October 2026 (replayed, not called on page load) beside the deterministic rehearsal; every verdict in both is re-checked by the test suite |
| Audience variants | Produced by the Audience Adapter; human language review not run |
| Producer approval and publishing | Not enabled; Approve is shown locked |
| Identity, hosting of the backend | Not part of the demo |

## Running it yourself

With Python 3.12, Node 22 and uv installed, from the repository root:

```bash
make setup            # or: make setup SETUP_PYTHON=3.12.13
cd apps/web && npm run build && npx next start
```

Then open `http://localhost:3000`. To regenerate everything the studio shows from the
event log: `PYTHONPATH=backend/src:. uv run --no-sync python -m scripts.export_demo_data`.

See the [demo script](demo-script.md), [pitch](pitch.md) and
[traceability](traceability-matrix.md).
