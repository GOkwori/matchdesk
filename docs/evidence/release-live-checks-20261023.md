# Release candidate and live checks, 23 October 2026 (night)

## What was released

| Item | State |
| --- | --- |
| `development` | `f21fa0d` (merge of #184, the Spanish and French review), all exact-head checks green: foundation, web, runtime-browser, native-images, dependencies, history-secrets, CodeQL (Python and JS/TS), and the delivery-control lanes |
| `release/submission-2026-10` | Moved from `a803dd2` to `f21fa0d` on the owner's instruction |
| Azure | Redeployed from `f21fa0d` by `azure-demo.yml` run 40028299537 (mode deploy). Every step passed, including the smoke test of the public studio and the API behind it |
| Vercel | Production deployment `dpl_4yqwCqXeocNhyFKHJzwesqwtUsYk` from `release/submission-2026-10` at `f21fa0d`, ready and aliased to https://matchdesk-seven.vercel.app |
| `main` | Unchanged at `31371b0` |

## Live checks on Azure

Run in a real browser against https://mdesk-web.icybeach-62467e8a.uksouth.azurecontainerapps.io
after the redeploy.

| Check | Result |
| --- | --- |
| MCP `initialize` on `POST /api/mcp` | Server `matchdesk` 1.0.0, protocol `2025-06-18`; `tools/list` returns the nine tools |
| MCP `check_sentence` "Okafor scored 2 goals." / "… 3 goals." (`goals.v1`, `nbr-09`) | `verified` / `needs_revision` |
| MCP `get_overlays` 58′–59′ in French | "BUT ! Okafor marque pour Northbridge. Le score est de 2–1." and "La tête d’Okafor a été mesurée à 49,4 km/h": the reviewed wording |
| Live stream `GET /api/live/stream?speed=60&from_ms=0`, read to the end | 1,421 events, then an `end` frame at the replay point. All 21 overlay cues and both recaps (half-time at 844 events, latest at 1,421) arrived `verified`, each checked on the events received so far |
| Spanish story page, 58:17 goal | Reviewed wording shown ("Goles de Okafor: 2", "Texto para pantalla"); every check matches the log and "Comprobado de nuevo en tu navegador" is shown |
| Auto-eventing lab page | Renders; the clip plays in Chromium (WebM, 666 px wide) |
| Demo producer approval for D-031 | The dialog shows the two SHA-256 digests and stays disabled until a reason is given; approval binds the version; publishing times out one destination (3 of 4 sent), Retry sends it (4 of 4, social channel `PUB-dded824720`, attempt 2); no `/api` request is made. Editing the draft and reloading withdraws the approval ("Approval withdrawn …") |

Vercel serves the same build: its recap feed carries the reviewed Spanish and French text.

## Not checked here

- A new live agent run on Foundry: not repeated, to save cost. The last one, at
  `88db1b2`, is in the [Azure live checks](azure-live-checks-20261023.md).
- The owner's own attributable walkthrough of the judge path, the video and the submission.
  These remain owner steps.
