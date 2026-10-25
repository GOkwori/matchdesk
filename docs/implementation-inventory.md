# Implementation inventory and capability boundaries

**Source reviewed:** `development` at `f65e07e94e30a9280a720d31863f22fbc1f5a62f`, 25 October 2026.
This is a source/evidence reconciliation, not a live website penetration test,
a production certification, an independent human accessibility assessment or
a guarantee of the current public endpoint's availability.

| Area | Implemented in source | Last confirmed live / evidence | Critical qualification |
| --- | --- | --- | --- |
| Next.js studio, guided tour, replay and evidence pages | Yes | Azure deployment at `6fe0bf54db92b7cce69bfd45fd99da0d793ab971` (24 October) | Synthetic single-match demo, not real league feed |
| Event replay, reducer, 18 metrics, moment detectors | Yes | 1,421 synthetic events; stream verification documented | Tracking speeds/distances modelled; not measured from real video |
| Four Foundry agents | Yes: opt-in live workflow | Recorded and live runs; multiple historical traces | Cost-capped, fallible, no approval or publication authority |
| Deterministic server claim verifier | Yes | Registered metrics, semantic text binding, benchmark | English vocabulary and scoped claims only |
| Browser verifier | Yes: parity-tested TypeScript port | Historical cross-runtime benchmark + current CI | No independent proof of universal semantic correctness |
| Overlays, recaps, stories, EN/ES/FR variants | Yes | Azure replay/Spanish/French checked 23 October | Native-speaker review still not independently signed off |
| Read-only MCP endpoint | Yes: host-enabled | Initialize/tools/check_sentence tested 23 October | Public demo tool is read-only; no source/mutation authority |
| Producer review and publication domain | Tested adapters/transaction logic | Browser-only demo D-031 approval and simulated retry | No trusted workforce session or real external destination |
| Browser-only producer approval | Yes | Checked in hosted demo 23 October | Explicitly not real producer approval or actual publication |
| Workforce producer BFF | Explicit disabled route in shipped frontend | None | Human authentication and authority not activated |
| Azure AI Speech voice-over | Implemented on development after 24 October | **Not independently confirmed at current submission release SHA** | Host flag + resource prerequisite; local/device fallback |
| Azure infrastructure / telemetry | Implemented and previously deployed | Azure demo run 40125200378 at `6fe0bf54db92b7cce69bfd45fd99da0d793ab971` | Current source/release parity required before new claims |
| Delivery supervisor/orchestrator | Offline read-only control, tests and scheduled inspection | PR #79 exact-head CI and delivery control successful | **No authenticated coding executor/always-on local host activation** |
| Automation CI, source/security, runtime/native-images | Implemented | Current SHA checks passed, integration attempt 2 | Original contrast failure retained; manual assessment missing |
| Public submission video | Script and judging guide exist | No verified video link in README | Independently record, review and submit |
| Manual WCAG 2.2 AA | Automated audit and unexecuted runbook | Issue #52 OPEN | NOT RUN / no independent conformance claim |
| Real external match/event feeds | Adapter/design boundaries exist | No licensed source evidenced | Production integration not qualified |

## Verification and known failures

- Source `f65e07e`: Foundation CI [40129492323](https://github.com/GOkwori/matchdesk/actions/runs/40129492323), Source security [40129492294](https://github.com/GOkwori/matchdesk/actions/runs/40129492294), Dependency audit [40129492330](https://github.com/GOkwori/matchdesk/actions/runs/40129492330) and delivery control [40162579945](https://github.com/GOkwori/matchdesk/actions/runs/40162579945) passed.
- [Integration 40129492295](https://github.com/GOkwori/matchdesk/actions/runs/40129492295) **failed on attempt one** at `/match/nbr-riv/tactical` in the desktop axe contrast check; **both runtime-browser and native-images passed on attempt two** (25 October).
- Backend package coverage was 94.61% on the observed Foundation CI run; this is not security certification.
- [Benchmark](evidence/verifier-benchmark-20261024.md): 810/810 synthetic mutations rejected and 295/295 generated truthful variants accepted; this measures own-rule test coverage, not all possible claims or linguistic quality.
- [Owner input holds](https://github.com/GOkwori/matchdesk/issues/65), [manual accessibility](https://github.com/GOkwori/matchdesk/issues/52), [producer](https://github.com/GOkwori/matchdesk/issues/61), [audience](https://github.com/GOkwori/matchdesk/issues/62) and [assurance](https://github.com/GOkwori/matchdesk/issues/63) remain separately tracked.

## Diagrams

[Implemented runtime](diagrams/runtime-implemented.svg) ·
[agent/evidence flow](diagrams/agent-verification-implemented.svg) ·
[release authority](diagrams/release-authority-implemented.svg) ·
[diagram register](diagrams/README.md).
