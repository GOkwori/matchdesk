# MatchDesk project specification

Owner: George Okwori. Baseline: 8 October 2026. Status: IN_PROGRESS, Phase 0.

## Purpose and users

The product is a football production desk for a studio or streaming producer.
Its objective is to turn synthetic event streams into useful, inspectable stories
without letting a language model determine numerical truth or publishing authority.
A producer reviews content; analyst, casual-fan and caption views adapt the output.

## Required outcomes

| ID | Requirement | Acceptance outcome |
|---|---|---|
| R1 | Synthetic engine | Four seeded scenarios plus a fault scenario; reproducible bytes and valid football invariants |
| R2 | Match intelligence | Ordered, idempotent ingestion; documented statistics; at least five detected moment types |
| R3 | Multi-agent workflow | Four specialists, typed state, bounded retries, timeouts and recovery |
| R4 | Evidence verification | Every factual claim has support; measured claims are recomputed; unsupported text cannot publish |
| R5 | Producer desk | Inspect, edit, reverify, approve, reject and publish with auditable version binding |
| R6 | Broadcast outputs | Commentary, explainers, overlay JSON, half-time and full-time recaps |
| R7 | Audience adaptation | Analyst, casual-fan and caption output in English, Spanish and French |
| R8 | Judge access | Isolated, resettable demo sessions in a functioning accessible build |
| R9 | Quality evidence | Automated tests, regression, model evaluation, UI checks and source-bound reports |

## Golden path

Synthetic events update match state. A detector creates a moment and evidence record.
The Tactical Analyst and Narrative Composer propose a story. Deterministic checks
validate claims; editorial review can request revision. Audience variants are checked
again. A producer reviews the exact version. Only an approved, current version can publish.

## Scope and non-goals

The first release targets one match per isolated demo session, fictional participants,
an interactive 2D pitch and a single coherent producer desk. Video interpretation,
audio commentary, 3D recreation, billing and multi-match operational scale are deferred.
Fabric and Event Hubs are optional additions, not prerequisites for the first working path.

## Architecture baseline

Python/FastAPI, PostgreSQL, Next.js/TypeScript, Microsoft Agent Framework and Foundry,
with Container Apps and Bicep proposed for hosting. The runtime AI integration must
be real and evaluated before it is described as operational. Azure target IDs, model
quota and resource costs require discovery before provisioning.

## Delivery and gates

Phase 0 establishes contracts, local services, comments, documentation and checks.
Phase 1 builds the deterministic engine. Phase 2 adds agent orchestration and verification.
Phase 3 completes producer and audience flows. Phase 4 qualifies reliability and security.
Phase 5 packages the demonstration and submission. Work stops at each owner review gate.
The internal submission target is 26 October 2026.

## Evidence rules

Statuses distinguish PLANNED, IN_PROGRESS, IMPLEMENTED, TESTED, DEPLOYED, VERIFIED
and BLOCKED. A missing tool is not a pass. A stub is not a live model. A declaration
of source validity is not a claim verification. Owner approval requires an explicit record.

## Open design decisions

Only main and development are authorised. Environment isolation, optional
auto-publication and the final inference-review policy require explicit decisions
before those capabilities are implemented. The [decision log](decisions/ADR-0005-baseline-conflicts.md)
records the boundaries. The local foundation adds no remote branches, publication
or deployment authority.
