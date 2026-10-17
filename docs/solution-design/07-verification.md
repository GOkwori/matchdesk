# Verification and publication design

Status: claim/evidence/approval contracts implemented; verifier and publisher planned.

A measured claim is checked by a named query over the authoritative event revision.
An event fact must match identity, type, team, player and period window. A tactical
inference is labelled analysis and must use appropriately qualified wording. Counting
supporting events or detecting the word "may" is not proof of tactical causality.

The current `structurally_valid` response explicitly returns `evidence_verified: false`.
No API caller can turn the contract workbench into an approval or publishing endpoint.

## Stated precision and whole-match windows (17 October 2026)

- **Precision.** A `MetricAssertion` may carry `decimals`, the precision the claim is stated at. With it, `eq` passes when the recomputed value rounds half up to the asserted value: "58% possession" is `value 0.58, decimals 2` and is true of 57.96% and false of 58.6%. Rounding uses the shortest decimal form of the float (`round_half_up`), so every platform agrees. Without `decimals`, `eq` stays exact. A precision is rejected on `gte`/`lte` and when the value has more places than the precision.
- **Whole-match windows.** `MatchWindow.period` may be omitted. The window then covers both periods by match clock, and possession intervals are still walked per period, so no interval spans half-time.
- **One verifier, two runtimes.** `apps/web/src/studio/verifier.ts` is a branch-for-branch port of `verify_claim` and the registered metrics. `scripts/export_demo_data.py` writes `apps/web/tests/verifier-parity.json` from the real verifier (every status and blocking reason, every metric), and CI fails unless the port reproduces each status, query, reason, expected and observed value exactly. The studio shows the server's verdicts and re-checks the possession claim in the browser from the event log; if the two ever disagree, the screen says so.

## Required publication invariants

An approval must bind item/version, text digest, evidence revision/digest, replay,
persona and language. Editing text, adapting language or correcting relevant events
invalidates that approval. Verification must be rerun on the complete final text,
not only on a convenient subset of claims supplied by the writer.

The future state transition and outbox write must occur in one database transaction.
Use optimistic concurrency and unique idempotency keys. A race between producer edits
and publication must fail without publishing a stale version. A user-set status
field cannot replace a server-owned verification and approval record.

Fallback text still requires its own evidence checks. Explicitly injected errors
must be marked on screen and kept out of the authoritative event store. No percentage
should be labelled a calibrated trust score without an evaluation basis.
