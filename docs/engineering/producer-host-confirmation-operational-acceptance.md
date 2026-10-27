# Producer host-confirmation operational acceptance — DEV-only contract

**Status:** implementation and acceptance specification only, 20 October 2026.
PR #105 disposable PostgreSQL bridge at `50f3117` passed 4/4 mandatory CI.
That proves synthetic signed approvals, restricted database grants, single-use
execution and read-only persisted provenance under disposable CI. It **does not**
prove a human performed a confirmation, a real Entra Conditional Access policy
enforced step-up, a real signing key was held independently, or DEV UAT passed.
No live API mounting, deployment, production DB migration or publishing follows
from this document.

## Trust and ownership boundaries

1. **Verified actor, never browser authority.** The API resource server verifies
   an issuer/audience/client/scope-pinned delegated access token, independent
   current workforce session entitlements, verified session ownership, and an
   independently authoritative current Entra Conditional Access result for the
   requested context and app. A token `acrs` claim alone is insufficient.
2. **A real human action, never a model-issued decision.** A separate server-
   authenticated custom-dialog host records a specific user's deliberate
   confirmation of the immutable displayed tenant, session, output, action,
   expected generation, evidence digest, case content hash and audit digest.
   The BFF cannot assert that a user clicked anything. Reject unattended,
   replayed, CSRF-forged, cross-origin or model/tool-direct calls.
3. **Provenance recorder independent of producer writer.** A dedicated,
   authenticated workload inserts an immutable event with a cryptographically
   random unique event ID and one-time confirmation ID. It can INSERT only into
   the event table, not UPDATE/DELETE existing events, issue grants, alter case
   or audit rows, or revoke confirmations. Revocation/cancellation belongs to
   another narrow workload writing a terminal event. Final database privileges,
   SECURITY DEFINER ownership, event ingestion function and replay constraint
   must be independently audited.
4. **Signing service separate from caller and recorder.** A dedicated signer
   with a non-exportable key if available receives a server-bound event
   reference, reloads the authenticated event and current entitlement/CA
   evidence, checks non-terminal state and exact contents, signs the canonical
   envelope with a narrowly pinned Ed25519 key and no arbitrary-sign API, and
   exposes it only through a scoped host-only resolver. No private signing keys,
   grants, tokens or issuer credentials may reach the browser or a model.
5. **Only one atomic mutation authority.** The producer bridge validates the
   signature, independently reads the exact event using its separate
   SELECT-only PostgreSQL role, checks current CA/session identity again,
   then stages and issues with two separate logins. A restricted writer
   atomically consumes one grant with case CAS/audit append. Its success
   receipt never activates publishing.
6. **Revocation and time-of-check/use.** A terminal record written *after*
   the bridge's provenance read but *before* staging/issuance can otherwise
   race the authorization. Before operational activation, either the issuer
   must check the same authoritative terminal state under a transaction
   that serializes against revocation, or issuance must reject a revoked
   confirmation under a proven equivalent atomic database protocol. Merely
   re-reading in Python is not a sufficient cross-process race guarantee.
   Expiry, changed generation, operator/session revocation and concurrent
   signer/issuer requests all fail closed.
7. **Recovery.** Ambiguous network or database outcomes never trigger a blind
   retry, implicit success, or a legacy direct-DML fallback. A separate
   READ-only reconciler records exact command, grant, event, case generation
   and immutable audit status before a governed retry decision. Never leak
   those internal IDs in the public response.

## Mandatory design and evidence to be independently approved

| Area | Acceptance evidence |
| --- | --- |
| Event capture | Authenticated operator end-to-end DEV video/log and accessible custom dialog, with exact before/after hashes and action visibility |
| Login and CA | Tenant-specific enforced policy inspection, included actor/client/context, phishing-resistant/MFA control, fresh API token challenge and negative claims tests |
| Event isolation | No browser/model mutation API; issuer/stager/reader/recorder/revoker physical login separation, no privileged memberships or unexpected EXECUTE, DML, CREATE or TEMP |
| Signing | Key ID/version binding and rotation/revocation plan; signing credentials inaccessible to approval caller; arbitrary-sign and cross-event tamper negatives |
| One-use and concurrency | One winner in concurrent confirmation, terminal revocation racing issuance, expired event, duplicate event/nonce, stale case, cross-tenant and cross-session negatives |
| Audit/recovery | Independent owner/DBA readback, event-to-envelope-to-grant-to-case audit correlation, outage and lost-acknowledgement reconciliation with immutable logs |
| Frontend/API | Exact receipt allowlist, CSP/CSRF/origin/session protections, accessible keyboard and screen-reader dialogue, deny direct API/tool invocation without verified actor |
| Deployment | Forward-only migrations reviewed against real tenant schema, rollback and deprovision plan, zero-trust threat review, cost estimate and explicit human approval |

## Operational hard stops

- **NOT READY:** no production-grade independently authenticated host event
  ingestion service, key service or live Entra policy-assurance adapter is
  currently implemented by PR #105. Synthetic CI fixture rows are not
  operator provenance.
- **NOT READY:** the atomic issuer does not yet serialize a fresh terminal
  event-state check with concurrent revocation. That condition must be met
  and tested on real DEV PostgreSQL before operational mounting.
- **NOT READY:** no independently witnessed human DEV UAT, DBA/identity/security
  sign-off, or deployment/cost approval has been recorded.
- Keep PRs #89, #102 and #105 DRAFT; keep the producer HTTP integration
  unmounted; do not promote to `development`/`main`, deploy paid resources,
  publish content or activate live credentials from this acceptance contract.

**Next implementation decision:** prioritize terminal-revocation/issuer
serialization on disposable PostgreSQL and its negative concurrency test;
then build the independently authenticated event-ingestion and scoped signing
adapters and conduct real DEV operator acceptance.
