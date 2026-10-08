# PostgreSQL persistence

Date: 8 October 2026. Status: Accepted design direction; implementation planned.

## Decision and consequences

Use PostgreSQL for authoritative events, revisions, workflow state and producer approvals. Transactions will bind state changes and outbox delivery. No SQLite substitute is allowed in persistence qualification; a container declaration is not a tested integration.
