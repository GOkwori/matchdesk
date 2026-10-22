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

At any point, press **Ask** and question the match: "What's the score?", "Who scored the
second goal?", "Possession after 60 minutes", "Which team had the most shots?". Every
figure in an answer is computed by a registered metric and checked by the same verifier,
with "How this was checked" under each line. Questions it cannot check (a header, the
season, "after the equaliser") are declined rather than answered with a nearby figure.

## What is real and what is staged

| Part | Status |
| --- | --- |
| Event log, metrics, moment detection | Deterministic code over synthetic data |
| Claim verification (numbers, names, statistic, time window, team, citations, event facts) | Real; the same verifier runs in Python and, ported exactly, in the browser. Limits below |
| Ask MatchDesk | Real; answers are built from registered metrics and verified before they are shown. An optional Foundry planner may only turn a question into a query plan, and it is off on the hosted demo |
| Four-specialist workflow | Real orchestration, role-scoped tools and verification loop. AI insights shows a live run recorded on Microsoft Foundry on 21 October 2026 (replayed, not called on page load) beside the deterministic rehearsal; every verdict in both is re-checked by the test suite |
| Audience variants | Produced by the Audience Adapter. Each cites only verified claims, and its fact comes from them; the surrounding tone ("Incredible performance!") is labelled as not checked. Human language review not run |
| Producer approval and publishing | Not enabled; Approve is shown locked |
| Identity, hosting of the backend | Not part of the demo |

## What the verifier does not check

The verifier is deliberately narrow, and fails closed: a sentence it cannot read is sent
back for revision rather than passed.

- **It checks:** the stated number against a recomputation from all events, at the stated
  precision; the named player or team; the statistic word (any of the fourteen registered
  metrics) and no other; the team; the time window ("in the second
  half", "since 60′"); for event facts, the clock time, minute and recorded details such as a
  header; that cited events are ones the metric counts; and that nothing reads past the
  replay point. Negative sentences ("did not score") are sent back, not checked.
- **It does not check:** tone and judgement ("a critical goal", "dominant"), which are shown
  as interpretation; Spanish and French sentences word by word (they carry the verified
  claims they cite and need a human language review); anything outside its fixed vocabulary
  of statistic and detail words; event facts beyond the two registered queries (who scored,
  and the gap between two events).
- **Data limits:** one synthetic match. Possession is time on the ball between consecutive
  events, not tracking data; synthetic xG is this demo's own model; ball speed is estimated from
  the time to the next event; there is no shot speed, distance run or auto-eventing from video.

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
