# Judging guide

MatchDesk runs on one invented match, Northbridge FC 2–1 Riverside United, replayed to
67:12 from a seeded log of 1,421 synthetic events. Nothing is real or published, and the live
stream plays that recorded log back as if it were happening.

## The three-minute path

Open the studio on Azure, [mdesk-web.icybeach-62467e8a.uksouth.azurecontainerapps.io](https://mdesk-web.icybeach-62467e8a.uksouth.azurecontainerapps.io) (Azure Container Apps: the Next.js studio in front of the FastAPI service). A studio-only copy runs at [matchdesk-seven.vercel.app](https://matchdesk-seven.vercel.app). Or run it yourself, below.
Choose **Start the 3-minute guided demo**. The tour has
seven stops:

1. **Match overview.** The score, the replay slider, and a "try to fool the verifier" panel.
2. **The 58′ goal.** Why it was detected and which events prove it.
3. **How AI helps.** A recorded live run of the four specialists on Microsoft Foundry,
   step by step: tool calls, a malformed answer rejected by the claim contract and
   retried, an unchecked sentence dropped by the reviewer, Okafor's goal verified by
   code, and nine audience versions. Switch to **Rehearsal** to watch the verifier send
   a 60% possession claim back and the revision pass.
4. **Check the facts.** The 58% claim recomputed from all events, in the server and again in
   your browser; claim 59% and it is rejected.
5. **Review drafts.** Draft D-031 is blocked by an unchecked interpretation and a
   season-history claim the log cannot support.
6. **Write a match story.** Remove or mark those sentences and the draft becomes eligible. Edit a
   sentence (change 58% to 60%) and it fails as you type.
7. **Fan story.** The verified story in English, Spanish or French, with its checks.

At any point, press **Ask** and question the match: "What's the score?", "Who scored the
second goal?", "Possession after 60 minutes", "Which team had the most shots?". Every
figure in an answer is computed by a registered metric and checked by the same verifier,
with "How this was checked" under each line. Questions it cannot check (a header, the
season, "after the equaliser") are declined rather than answered with a nearby figure.

## Beyond the tour

- **Live replay with broadcast overlays** (Watch the replay). Play the log at 1×, 10×, 30×
  or 60×, scrub, or jump to a goal. The score bug, possession, shots, pass accuracy and your
  focus statistic are recomputed by the registered metrics as the clock moves. Twenty-one
  timed overlays appear at their moments in fan, analyst or caption style, in English,
  Spanish or French:
  - goals, and the speed of each scoring shot;
  - stats cards every 15 minutes, a spell of control and a tackles leader;
  - a player tag when a sprint reaches 33 km/h, and the first player on each side past 5 km;
  - cards and the substitution.

  Before any is shown, all 37 claims behind them are re-verified in your browser; cards and
  the substitution are checked by their own event-fact queries (the colour and both players).
  **On Azure the replay streams from the API.** Each event goes through the backend's
  ordered ingestor and football-state reducer, and each overlay is verified on the server
  the moment its window closes, using only the events received so far ("Checked on the
  server at 15:00, on the 305 events received").
- **Automated recaps** (Match stories › Match recaps, or the replay once a half is played).
  - A half-time recap and a recap at 67:12: the score, scorers, possession, shots, passing,
    synthetic xG and the tackles leader.
  - Milestones: the opening goal, the equaliser, the lead restored, Okafor's brace, and each
    side's 5th, 10th and 15th shot.
  - Every figure is a verified claim, re-checked in your browser, in three styles and three
    languages.
  - On Azure the live stream sends each recap, verified on the server, once its part of the
    match has arrived.
  - The same recaps are JSON at [`/recaps/nbr-riv.json`](https://mdesk-web.icybeach-62467e8a.uksouth.azurecontainerapps.io/recaps/nbr-riv.json).
- **Run the agents live** (AI insights › *Run it live now*, Azure only). Starts a fresh run of
  the four specialists on Microsoft Foundry for the 58′ goal and shows each step as it
  happens: tool calls, claims sent back by the verifier, the revision, the audience versions.
  It takes a few minutes (at most six); runs are five minutes apart and at most twelve a day, to
  bound cost. If one has just run, you will see it and when the next can start.
- **Auto-eventing from video** (Watch the replay › *Open the auto-eventing lab*). The synthetic
  match is rendered as a top-down video with sensor noise and an occasionally hidden ball. A
  detector that sees only the pixels finds every touch and reads passes, carries, shots,
  pass lengths and ball and shot speeds. The lab scores it against the log over the whole
  replay: touches found, precision, type and team accuracy, length and speed errors, shot
  speeds against the synthetic tracking, and possession from the video against the registered
  metric. It is synthetic video and much easier than broadcast footage, and the page says so
  ([method](../../labs/auto_eventing/README.md)).
- **Approve and publish, as a demo producer** (Review drafts › Try demo publishing, once D-031 is
  eligible). The approval binds SHA-256 digests of the exact text and of the claims' verdicts;
  edit the draft afterwards and the approval is withdrawn. Publishing sends the approved
  version to four demo destinations, each with a publication id derived from the digest; the
  social channel times out on its first attempt, and Retry sends only that one again. Every
  step goes into an audit trail. No sign-in, and nothing leaves your browser.
- **Machine-readable overlay feed.** The same cues as JSON at
  [`/overlays/nbr-riv.json`](https://mdesk-web.icybeach-62467e8a.uksouth.azurecontainerapps.io/overlays/nbr-riv.json)
  (schema `matchdesk-overlay-feed/1`): time, kind, team, players, event ids, every persona
  and language, and each claim in full, so a graphics engine or a judge can re-run the
  verifier on it.
- **Voice-over** (Listen on every story and recap, *Read overlays aloud* in Live Intelligence,
  Listen on Ask MatchDesk answers, `voice=1` on the broadcast overlay). On Azure, Azure AI Speech
  neural voices read the verified text in English, Spanish or French; the API voices only items
  from the verified feeds, by name, never free text, caches each clip and caps new ones. Elsewhere,
  and for Ask answers, the device's own voice reads the same verified sentences.
- **Broadcast overlay for OBS or vMix** (Live Intelligence › *Open the broadcast overlay*).
  The same cues as lower-thirds with a score bug on a transparent page, at
  [`/broadcast/nbr-riv`](https://mdesk-web.icybeach-62467e8a.uksouth.azurecontainerapps.io/broadcast/nbr-riv?style=caption&lang=es&speed=10&bg=dark).
  Add it as a 1920×1080 browser source; `style`, `lang`, `speed`, `from`, `bg` and `bug` set it
  up. Each graphic is re-verified in that browser before it is drawn, and one that does not
  verify is never drawn.
- **Try to fool the verifier, at scale** (Evidence & Verification › *How the verifier did*).
  The 79 claims the demo shows, made wrong one way at a time (number, player, team, half,
  statistic, evidence, scorer, card, substitute, gap, time): 810 of 810 caught, and 0 of 295
  true claims and rewordings rejected, with the same verdicts in the browser. It found one
  gap, a substitution written the wrong way round, which is now fixed
  ([record](../evidence/verifier-benchmark-20261024.md)).
- **My match** (Settings). Favourite club and player, fan / analyst / caption, language and
  one focus statistic (top speed, distance and sprints among them). The overview, the replay overlays, the player page and Ask MatchDesk's
  suggestions follow these choices, kept on the device only.
- **Player focus** (Players). Each of the 32 players has a page with up to fifteen figures,
  each stated as a sentence and verified, plus an action map of their passes, shots and
  recoveries:
  - goals, shots and synthetic xG;
  - pass accuracy, length, progressive passes, difficulty and passes under pressure;
  - tackles, interceptions and recoveries;
  - from synthetic tracking: shot speed, top speed, distance covered and sprints.
- **Fan stories** (Audience Stories). One story for every goal, generated from the log:
  headline, body, score and a diagram of the move. Each fact in the text (scorer, score,
  the scorer's tally, and how the move began: a corner, an interception or the start of the
  move, with the seconds to the goal) is a claim the verifier passed, and the page re-runs
  those checks in your browser. What the log cannot show (who made the final pass, defender
  positions) is listed as not checked. The page follows My match: language, fan / analyst /
  caption style, and a line when your club or player is involved.
- **Control, chaos and pressure** (Tactical Analysis). Every five minutes is labelled by a
  published rule, not a model, and each phase lists the verified sentences that justify it,
  with ball speed as the match rhythm:
  - control: a side has 60% of the ball and completes 85% of its passes;
  - chaos: the ball is won back at least 3.2 times a minute;
  - contested: anything else.

  **Pressure changes** are listed when the side pressing harder switches, or when passes
  under pressure rise or fall by eight, each with the verified counts either side (pressure
  doubles at the restart, from 12 to 26).
- **Connect your own agent (MCP).** On Azure, `POST /api/mcp` is a read-only Model Context
  Protocol server ([design](../design/mcp.md)). Add
  `https://mdesk-web.icybeach-62467e8a.uksouth.azurecontainerapps.io/api/mcp` to any MCP
  client (in VS Code, an `http` server). It has nine tools:
  - `check_sentence` and `verify_claim` run the same verifier on your agent's own sentences;
  - `compute_metric`, `list_metrics` and `list_players`;
  - `get_events`, `get_overlays`, `get_story` and `get_recap`.

## What is real and what is staged

| Part | Status |
| --- | --- |
| Event log, metrics, moment detection | Deterministic code over synthetic data |
| Claim verification (numbers, names, statistic, time window, team, citations, event facts) | Real; the same verifier runs in Python and, ported exactly, in the browser. Limits below |
| Ask MatchDesk | Real; answers are built from registered metrics and verified before they are shown. When the built-in reader cannot read a question, a planner on Microsoft Foundry may turn it into a query plan, never an answer: it is on for the Azure deployment (bounded to 200 output tokens, 10 seconds, 20 calls a minute) and off on the Vercel copy |
| Four-specialist workflow | Real orchestration, role-scoped tools and verification loop on Microsoft Foundry. AI insights opens on a run recorded on 21 October 2026 beside the deterministic rehearsal, and on Azure you can start a fresh live run (rate-limited). Every verdict is the real verifier's |
| Live replay and overlay feed | Real: the recorded synthetic log played back (not a real match); on Azure it streams from the API through the ingestor, reducer and verifier; overlay numbers come from verified claims, re-verified in the browser before display. Cards and substitutions are verified by registered event facts (`card.v1`, `substitution.v1`) |
| Recaps | Real: built from verified claims at half-time and the replay point; on Azure streamed and verified on the events received |
| Voice-over | Real: Azure AI Speech neural voices on Azure, signed in with the managed identity; the device's own voice elsewhere |
| Synthetic tracking (shot speed, player speed, distance) | Generated with the match by a seeded model, as a tracking provider would supply it; not measured from video. The metrics over it are real and verified |
| MCP endpoint | Real, read-only, on Azure only; the same verifier and feeds |
| Personalisation | Real, on the device only: no account, nothing sent |
| Audience variants | Produced by the Audience Adapter. Each cites only verified claims, and its fact comes from them; the surrounding tone ("Incredible performance!") is labelled as not checked. The Spanish and French templates were reviewed and corrected on 23 October and certified by the owner ([record](../evidence/language-review-es-fr-20261023.md)); live model variants have not had a human language review |
| Producer approval and publishing | Demo: approve D-031's exact version without sign-in, then publish to a demo channel in your browser (one destination times out first, to show a safe retry). No real sign-in or destination |
| Hosting | Azure Container Apps in UK South, traced to Application Insights: the studio (public) and the API (internal only, reached through the studio's same-origin `/api`), images in Azure Container Registry, pulled by a managed identity with no passwords; logs in Log Analytics. Deployed from GitHub Actions with OIDC, no stored cloud keys |
| Producer sign-in | Not part of the demo |

## What the verifier does not check

The verifier is deliberately narrow, and fails closed: a sentence it cannot read is sent
back for revision rather than passed.

- **It checks:** the stated number against a recomputation from all events, at the stated
  precision; the named player or team; the statistic word (any of the eighteen registered
  metrics) and no other; the team; the time window ("in the second
  half", "since 60′"); for event facts, the clock time, minute and recorded details such as a
  header; that cited events are ones the metric counts; and that nothing reads past the
  replay point; for a substitution, who came on and who went off. Negative sentences ("did
  not score") are sent back, not checked.
- **It does not check:** tone and judgement ("a critical goal", "dominant"), which are shown
  as interpretation; Spanish and French sentences word by word (they carry the verified
  claims they cite; their wording had a separate, certified language review); anything outside its fixed vocabulary
  of statistic and detail words; event facts beyond the four registered queries (who scored,
  the gap between two events, a card and its colour, a substitution and both players).
- **Data limits:** one synthetic match. Possession is time on the ball between consecutive
  events; synthetic xG is this demo's own model; ball speed is estimated from the time to the
  next event. Shot speed, player speed and distance come from synthetic tracking generated
  with the log, one sample per action, so distance is metres run between a player's actions.
  There are no positions of players off the ball; auto-eventing runs on synthetic video only
  (the lab), not on broadcast footage.

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
