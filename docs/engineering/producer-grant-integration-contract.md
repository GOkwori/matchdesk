# Producer authorization contract reconciliation — DEV integration candidate

**Status:** architecture decision for the next *combined disposable* PR only.
Neither independent PR nor this document authorizes activation, live Entra/MFA,
human signing, publishing, production database migration, or deployment.

## Inputs and competing contracts

- PR #89: default-unmounted, bearer-validated workforce API and same-origin
  BFF; current grant-backed mutation adapter selects a host-held UUID from
  `matchdesk_producer_execution_grants`, then uses a restricted but
  **direct-DML-capable** case/audit writer.
- PR #102: independent, default-unused confirmation preflight, staging/issuer
  and restricted physical PostgreSQL logins. Its text-ID
  `matchdesk_producer_action_grants` record includes an exact normalized
  JSONB case SHA-256 and audit digest; one transaction invokes
  `matchdesk_commit_producer_grant` for consumption, case CAS and audit append.
- Both branches separately passed their required four CI workflows on
  20 October 2026. The passing results do **not** certify their combination,
  and synthetic CI confirmations do not prove real human step-up.

## Canonical candidate and invariants

1. **One execution authority:** the atomic action-grant writer from #102 is
   the only candidate operational producer mutation entry point. All five
   actions (create, edit, reverify, approve, reject) must use this path.
   No UUID translation, old `matchdesk_consume_producer_execution_grant`
   call, legacy boolean grant, or direct case/audit DML fallback is allowed.
2. **Verified human provenance:** a trusted host verifies the delegated API
   JWT and current tenant/session/actor permissions, independent enforced
   Conditional Access step-up, signed human confirmation and exact reviewed
   case. The browser sends only a bound intention, never authority or a
   client-picked grant/command ID. SQL staging records or hashes alone
   cannot authenticate the operator.
3. **Scope at issuance AND execution:** issuer binds tenant, issuer, actor,
   session, output, action, immutable approval binding, expected generation,
   canonical case hash, full audit digest, expiry and revocation. An
   independently authorized issuer writes the grant; the writer consumes it
   once under the same PostgreSQL transaction as case CAS and append-only audit.
   Unknown execution outcomes require independent readback, not blind retries.
4. **Physical role separation:** distinct LOGIN principals for confirmation
   stager, grant issuer, revoker, atomic executor and SELECT-only reader.
   The atomic executor has no case/audit/grant table DML, no TEMP/CREATE,
   no membership/owner rights, and no EXECUTE on issuer/stager/revoker or
   the #89 legacy grant function. `SECURITY DEFINER` functions have a
   reviewed NOLOGIN owner with only column/table privileges needed for that
   particular function; no PUBLIC EXECUTE or inherited privileged calls.
5. **Stable, explicit API result:** only a successful database-owned
   atomic mutation receipt represents a committed producer decision.
   A frontend modal is not proof; approval does not enable publishing.

## Branch/migration reconciliation before a combined CI run

- PR #89 currently owns SQL revisions 006 (legacy grant), 007 (OIDC),
  008 (workforce sessions) and 009 (workforce step-up challenge).
  PR #102 separately owns 006 (atomic grant), 007 (issuance) and
  008 (staging). These are **colliding filenames/sequence numbers**;
  neither set is merged directly or applied to shared production data.
- In a new short-lived **draft integration branch**, preserve the already
  reviewed OIDC/session/challenge sequence, explicitly retire the unused
  legacy producer-grant schema path, and renumber P4 atomic-grant/issuer/
  staging migrations forward to non-colliding versions, provisionally
  010–012. Audit every migration runner and test path; prove an empty
  disposable database can apply the forward-only chain twice without
  inheriting stale function ACLs. Never guess/retrofit live migration history.
- Replace #89's `ProducerTransactionalGrantSelector` and
  `ProducerGrantMutationStore` UUID interfaces with an explicit server-held
  action-grant/command-handle adapter calling the #102 atomic writer. A
  protected host-created grant handle must not be returned to the browser.
  Retain fail-closed, default-unmounted HTTP/BFF routes and no-publication
  receipts throughout the integration.

## Required combined qualification (not yet achieved)

- Fresh exact-head Foundation CI, Source security, Dependency audit and
  Foundation integration against the **same combined commit**.
- Restricted real PostgreSQL create -> reverify -> approve and edit -> reverify
  -> reject; cross-tenant/output/session/action, stale generation, revoked,
  expired, consumed, tampered digest, replay, concurrent CAS, issuer grant
  drift, direct DML, crash/restart and audit readback negatives.
- Host-only actor, signed confirmation, fresh enforced CA/MFA and
  policy-revocation negative tests, including direct API/function invocation
  outside the BFF; accessible custom confirmation acceptance by a real
  human operator in independently governed DEV.
- DBA/identity/security review, deployment/cost preflight, explicit manual
  approval and documented rollback before any move toward production.

Until that evidence exists, **keep PRs #89 and #102 DRAFT**, leave
`development`/`main` unchanged, and leave live login, grant issuance,
publication and deployment disabled.
