# Requirement traceability

| Requirement | Current implementation | Current tests/evidence | Outstanding acceptance |
|---|---|---|---|
| R1 | Seeded synthetic match engine with four normal scenarios plus one fault stream | Phase 1A evidence; simulator and reducer regressions | Phase 1 acceptance complete |
| R2 | Ordered/idempotent ingestion, football-state reducer, six registered metrics and five deterministic moment detectors | Phase 1A-E evidence; hosted CI/integration/security | Phase 1 acceptance complete |
| R3 | Typed four-specialist orchestration control plane with bounded retries, timeouts, verification hand-off and recovery | Phase 2A evidence; 226 hosted tests; orchestration module 100% statement/branch coverage | Implement scoped execution adapters, live specialist runtimes and end-to-end recovery evaluation |
| R4 | Claim/evidence/result contracts; structural truth remains separate from verification | Claim tests, HTTP distinction test, Phase 2A verification hand-off | Implement deterministic claim verifier, complete claim coverage and inference review |
| R5 | Approval binding contract only | Hash varies with language | Producer identity, editor, review and transactional publisher |
| R6 | Design only | NOT_RUN | Overlay, commentary and recaps |
| R7 | Audience/language fields in binding | Contract validation | Three personas and languages with fact preservation |
| R8 | Local workbench source | API tested; UI build NOT_RUN | Isolated live judge sessions and deployment |
| R9 | Hosted CI, dependency/source-security gates, runtime/browser and native-image qualification with source-bound evidence | Phase 0/1 closure records and Phase 2A evidence | Add live-model/recovery evaluation, visual/accessibility and later deployment qualification |

Source: `backend/src/matchdesk`; tests: `backend/tests`; results: [evidence index](../evidence/INDEX.md).
The table never treats a contract or plan as the complete implementation of a requirement.
