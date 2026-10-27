# Azure deployment record — 23 October 2026

MatchDesk's competition demo now runs on Azure Container Apps, built and deployed from GitHub Actions.

- **Studio:** https://mdesk-web.icybeach-62467e8a.uksouth.azurecontainerapps.io
- **Source:** `development` @ `af477a3`, the same commit as `release/submission-2026-10` and the Vercel copy
  (deployment `dpl_5ZmiPZEAVoy4UzRXU9y3D6QjEGCJ`, https://matchdesk-seven.vercel.app).
- **Workflow:** [Azure demo (studio and API)](../../.github/workflows/azure-demo.yml); template
  [`infra/azure/demo.bicep`](../../infra/azure/demo.bicep); setup in [azure-demo.md](../operations/azure-demo.md).

## What is running

| Resource | Detail |
| --- | --- |
| Resource group | `rg-matchdesk-dev`, UK South |
| `mdesk-web` | Next.js studio, public HTTPS, one warm replica (up to two) |
| `mdesk-api` | FastAPI service, internal ingress only; the studio reaches it as `http://mdesk-api` behind same-origin `/api` |
| Container registry | Basic, admin user off; both images tagged with the commit SHA |
| `mdesk-demo-id` | User-assigned managed identity: AcrPull on the registry, Cognitive Services User on the Foundry account |
| Log Analytics | Console logs, capped at 0.1 GB a day |

No keys or passwords: GitHub Actions signs in with OIDC, the apps pull images and call Foundry with the managed
identity, and the Foundry endpoint and model name are passed as settings.

## Runs

| Run | What it showed |
| --- | --- |
| what-if `39912446114` | Base resources previewed, nothing changed |
| deploy `39912573959` (`1a6629d`) | Base resources, both images, both apps; smoke test passed (pages, CSP and security headers, `/api/health`) |
| deploy (`3a7aa0a`) | Planner error detail in the server log |
| diagnose (read-only) | Foundry answered the planner with 403; the identity held only management roles (Azure AI Developer on the project, Azure AI Administrator on the account). Network open |
| deploy (`af477a3`) | Planner vocabulary for leaders and "the nth goal" |

Getting there took four owner actions, each found by the workflow rather than by guesswork: register three resource
providers; let the deploy identity assign AcrPull only (Role Based Access Control Administrator with a condition);
pass the budget addresses as a parameters file; and give `mdesk-demo-id` a role with the data permission to call
the model (Cognitive Services User on the Foundry account).

## Checked on the live Azure site

| Check | Result |
| --- | --- |
| `/api/health` through the studio | `{"service":"matchdesk","status":"alive",...}` |
| Live Intelligence | "13 timed overlays · 26 of 26 claims re-verified here" |
| Overlay feed `/overlays/nbr-riv.json` | Schema `matchdesk-overlay-feed/1`, 13 cues |
| Foundry planner, "Who scored the second goal?" | `{"intent":"scorers","nth":2,...}` in about 1.1 s |
| Foundry planner, "which player won the ball back most" | `{"intent":"leaders","metric":"recoveries.v1",...}` |
| Foundry planner, "Northbridge passing in the last ten mins" | `{"intent":"metric","metric":"pass_accuracy.v1","subjects":["nbr"],"window":{"last_minutes":10}}` |
| Ask MatchDesk, "which player won the ball back most after the break" | Top three players, each line verified; "Pettersen led 19 players on ball recoveries" |

The planner only reads a question into a plan; the studio validates the plan and computes and verifies every figure
itself. On the Vercel copy the planner is not mounted (`/api/assistant/plan` returns 404) and Ask uses its built-in
reader.

## Cost and lifetime

About $10–20 a month, mostly the registry and two small always-warm replicas. The demo stays up until judging ends
(10 November 2026) and is kept to 20 November; rollback is deleting the resource group.
