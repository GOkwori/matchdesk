# Requirement traceability

| Requirement | Current implementation | Current tests/evidence | Outstanding acceptance |
|---|---|---|---|
| R1 | Seeded synthetic match engine with four normal scenarios plus one fault stream | Phase 1A evidence; simulator and reducer regressions | Phase 1 acceptance complete |
| R2 | Ordered/idempotent ingestion, football-state reducer, six registered metrics and five deterministic moment detectors | Phase 1A-E evidence; hosted CI/integration/security | Phase 1 acceptance complete |
| R3 | Four-specialist workflow runs end to end (`agent_workflow`): role-scoped traced tools, bounded retries and timeouts, verification loop back to the composer, Agent Framework/Foundry executor and a deterministic rehearsal | `test_agent_workflow.py` (normal, never-passing, malformed, out-of-scope and bad-adapter providers); committed trace re-verified in CI | Record and commit a live Foundry trace with the "Record live agent workflow" action |
| R4 | Deterministic verifier: registered metrics at stated precision, sentence-to-assertion binding, citation semantics, evidence window, registered event facts; exact TypeScript port | `test_claim_text_binding.py`, `test_verification.py`; 45-case Python/TypeScript parity fixture | More registered event-fact queries (cards, substitutions) |
| R5 | Producer review domain and PostgreSQL compare-and-swap store with append-only audit; studio composer, queue and locked Approve | Real-PostgreSQL CAS, rollback and restart tests; browser journeys | Authenticated producer, approval and publication (unmerged authority work) |
| R6 | Fan story with computed "How we checked this" rows; Match Centre style preview in the composer | Browser tests; story checks are verifier results in the export | Broadcast overlay and recap formats |
| R7 | Audience Adapter produces EN/ES/FR × analyst/fan/caption variants citing verified claims only | Workflow tests reject variants citing unverified claims | Human language review of ES/FR |
| R8 | Routed studio with a seven-stop guided tour, offline support and per-route metadata; loopback judge workbench | 108 studio browser tests at three viewports, axe on every page, visual baselines | Public hosting and recorded video |
| R9 | Hosted CI, dependency/source-security gates, runtime/browser and native-image qualification with source-bound evidence | Phase 0/1 closure records and Phase 2A evidence | Add live-model/recovery evaluation, visual/accessibility and later deployment qualification |

Source: `backend/src/matchdesk`; tests: `backend/tests`; results: [evidence index](../evidence/INDEX.md).
The table never treats a contract or plan as the complete implementation of a requirement.
