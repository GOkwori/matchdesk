# Demo script (under 2 minutes)

Recorded on the Azure deployment, https://mdesk-web.icybeach-62467e8a.uksouth.azurecontainerapps.io, with the
synthetic Northbridge v Riverside replay. Narration is first person. No music.

**Before recording**

1. Settings › **Reset demo data**, close the tour, then in **My match** choose Riverside, Lindqvist, Fan, English.
2. About three minutes before you record, open AI insights › **Run it live now** › **Start a live run**, so a fresh
   run has finished when you reach that screen (runs are five minutes apart).
3. In VS Code, add the MCP server (`.vscode/mcp.json`:
   `{"servers": {"matchdesk": {"type": "http", "url": "https://mdesk-web.icybeach-62467e8a.uksouth.azurecontainerapps.io/api/mcp"}}}`)
   and open GitHub Copilot Chat in Agent mode.
4. Open Application Insights › *Transaction search* in another tab, filtered on `matchdesk.agents.live_run`.

| Time | Screen | Action | Narration |
| --- | --- | --- | --- |
| 0:00 | Home | Show the headline | "MatchDesk lets AI draft football stories, but only code can certify a fact, and only a producer can publish. It runs on Azure." |
| 0:08 | Overview | Click **Claim 59% instead** | "Northbridge had 57.96% of the ball. Claim 59% and it is rejected, recomputed from every event." |
| 0:16 | Live Intelligence | **Goal 58:17**, Play at 10×; then **Español** and **Broadcast caption** | "The match streams from the API: each event ingested as it arrives, each graphic verified on the server the moment its window closes. The header left Okafor's head at 49.4 km/h; sprints and distance tag players as they cross a threshold. Three styles, three languages, and a JSON feed." |
| 0:38 | AI insights | **Run it live now**: show the finished run's steps | "This run happened minutes ago on Microsoft Foundry. Four specialists, role-scoped tools; the verifier sent a claim back, the composer revised it, and only then did the audience versions go out." |
| 0:56 | Composer | Change 58 to 60 in a sentence | "Edit a sentence and it fails as I type." |
| 1:03 | Audience Stories | **Match recaps** › Half-time; then Lindqvist's equaliser | "Recaps write themselves at half-time, milestones included, every figure verified and re-checked in the fan's browser, in their language. It knows Lindqvist is my player." |
| 1:18 | Tactical Analysis | Scroll to **Pressure changes** | "Control, chaos and pressure are published rules over recomputed figures: pressure doubles at the restart." |
| 1:27 | Ask | Ask "Who ran the furthest?" | "Ask anything. Foundry reads the question into a plan; code computes and verifies every figure." |
| 1:36 | VS Code | In Copilot Agent mode: "Use matchdesk to check: Okafor scored 3 goals." | "And any agent can use the same verifier over MCP. Copilot's sentence is sent back: the log says two." |
| 1:48 | Application Insights | Show the live-run span | "Every run, question, stream and tool call is traced in Application Insights." |
| 1:55 | Home | End | "AI-assisted. Verified. Human-led." |

If a live run is not available when you record (the five-minute spacing), use **Recorded live run**; its banner
names the provider and the date.
