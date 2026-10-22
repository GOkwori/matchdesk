# Requirement traceability

| Requirement | Current implementation | Current tests/evidence | Outstanding acceptance |
|---|---|---|---|
| R1 | Seeded synthetic match engine with four normal scenarios plus one fault stream | Phase 1A evidence; simulator and reducer regressions | Phase 1 acceptance complete |
| R2 | Ordered/idempotent ingestion, football-state reducer, six registered metrics and five deterministic moment detectors | Phase 1A-E evidence; hosted CI/integration/security | Phase 1 acceptance complete |
| R3 | Four-specialist workflow runs end to end (`agent_workflow`): role-scoped traced tools, bounded retries and timeouts, verification loop back to the composer, Agent Framework/Foundry executor and a deterministic rehearsal | `test_agent_workflow.py` (normal, never-passing, malformed, out-of-scope and bad-adapter providers); live Foundry trace (21 Oct 2026) and rehearsal both re-verified in CI | Repeat live runs to measure how often the verifier sends claims back |
| R4 | Deterministic verifier: registered metrics at stated precision, sentence-to-assertion binding (value, subject, statistic word, negation, team, time window, clock and recorded detail), citation semantics, evidence window, registered event facts; exact TypeScript port | `test_claim_text_binding.py`, `test_verification.py`; 76-case Python/TypeScript parity fixture | More registered event-fact queries (cards, substitutions) |
| R5 | Producer review domain and PostgreSQL compare-and-swap store with append-only audit; studio composer, queue and locked Approve | Real-PostgreSQL CAS, rollback and restart tests; browser journeys | Authenticated producer, approval and publication (unmerged authority work) |
| R6 | Fan story with computed "How we checked this" rows; Match Centre style preview in the composer | Browser tests; story checks are verifier results in the export | Broadcast overlay and recap formats |
| R7 | Audience Adapter produces EN/ES/FR × analyst/fan/caption variants citing verified claims only; fan story in EN/ES/FR with every visible string, including accessible labels, in the selected language and an AI-assisted-translation notice | Workflow tests reject variants citing unverified claims; browser test checks `lang` and translated copy | Native-speaker sign-off on the [ES/FR review sheet](../testing/language-review-es-fr.md) |
| R8 | Routed studio with a seven-stop guided tour, offline support and per-route metadata; hosted at matchdesk-seven.vercel.app | 108 studio browser tests at three viewports, axe on every page, visual baselines | Recorded video |
| R9 | Hosted CI, dependency/source-security gates, runtime/browser and native-image qualification with source-bound evidence | Phase 0/1 closure records and Phase 2A evidence | Add live-model/recovery evaluation, visual/accessibility and later deployment qualification |

Source: `backend/src/matchdesk`; tests: `backend/tests`; results: [evidence index](../evidence/INDEX.md).
The table never treats a contract or plan as the complete implementation of a requirement.
