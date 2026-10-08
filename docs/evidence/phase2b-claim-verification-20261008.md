# Phase 2B deterministic claim verification qualification — 8 October 2026

Status: **TESTED** on development source
`6bff563d0d2b66eb9538513d0b77829872edccd1`.

This evidence covers P2-02 only: deterministic verification of MatchDesk claims
against accepted Phase 1 events, registered metrics and an explicit EvidenceRecord.
It does not certify live agent execution, model quality, publication authority,
Azure deployment or production readiness.

## Verification rules

The verifier applies the following fail-closed rules:

- every claim evidence reference must be present in the supplied EvidenceRecord;
- every cited event must also exist in the accepted event input;
- accepted event input cannot mix match identities outside the EvidenceRecord match;
- measured claims are recomputed through the registered Phase 1 metric engine;
- the claim unit must match the registered metric unit;
- `eq`, `gte` and `lte` comparators are evaluated against the recomputed value;
- a passing measured claim is `verified`; a numerical mismatch is `needs_revision`;
- tactical prose can become only `supported_inference` when every cited event exists;
- event-fact prose without a registered semantic assertion is `needs_revision`, not
  `verified`, because evidence existence alone cannot prove the meaning of arbitrary text;
- missing, mixed or incompatible evidence is `blocked`;
- each VerificationResult is bound to the exact EvidenceRecord content digest.

Verification status remains separate from producer approval and publication authority.

## Hosted qualification

All required hosted workflows passed on the exact implementation source:

| Workflow | Run | Result |
|---|---:|---|
| Foundation CI | 37833033850 | PASS |
| Dependency audit | 37833033906 | PASS |
| Source security | 37833035687 | PASS |
| Foundation integration | 37833034000 | PASS |

Foundation CI executed 235 tests on Python 3.12.15. The implemented `matchdesk`
package measured 98.56% total coverage across 932 statements and 316 branches.
The new verification module measured 87% coverage; retained defensive branches include
invalid internal comparator/metric-runtime paths that are already constrained by strict
public contracts. Ruff, formatter checks and strict mypy passed, and the frontend build
remained green.

Foundation integration passed real runtime/PostgreSQL checks, locked Chromium
regressions, complete scans of the exact runtime-tested image IDs and the independent
native-image verdict.

## Boundaries

P2-02 does not parse arbitrary prose into facts, call a language model, create a
producer approval, persist verification durably or authorize publication. Event facts
need a future registered semantic assertion/checker before they can receive
`verified` status.

P2-03, specialist execution interfaces and scoped read tools, is the next controlled
work item. Live Agent Framework / Foundry integration remains P2-04 and separately gated.
