# Project pitch

**MatchDesk: AI agents draft the football story, code checks every claim, a producer decides.**

Broadcast and digital teams publish match statistics and storylines under time
pressure. A wrong number or a misattributed goal goes out in seconds and is corrected in
public. A general-purpose AI makes this worse: it writes fluent sentences that sound
checked and are not.

MatchDesk separates writing from truth:

1. **Detect.** Deterministic rules find the moments that matter in the match event log
   (goals, big chances, momentum swings).
2. **Draft.** Four specialist agents built on Microsoft Agent Framework and Foundry
   (Tactical Analyst, Narrative Composer, Editorial Reviewer, Audience Adapter) read the
   match through role-scoped tools and propose claims. No agent can approve or publish.
3. **Verify.** Every claim is recomputed from the event log by registered formulas.
   The sentence itself is checked too: it must name its subject, its statistic and its
   time window, and state the number it asserts. A failed claim is sent back to the
   composer; code, not an agent, decides.
4. **Approve.** Only claims that pass, or that are explicitly marked as opinion, reach
   a human producer, who decides what fans see in English, Spanish or French.

What you can try in three minutes, on an invented match (Northbridge FC 2–1 Riverside
United, 1,421 events):

- Start a live run of the four agents on Microsoft Foundry for the 58th-minute goal and
  watch code send a claim back; or replay the recorded run, and a rehearsal in which the
  composer claims 60% possession and the verifier recomputes 57.96% and sends it back.
- Claim 59% yourself and watch it rejected, in the browser, from the raw events.
- Edit a sentence in the composer and see it re-verified as you type.
- Stream the match from the API on Azure at up to 60×, each event ingested and reduced as
  it arrives, with timed broadcast overlays (goals, stats cards, a
  spell of control, a tackles leader) in fan, analyst or caption style, in English,
  Spanish or French. Every number on screen is re-verified in your browser first, and the
  same cues are a downloadable, machine-readable feed for a graphics engine.
- Make it your match: a favourite club and player, a focus statistic and a language, and a
  player-focus page for each of the 32 players where every figure is a verified sentence.
- See who controlled each spell, and where it turned to chaos, labelled by a published
  rule over recomputed figures rather than by a model.
- Read a fan story for any goal, in your language and style, with its "How we checked this"
  panel: every row a check the verifier passed, run again in your browser.
- Ask MatchDesk a question ("Who scored the second goal?", "Possession after 60 minutes")
  and get an answer whose every figure was computed and verified, or an honest "I can't
  check that".

Everything is synthetic and nothing is published. The point is the trust boundary:
AI may draft, only code may certify a fact, and only a human may publish.
