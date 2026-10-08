# Requirement traceability

| Requirement | Current implementation | Current tests/evidence | Outstanding acceptance |
|---|---|---|---|
| R1 | MatchEvent/Location boundary contracts | test_contracts.py, evidence index | Complete simulator, rosters, scenarios, full-match invariants |
| R2 | Window/event semantics only | Clock/window regressions | Ingest, reducer, metrics, five detectors |
| R3 | Design only | NOT_RUN | Four specialists, recovery and live workflow |
| R4 | Claim/evidence/result contracts; structure is not truth | Claim tests, HTTP distinction test | Query verifier, complete claim coverage, inference review |
| R5 | Approval binding contract only | Hash varies with language | Producer identity, editor, review and transactional publisher |
| R6 | Design only | NOT_RUN | Overlay, commentary and recaps |
| R7 | Audience/language fields in binding | Contract validation | Three personas and languages with fact preservation |
| R8 | Local workbench source | API tested; UI build NOT_RUN | Isolated live judge sessions and deployment |
| R9 | Foundation tests, contract/comment/doc checks, evidence writer | Dated local results | Hosted CI, scans, property/visual/integration/live-model/recovery suites |

Source: `backend/src/matchdesk`; tests: `backend/tests`; results: [evidence index](../evidence/INDEX.md).
The table never treats a contract or plan as the complete implementation of a requirement.
