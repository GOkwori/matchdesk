# Azure demo: the studio and the API on Container Apps

The competition demo runs on Azure Container Apps. This is smaller than the production plan in
[azure-deployment-plan.md](azure-deployment-plan.md): there is no private network, database, Key Vault or
sign-in, because the demo has none of them.

## What is created

Everything is in one resource group, in UK South:

| Resource | Purpose |
| --- | --- |
| Log Analytics workspace | Container logs, capped at 0.1 GB a day |
| User-assigned managed identity | Pulls images and, for the planner, calls Microsoft Foundry. No keys or passwords |
| Container Registry (Basic) | Holds the studio and API images, tagged with the git commit |
| Container Apps environment (Consumption) | Runs both apps |
| `mdesk-web` | The studio: the same Next.js build and Dockerfile CI scans. Public HTTPS, one warm replica, up to two |
| `mdesk-api` | The FastAPI service, internal only. The studio reaches it as `http://mdesk-api` through same-origin `/api` paths. One replica |
| Budget (optional) | Email alerts at 50%, 80% and a 100% forecast, when `AZURE_BUDGET_EMAILS` is set |

With the planner switched on (`assistant: true`), the API mounts `POST /api/assistant/plan`. It reads a free-form
Ask MatchDesk question into a query plan on Foundry and never writes an answer: the studio computes and verifies
every figure itself. Each call is capped at 200 output tokens and 10 seconds, with at most 20 calls a minute and
400 a day. One replica means those caps are also the totals.

## Cost

About $10–20 a month in UK South, mostly the registry (~$5) and two small always-warm replicas, much of which is
inside the Container Apps monthly free grant. Planner calls cost a few pence a day at the capped rate.

## One-time setup (owner)

1. Create the resource group, for example `rg-matchdesk-demo` in UK South.
2. On the identity GitHub Actions already uses for Foundry, add a federated credential for this repository's
   `development` branch, and give it **Contributor** on that resource group only.
3. In GitHub, set the secret `AZURE_SUBSCRIPTION_ID` and the variable `AZURE_RESOURCE_GROUP`. Optionally, set
   `AZURE_BUDGET_EMAILS` to a JSON array of addresses.
4. After the first deploy, give the managed identity `mdesk-demo-id` the **Azure AI User** role on the Foundry
   project. The workflow summary prints its principal ID. Until then the planner answers "unknown", and the studio
   falls back to its built-in parser.

## Deploy

Run **Azure demo (studio and API)** on `development`:

1. `mode: what-if` previews the base resources and changes nothing.
2. `mode: deploy`, with `confirm: DEPLOY_MATCHDESK_DEMO_TO_AZURE`:
   - creates the base resources;
   - builds both images from the exact commit and pushes them;
   - creates or updates both apps;
   - smoke-tests the public pages, the security headers, `/api/health` and, if switched on, the planner.

## Rollback

Delete the resource group. The Vercel copy of the studio is unaffected.
