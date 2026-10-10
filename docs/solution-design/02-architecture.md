# Architecture and trust boundaries

Status: proposed whole-system design; Phase 0/1/2 VERIFIED / COMPLETED, Phase 3 P3-01/02/03 domain contracts TESTED and P3-04/05 IN PROGRESS.

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
agents, API and infrastructure. Phase 1 implements the deterministic simulator, ingestion,
reducer, registered metrics and moment detection. Phase 2 implements a model-independent
typed orchestration control plane for four specialist roles, scoped read-only specialist
tools, deterministic claim verification, a fail-closed Microsoft Agent Framework / Foundry
runtime, bounded retry/timeout/recovery controls and deterministic model-output evaluation.
One bounded live Foundry tactical proposal has passed the same evidence-verification path.
Phase 3 includes tested producer review, pure-domain publication gating and broadcast
output envelopes. The PostgreSQL producer-case tables, generation/audit CAS and
rollback/restart semantics have been tested through the actual pinned Psycopg Python
adapter using a restricted role in disposable integration, including independent
audit-row reconciliation and DB restart. This is not production persistence.
The multi-provider sign-in decision is now approved in
[ADR-0011](../decisions/ADR-0011-federated-authentication.md). The customer
journey will broker Apple, Google, Facebook, personal Microsoft, organisational
Entra ID and local email through a **separate Entra External ID tenant**.
Producers/admins will use a workforce Entra tenant. Both issuers, API audiences,
tenant IDs, sessions and entitlements remain isolated; all users are mapped by
trusted issuer+tenant+immutable subject, never by email matching.

```mermaid
flowchart TB
    Users[Fans and customers] --> BFF[Browser-delegated BFF login]
    Social[Apple Google Facebook and personal Microsoft] --> Broker[Entra External ID]
    Local[Email OTP or password] --> Broker
    Orgs[Approved organisations via OIDC or SAML] --> Broker
    BFF --> Broker
    Broker --> CustomerAPI[Customer broker JWT and server-owned viewer grants]
    Staff[Human producer and administrator] --> Workforce[Workforce Entra ID and MFA]
    Workforce --> ProducerAPI[Separate workforce JWT and session grants]
    ProducerAPI --> Review[Version-bound human review]
    Review --> Publish[Governed publication gate]
```

The customer broker and protected BFF sessions are **PLANNED, not live**.
An offline workforce JWT verifier is implemented, but trusted production
JWKS retrieval, session authorisation, authenticated HTTP producer commands,
transactional delivery and production workflow persistence remain later work.

Numerical truth belongs to registered deterministic queries. Narrative reasoning is
an interpretation of that evidence. Publishing authority belongs to an authenticated
producer action, never an agent's generated status. Model/tool calls use scoped read
interfaces and cannot modify metric evidence or approval records. The Phase 2 controller,
not a specialist runtime, owns role order, retry budget, timeout classification, recovery
budget and eligibility to cross the verification hand-off. Live model output remains a
non-authoritative proposal and must pass deterministic evaluation before later workflow
stages can rely on it.

Replay cursors, workflow identities and published outputs must include session and
replay generation. Resetting one judge session cannot invalidate another. A future
transactional outbox links committed publication to its output stream; a crash between
commit and delivery must not duplicate publication.

SSE conveys versioned state changes and resumes from a scoped cursor. An HTTP command
changes state only after request identity, authorisation and concurrency checks pass.
