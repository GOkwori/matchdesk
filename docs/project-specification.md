# MatchDesk project specification

Owner: George Okwori. Baseline: 8 October 2026. Status: IN_PROGRESS; Phase 0 and Phase 1 VERIFIED / COMPLETED, Phase 2 P2-01 TESTED.

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

Phase 0 established contracts, local services, documentation, hosted qualification,
runtime/browser/security gates and protected repository promotion. It is complete on
main commit `773ba7cc2da60d14e5a1e3106b61fa202c93624b`.

Phase 1 builds the deterministic engine. P1-01 synthetic generation, P1-02 temporal
ingestion, P1-03 roster/score/possession reduction, P1-04 registered football metrics
and P1-05 deterministic moment detection are TESTED. P1-06 technical review passed,
the exact closure head was owner-approved and merged, and Phase 1 is VERIFIED /
COMPLETED, with the final status record on main commit `8e110607c6877efca431debe7f8b69b5f53db9d9`. Phase 2 adds agent orchestration and verification. P2-01, the model-independent typed orchestration control plane, is TESTED; P2-02 deterministic claim verification is next.
Phase 3 completes producer and audience flows. Phase 4 qualifies reliability and security.
Phase 5 packages the demonstration and submission. Work stops at each owner review gate.
The internal submission target is 26 October 2026.

## Evidence rules

Statuses distinguish PLANNED, IN_PROGRESS, IMPLEMENTED, TESTED, DEPLOYED, VERIFIED
and BLOCKED. A missing tool is not a pass. A stub is not a live model. A declaration
of source validity is not a claim verification. Owner approval requires an explicit record.

## Approved repository policy

[ADR-0010](decisions/ADR-0010-solo-maintainer-approval.md) records George's approved
solo-maintainer workflow. Main retains PR-only promotion and all required checks,
with zero additional approving reviews and no last-push approval. The owner must
still explicitly approve the exact proposed head and base after reviewing evidence.
Development retains history safeguards and ordinary development commits. This policy
supersedes the additional-reviewer requirement, not security gates or phase approval.
Ruleset activation and the Phase 0 protected merges are complete. Production deployment,
release tagging and later phase approvals remain separate.

## Open design decisions

Only main and development are authorised. Environment isolation, optional
auto-publication and the final inference-review policy require explicit decisions
before those capabilities are implemented. The [decision log](decisions/ADR-0005-baseline-conflicts.md)
records the boundaries. The deterministic Phase 1 path currently includes the tested
synthetic engine, temporal ingestor, football-state reducer, registered metric engine and
five deterministic moment detectors. P1-06 is COMPLETE and Phase 1 is VERIFIED /
COMPLETED. Phase 2 now includes a TESTED bounded orchestration control plane with four
locked specialist roles, typed state, retry/timeout/recovery budgets and a deterministic
verification hand-off. P2-02 claim verification is next. Live model and Azure work remain later controlled decisions.
