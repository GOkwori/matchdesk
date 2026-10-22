# Azure deployment plan: sign-in and hosted backend

Status: **PLAN FOR OWNER APPROVAL. Nothing has been provisioned.** Date: 22 October 2026.

The competition demo stays where it is: https://matchdesk-seven.vercel.app, built from
`release/submission-2026-10`. This plan adds a second, Azure-hosted MatchDesk with real producer
sign-in and a database, without touching the demo.

## What would be created

All in one resource group, region UK South, from [`infra/azure/main.bicep`](../../infra/azure/main.bicep)
(compiles and lints clean with Bicep 0.30):

| Resource | Setting | Why |
| --- | --- | --- |
| Container Apps environment | Consumption, in a private VNet | Runs the web app and the API; both scale to zero when idle |
| `web` container app | External HTTPS, 0–3 replicas | The studio, including the workforce BFF |
| `api` container app | **Internal only**, 0–2 replicas | Reachable only from the web app |
| PostgreSQL Flexible Server 16 | Burstable B1ms, 32 GiB, 7-day backups, **private access, Entra sign-in only (no passwords)** | Producer review, grants, sessions, audit (migrations 001–014) |
| Key Vault | RBAC, purge protection | The studio's client certificate and app secrets |
| Container Registry | Basic, admin user off | Images, pulled by managed identity |
| Managed identity | User-assigned | The apps' identity for the registry, Key Vault and PostgreSQL |
| Log Analytics | 30-day retention, **0.1 GB/day cap** | Logs, capped so they cannot run up cost |
| Budget | Default 40/month, e-mails at 50%, 80% and 100% forecast | Spend alerts |

Producer sign-in uses Microsoft Entra ID in your tenant, set up by
[`infra/azure/entra-workforce.sh`](../../infra/azure/entra-workforce.sh):
- a producer API app with one scope, `producer.decide`;
- the studio app (certificate credential, no secret; sign-in limited to a "MatchDesk producers" group);
- an authentication context, `c1`, protected by a Conditional Access policy that requires MFA before approve or reject.

This matches what `apps/web/src/workforce` verifies today.

## Estimated monthly cost (USD, pay-as-you-go, UK South)

Estimates only: confirm in the [Azure pricing calculator](https://azure.microsoft.com/pricing/calculator/)
before approving.

| Item | Light use (demo, a few hours a week) | Worst case (always on) |
| --- | --- | --- |
| Container Apps (2 apps × 0.5 vCPU, 1 GiB) | ~$0, inside the monthly free grant of 180,000 vCPU-s and 360,000 GiB-s | ~$75 |
| PostgreSQL B1ms + 32 GiB storage | ~$18 (about $14 compute in UK South + storage) | ~$18 |
| Container Registry Basic | ~$5 | ~$5 |
| Key Vault, private DNS zone, VNet | ~$1 | ~$1 |
| Log Analytics (capped at 0.1 GB/day) | ~$0, inside the free 5 GB/month | ~$0 |
| **Total** | **~$25/month** | **~$100/month** |

Not included:
- **Microsoft Entra ID P1**, needed for Conditional Access step-up: about $6 per producer per month, unless your Microsoft 365 plan already includes it.
- **Live agent runs on demand** (off in this plan). The recorded run used 25,731 tokens. Cost per run depends on your Foundry model deployment; on a small model it is about a cent.

The budget alert e-mails you; it does not stop spending. Scale-to-zero, the log cap and the B1ms
size are the cost controls.

## Security choices for you to confirm

1. **API not on the internet:** only the web app can reach it.
2. **PostgreSQL without passwords:** Entra sign-in only. An Entra group administers it; the apps use a managed identity.
3. **Key Vault on its public endpoint, RBAC only.** A private endpoint adds about $7/month. Recommended later; not needed for a pilot.
4. **The web app moves to Azure for the signed-in version.** Vercel keeps serving the public demo. The alternative, keeping the web app on Vercel and exposing the API publicly with its own authentication, is cheaper but weaker.

## Code still needed before Azure is useful

The infrastructure is half of it. These are code tasks, tracked in the delivery plan:

1. **API to PostgreSQL with Entra tokens:** a connection factory that uses the managed identity's token as the password.
2. **Migration runner:** apply migrations 001–014 as the admin group, then grant the app identity its restricted roles.
3. **Real workforce host:** today `/api/workforce/producer/*` ships a null adapter by design. A reviewed host adapter must wire it to Entra (certificate client assertion, signing keys) and to the PostgreSQL session, step-up and grant stores.
4. **Publishing:** outbox and destinations with a language-review gate.
5. **Live agents on demand:** a daily run cap and a per-run token cap, with `MATCHDESK_FOUNDRY_ENABLED` off by default.
6. **Ask MatchDesk planner (optional):** `MATCHDESK_ASSISTANT_FOUNDRY_ENABLED` (off by default) lets the API read free-form questions into query plans with the same Foundry project. Each call is capped at 200 output tokens and 10 seconds, with at most 20 calls a minute and 400 a day per replica. The studio computes and verifies every answer itself, so the assistant works without it.

## Sequence once you approve

1. Create a resource group. Add a federated credential for this repository to the existing deployment identity, with the Contributor role on that group only.
2. In GitHub, set the secret `AZURE_SUBSCRIPTION_ID` and the variables `AZURE_RESOURCE_GROUP`, `AZURE_BUDGET_EMAILS` and `AZURE_PG_ADMIN_GROUP_ID`.
3. Run **Azure deployment (plan or deploy)** with `what-if`. This is read-only; review the listed changes.
4. Set the variable `AZURE_DEPLOY_APPROVED=true`, run `deploy` with the confirmation text, then unset the variable.
5. Run `entra-workforce.sh` with the web URL from the deployment output, then finish the manual steps it prints.
6. Ship the code tasks above. Each lands as a reviewed PR, with the workforce host switched on only after its own tests pass.

The workflow can only be started once `development` is the default branch (ADR-0012) or the workflow
file is on `main`.

**Rollback:** delete the resource group. The demo on Vercel is unaffected throughout.
