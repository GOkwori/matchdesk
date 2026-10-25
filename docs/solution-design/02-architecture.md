# Architecture and trust boundaries

**Status (25 October 2026):** The implemented synthetic-only demo is deployed
at an older release revision. This chapter distinguishes working source,
deployed-demo evidence and proposed production architecture.

![Implemented demo runtime](../diagrams/runtime-implemented.svg)

Source: [editable Mermaid map](../diagrams/runtime-implemented.mmd).
See [release ledger](../operations/release-status.md) for actual SHAs.

## Implemented topology

The Next.js studio provides a public responsive demonstration and a same-origin
API path. On Azure Container Apps, `mdesk-web` fronts an internal FastAPI
`mdesk-api`. Public viewers can use synthetic replay, verified statistics,
moment detection, overlays, stories, recaps, the optional Ask planner,
read-only MCP and opt-in live specialist runs.

The backend separates `api/` route boundaries from `domain/` football
ingestion, reducer, registered metrics, claim binding, verification, agent
workflow, producer-domain policy and output generation.

The demonstration uses a **single synthetic match** and a bounded event
log. Tracking numbers are synthetic. The browser has a parity-tested
TypeScript implementation of the registered metrics and verifier. The
server retains authority over its evidence revision/digests.

## Agent and verification trust boundary

![Agent and verification flow](../diagrams/agent-verification-implemented.svg)

Tactical Analyst, Narrative Composer, Editorial Reviewer and Audience
Adapter run through bounded Microsoft Foundry/Agent Framework workflows.
Their outputs are **proposals**. The deterministic verifier recomputes
registered metrics and checks the asserted text, reference and window.
Invalid or unsupported claims are rejected or receive bounded revision.
Models do not gain authorisation by producing a favourable status.

## Producer and identity boundary

The database-backed producer command and approval logic has extensive
disposable PostgreSQL tests. Public producer approval in the studio is
a **browser-only demo** with SHA-256 version binding, staged retry and
approval withdrawal on edits. It is not an authenticated human producer
action and does not publish to real destinations.

The shipped Next.js workforce BFF is explicitly disabled. A real
workforce identity, step-up, limited tenant/session permissions, independently
validated host trust and real outbox delivery remain separately controlled.
Customer federation via External ID is planned, not an active public login
authority. See [ADR-0011](../decisions/ADR-0011-federated-authentication.md).

## Source, deployment and release authority

![Release authority flow](../diagrams/release-authority-implemented.svg)

Automation checks the exact source head; a separately approved deployment
identifies the Azure revision. Neither can satisfy genuine human review,
manual accessibility, competition submission or production publishing.
Development and release branch SHAs differ: see
[release ledger](../operations/release-status.md).

## Target (not deployed)

The existing [target architecture](../diagrams/architecture-target.png)
is **proposed**, including licensed match feeds, full production PostgreSQL,
isolated identity tenants, private network, durable model budgets, signed images,
independent assurance, authenticated publication and production-scale recovery.
It must not be mistaken for the Azure demo.
