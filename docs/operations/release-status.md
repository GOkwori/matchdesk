# Current release and acceptance ledger

**As-of:** 25 October 2026. **Change control:** source documentation only;
this ledger is not approval to alter branches, deploy or publish.

| Reference | Exact SHA | Scope / evidence |
| --- | --- | --- |
| Protected `development` | `f65e07e94e30a9280a720d31863f22fbc1f5a62f` | Latest source inspected |
| `release/submission-2026-10` | `6fe0bf54db92b7cce69bfd45fd99da0d793ab971` | Latest evidenced Azure demo source |
| Protected `main` | `31371b06b23ee61f25d5b9f6ccceb9b3ae7bb222` | Unchanged since 9 October |
| PR #79 delivery rehearsal head | `21439e71d9e15bdbcc46c336285eaec415793ee5` | Merged; five workflow groups passed, no executor activation |
| PR #106 judge-demo head | `24460c069fa2ce6796a6a5d82efa1a4df283a4b1` | Closed without merge; synthetic CI passed, no independent J64 acceptance |

## Current exact-head automation evidence

| Gate | Status | URL |
| --- | --- | --- |
| Foundation CI | PASS | [40129492323](https://github.com/GOkwori/matchdesk/actions/runs/40129492323) |
| Source security | PASS | [40129492294](https://github.com/GOkwori/matchdesk/actions/runs/40129492294) |
| Dependency audit | PASS | [40129492330](https://github.com/GOkwori/matchdesk/actions/runs/40129492330) |
| Foundation integration | ATTEMPT 1 FAIL, ATTEMPT 2 PASS | [40129492295](https://github.com/GOkwori/matchdesk/actions/runs/40129492295) |
| Delivery control | PASS | [40162579945](https://github.com/GOkwori/matchdesk/actions/runs/40162579945) |
| Azure deployment | PASS on older release SHA `6fe0bf54db92b7cce69bfd45fd99da0d793ab971` | [40125200378](https://github.com/GOkwori/matchdesk/actions/runs/40125200378) |

**Retain failed evidence:** The first integration attempt reported colour-contrast
violations in desktop tactical controls and labels; the passing second attempt
on identical source proves test completion, not root-cause remediation.

## Promotion/acceptance boundary

- A successful push/PR CI run proves tests for that source/runner, not an independent
  human demo rehearsal, accessibility conformity, penetration test, production identity
  or publication authority.
- The last source contains later voice-over changes not evidenced at the older released
  SHA; verify the exact build revision before claiming features publicly.
- Owner-controlled submission, production, paid Azure changes, real producer writes,
  competition authorisation and `main` promotion remain separate decisions.
- A generated diagram is explanatory and must not be used as runtime evidence.

Follow [implementation inventory](../implementation-inventory.md) and
[ownership/provenance](../engineering/ownership-and-provenance.md) for the scope.
