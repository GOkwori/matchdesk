# Phase 3A producer review/version binding qualification — 9 October 2026

Status: **TESTED**.

Qualified source:
`bfa883597056c9c934f3e8fdce7cdc24adfeb73a`.

## Scope

P3-01 introduces a pure domain producer-review state machine over the existing
`ApprovalBinding` contract. It binds human review decisions to the exact item version,
replay, content digest, evidence digest, language and persona.

The qualified controls cover:

- review opening for one exact immutable binding;
- mandatory reverification before approval;
- stale-binding rejection for reverification and producer decisions;
- explicit rejection as a terminal decision for the current version;
- strictly increasing revision versions;
- replay/language/persona scope preservation across revisions;
- invalidation of a prior approval when a new revision is opened;
- immutable transition audit history;
- non-blank actor identity and transition reason requirements;
- fail-closed retrieval of an approved binding.

No publication side effect, authentication mechanism, persistence adapter or UI action
is claimed by P3-01.

## Hosted qualification

Exact-head hosted qualification passed:

| Workflow | Run | Result |
|---|---:|---|
| Foundation CI | 37957060648 | PASS |
| Foundation integration | 37957060489 | PASS |
| Dependency audit | 37957060542 | PASS |
| Source security | 37957060712 | PASS |

The preceding candidate `b9945ab63b4d05e24b65d089e32f9afcb2a074b1` retained a real
Ruff import-order failure after its functional tests passed. The import order was
corrected without weakening any gate.

P3-01 is **TESTED**. P3-02 version-bound publication gating is next.
