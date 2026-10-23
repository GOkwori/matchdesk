# Demo script (under 2 minutes)

Recorded on the Azure deployment, https://mdesk-web.icybeach-62467e8a.uksouth.azurecontainerapps.io, with the
synthetic Northbridge v Riverside replay. Narration is first person. No music.

**Before recording**

1. Settings › **Reset demo data**, close the tour, then in **My match** choose Riverside, Lindqvist, Fan, English.
2. About three minutes before you record, open AI insights › **Run it live now** › **Start a live run**, so a fresh
   run has finished when you reach that screen (runs are five minutes apart).
3. Open Application Insights › *Transaction search* in another tab, filtered on `matchdesk.agents.live_run`.

| Time | Screen | Action | Narration |
| --- | --- | --- | --- |
| 0:00 | Home | Show the headline | "MatchDesk lets AI draft football stories, but only code can certify a fact, and only a producer can publish. It runs on Azure." |
| 0:08 | Overview | Click **Claim 59% instead** | "Northbridge had 57.96% of the ball. Claim 59% and it is rejected, recomputed from every event." |
| 0:18 | Live Intelligence | **Goal 58:17**, Play at 10×; then **Español** and **Broadcast caption** | "The match streams from the API on Azure: each event is ingested and reduced as it arrives, and each graphic is verified on the server the moment its window closes, using only what has arrived. Fan, analyst or caption, in three languages, and the same cues are a JSON feed." |
| 0:42 | AI insights | **Run it live now**: show the finished run's steps | "This run happened minutes ago on Microsoft Foundry. Four specialists, role-scoped tools, and here the verifier sent a claim back; the composer revised it, and only then did the audience versions go out." |
| 1:02 | Composer | Change 58 to 60 in a sentence | "Edit a sentence and it fails as I type. The words are checked, not just the data." |
| 1:12 | Audience Stories | Open Lindqvist's equaliser | "Every goal gets a story for fans, in their language, with the checks behind it, run again in their browser. It knows Lindqvist is my player." |
| 1:24 | Tactical Analysis | Scroll to Control and chaos | "Who controlled each spell, and when it turned to chaos, is a published rule over recomputed figures, not a model's opinion." |
| 1:34 | Ask | Ask "which player won the ball back most after the break" | "Ask anything. Foundry reads the question into a plan; code computes and verifies every figure." |
| 1:46 | Application Insights | Show the live-run span | "Every run, question and stream is traced in Application Insights." |
| 1:54 | Home | End | "AI-assisted. Verified. Human-led." |

If a live run is not available when you record (the five-minute spacing), use **Recorded live run**; its banner
names the provider and the date.
