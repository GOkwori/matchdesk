# Architecture and trust boundaries

Status: proposed whole-system design with implemented Phase 0 boundary components.

```mermaid
flowchart TB
    Producer[Producer or isolated judge session] --> Web[Next.js producer desk]
    Web --> API[FastAPI boundary]
    API --> Store[(PostgreSQL events / evidence / approvals / audit)]
    Replay[Seeded replay worker] --> Engine[Pure reducer and metric engine]
    Engine --> Store
    Engine --> Jobs[Durable workflow jobs]
    Jobs --> Agents[Agent Framework with Foundry]
    Agents --> Verify[Deterministic verification]
    Verify --> Store
    API --> Publish[Version-bound publication gate]
    Publish --> Outputs[Overlay and audience feeds]
```

The modular backend separates simulation, ingestion, state, intelligence, verification,
agents, API and infrastructure. The Phase 0 source currently implements domain and
API modules only. No persistence adapter or agent execution is represented as complete.

Numerical truth belongs to registered deterministic queries. Narrative reasoning is
an interpretation of that evidence. Publishing authority belongs to an authenticated
producer action, never an agent's generated status. Model/tool calls use scoped read
interfaces and cannot modify metric evidence or approval records.

Replay cursors, workflow identities and published outputs must include session and
replay generation. Resetting one judge session cannot invalidate another. A future
transactional outbox links committed publication to its output stream; a crash between
commit and delivery must not duplicate publication.

SSE conveys versioned state changes and resumes from a scoped cursor. An HTTP command
changes state only after request identity, authorisation and concurrency checks pass.
