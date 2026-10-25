# Infrastructure and deployment

**Implemented and deployed demo:** Azure Container Apps in UK South
hosts a public Next.js studio and an **internal-only FastAPI API**.
The Azure Container Registry stores source-tagged images; Application
Insights/Log Analytics collects traces and diagnostic events;
managed identity is used instead of static Foundry/Speech API keys.
The last evidenced Azure demo source is `6fe0bf54db92b7cce69bfd45fd99da0d793ab971`.

![Runtime topology](../diagrams/runtime-implemented.svg)

[Editable diagram](../diagrams/runtime-implemented.mmd) ·
[Azure runbook](../operations/azure-demo.md) ·
[Release ledger](../operations/release-status.md)

## Local/CI topology

`docker-compose.yml` defines PostgreSQL, FastAPI and Next.js, with
loopback-only web/API host ports, an unexposed database port, read-only
service filesystems, dropped Linux capabilities, no-new-privileges and
ephemeral local secrets. The integration workflow exercises PostgreSQL
persistence, permission boundaries, browser journeys and native image
vulnerability scans in disposable runners.

## Demo deployment controls

[`.github/workflows/azure-demo.yml`](../../.github/workflows/azure-demo.yml)
requires explicitly selected deployment mode and a typed owner
confirmation for deploy, uses OIDC to Azure and records the checked
source. A successful earlier deployment does not mean later source
changes are live. The Vercel mirror is **studio-only** and cannot
stand in for API/MCP/Foundry features.

## Not deployed or qualified

The public demo is not the target private-cloud production stack.
It has no licensed live match feed, authenticated workforce producer
publishing, managed production PostgreSQL, private WAF architecture,
full recovery programme or independent production security sign-off.
The [main infrastructure Bicep](../../infra/azure/main.bicep)
describes a future target, not the actual demo inventory.

See [cost governance](../operations/cost-estimate.md); the old
"no Azure resources provisioned" statement was historical and
is no longer accurate.
