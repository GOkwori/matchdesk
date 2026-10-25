# Cost model and governance

**State:** Azure competition resources **have been deployed**. Earlier
"NOT_ESTIMATED / no resources created" wording described an obsolete foundation
stage and does not represent the current implementation.

## Implemented demo cost drivers

| Service | Current technical dependency | Cost / limit evidence |
| --- | --- | --- |
| Azure Container Apps (studio/API) | Hosted web and private API, warm replicas | [Azure demo runbook](azure-demo.md) estimates around $10–20/month for the *demo stack in total*, not a verified invoice |
| Azure Container Registry (Basic) | Two pinned service images | Included in same estimate |
| Application Insights / Log Analytics | Trace + log collection | Log Analytics ingestion capped by configuration intent; actual billed usage not independently retrieved |
| Microsoft Foundry | Live bounded agent runs and planner | Token usage occurs; budget/charges depend on model, account and volume |
| Azure AI Speech (optional) | Verified-feed synthesis | Source caps 60 new clips/hour and 400/day **per live process**, in-memory cache |
| Vercel | Studio-only hosted copy | Plan/billed usage not independently verified |
| PostgreSQL | Local/CI and future production | No claim that the public demo uses managed PostgreSQL; price future managed service separately |

## Governance

No finance or invoice connector was queried for this ledger. **Actual recurring
cost, credits, remaining budget and effective Azure spending limits are
NOT VERIFIED.** The historical estimate is not a spending guarantee. Azure budget
alerts do not hard-stop billing.

Before authorising *new or expanded* paid usage, produce a current UK South
bill of materials specifying region, SKUs, replica minimums, query/token rate,
Speech volume, analytics retention, price date, currency, credits assumptions,
free alternatives, teardown/rollback and owner approval. Confirm subscription
policies and provider-side spending controls independently.

No new paid resources or deployments are authorised by this document.
