# Verification and publication design

Status: claim/evidence/approval contracts implemented; verifier and publisher planned.

A measured claim is checked by a named query over the authoritative event revision.
An event fact must match identity, type, team, player and period window. A tactical
inference is labelled analysis and must use appropriately qualified wording. Counting
supporting events or detecting the word "may" is not proof of tactical causality.

The current `structurally_valid` response explicitly returns `evidence_verified: false`.
No API caller can turn the contract workbench into an approval or publishing endpoint.

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
