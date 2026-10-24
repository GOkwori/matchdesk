# Project pitch

**MatchDesk: AI agents draft the football story, code checks every claim, a producer decides.**

**In one paragraph.** MatchDesk turns a stream of synthetic football events into
explainable match intelligence for studios, broadcasters and fans. Four specialist agents
on Microsoft Foundry and Agent Framework draft live overlays, stories and recaps. A
deterministic verifier recomputes every figure, and every sentence's claim, from the
event log before anything is shown. The result is personalised for each viewer: club,
player, focus statistic, fan, analyst or caption style, and English, Spanish or French.
It runs on Azure Container Apps. The match streams from the API, live agent runs and the
verifier are traced in Application Insights, and an MCP endpoint lets any other agent use
the same evidence and verifier.

**The problem.** Broadcast and digital teams publish match statistics and storylines
under time pressure. A wrong number or a misattributed goal goes out in seconds and is
corrected in public. A general-purpose AI makes this worse: it writes fluent sentences
that sound checked and are not.

**How it works.** MatchDesk separates writing from truth:

1. **Ingest.** Events arrive in order through an idempotent ingestor and a football-state
   reducer, streamed live from the API.
2. **Interpret.** Eighteen registered metrics run over the log: goals, shots, synthetic
   xG, pass quality, possession, defending, and synthetic tracking for shot speed, top
   speed, distance and sprints. Five deterministic detectors find the moments.
3. **Draft.** Four specialist agents built on Microsoft Agent Framework and Foundry
   (Tactical Analyst, Narrative Composer, Editorial Reviewer, Audience Adapter) read the
   match through role-scoped tools and propose claims. No agent can approve or publish.
4. **Verify.** Every claim is recomputed from the event log by registered formulas. The
   sentence itself is checked too: it must name its subject, its statistic and its time
   window, and state the number it asserts. A failed claim is sent back to the composer;
   code, not an agent, decides. The same verifier runs, ported exactly, in the browser.
5. **Explain and render.** Timed, machine-readable overlays and recaps are composed from
   verified values. Control, chaos and pressure changes are labelled by published rules.
6. **Approve.** Only claims that pass, or that are explicitly marked as opinion, reach a
   human producer, who decides what fans see.

**Category.** Best Multi-Agent System. The four specialists have distinct roles and
role-scoped tools. They hand off through typed shared state, and the deterministic
verifier sends unsupported claims back for a bounded revision. They recover from
malformed answers and provider errors within retry and time budgets. The end result, nine
audience versions whose every figure is verified, is something a single agent could not
produce or prove on its own.

**Microsoft technologies.**
- Microsoft Foundry and Microsoft Agent Framework: the four specialists and the Ask
  MatchDesk planner.
- Azure Container Apps: the studio and the internal API, with live replay streaming.
- Azure Container Registry, pulled through a managed identity with no keys.
- Azure Monitor: Application Insights through OpenTelemetry, plus Log Analytics.
- GitHub Actions deploying with OIDC.
- Azure AI Speech: neural voice-over in three languages, through the managed identity.
- The Model Context Protocol, for the read-only tools endpoint.

What you can try in three minutes, on an invented match (Northbridge FC 2–1 Riverside
United, 1,421 events):

- **Live agent run.** Start a live run of the four agents on Microsoft Foundry for the
  58th-minute goal and watch code send a claim back. Or replay the recorded run, and a
  rehearsal in which the composer claims 60% possession and the verifier recomputes 57.96%.
- **Try to fool the verifier.** Claim 59% yourself and watch it rejected, in the browser,
  from the raw events. Then see 810 false claims, made from the demo's own claims one
  error at a time, all caught, with none of 295 true ones rejected.
- **Live overlays.** Stream the match from the API on Azure at up to 60×, each event
  ingested and reduced as it arrives.
  - Timed overlays cover goals, shot speeds, stats cards, a spell of control, a tackles
    leader, and player tags when a sprint reaches 33 km/h or a player passes 5 km.
  - Each comes in fan, analyst or caption style, in English, Spanish or French.
  - Every number on screen is verified on the server, using only the events received
    so far, and again in your browser.
  - The same graphics load into OBS or vMix as a transparent broadcast overlay.
- **Automated recaps.** A half-time recap and a recap at the replay point, with milestones,
  every figure verified, in three styles and three languages. The live stream sends each
  one once its part of the match has arrived.
- **Listen.** Stories, recaps and overlays are read aloud by Azure AI Speech in English, Spanish
  or French, and Ask answers by your device's voice; only verified text is ever voiced.
- **Make it your match.** Choose a favourite club and player, a focus statistic and a
  language. Each of the 32 players has a page where every figure, including top speed and
  distance, is a verified sentence.
- **Explainability.** See who controlled each spell, where it turned to chaos, and when
  the pressure changed hands, labelled by published rules rather than by a model.
- **Fan stories.** Read a story for any goal, in your language and style, with its "How we
  checked this" panel.
- **Ask MatchDesk.** Ask "Who ran the furthest?" or "Who scored the second goal?" and get
  an answer whose every figure was computed and verified, or an honest "I can't check that".
- **Auto-eventing from video.** A detector that sees only a synthetic top-down video of the match
  finds the touches, passes, carries, shots and speeds, and is scored against the log.
- **Connect your own agent.** Point an MCP client at `/api/mcp` and use `check_sentence`
  to have its own sentences verified.

Everything is synthetic and nothing is published. The point is the trust boundary: AI may
draft, only code may certify a fact, and only a human may publish.
