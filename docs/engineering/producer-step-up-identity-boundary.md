# Producer workforce step-up identity boundary — candidate

**Status: offline implementation only; no live Entra configuration or producer activation.**

## What the code qualifies

The existing API token verifier already checks the issuer- and kid-pinned RS256
signature, exact workforce tenant, resource audience, delegated client/scope,
token freshness and *server-owned* producer/session entitlements.

The new optional `ProducerIdentityPolicy.required_auth_context` accepts exactly
one Entra authentication context ID (`c1`–`c99`) from trusted host policy.
When configured, the verifier requires that **same ID** in the verified delegated
access token's `acrs` array. Missing, malformed and different contexts fail
closed. Neither `amr=["mfa"]` nor a request-supplied identity field substitutes
for the authenticated context. Read-only call sites retain their existing
policy until explicitly configured.

## Required real operational enforcement (NOT DONE)

1. Configure the precise Microsoft Entra workforce-tenant Conditional Access
   context and independently confirm that its policy enforces the intended
   MFA/step-up strength and excludes disallowed users and clients. An `acrs`
   value alone is **not** proof of a tenant's MFA configuration.
2. Have the server-owned BFF request an Entra claims challenge for the intended
   context and acquire a new delegated **API audience** access token. Never
   take any access token from a browser as a durable approval or an authorization
   to write without independent HTTP resource-server validation.
3. Invoke verification with a **required** configured authentication context
   on **every privileged grant issuance**, not only interactive login.
   Look up current actor/tenant/session entitlements independently, check the
   exact action, content/evidence binding, generation and confirmation record.
   Use a dedicated independently authenticated grant-issuer workload identity.
4. Only a constrained issuer with separate role and approval evidence may
   create a bounded, single-use grant bound to the complete authorized case
   and audit hashes. It must **not** share producer writer credentials or expose
   arbitrary INSERTs. Grant revocation and consumption must preserve the same
   database lock ordering.
5. Keep publication separately human-approved, with immutable evidence,
   explicit policy gates and durable outbox/recovery. No automatic publishing.

## Qualification required before activation

Real workforce Entra sign-in and MFA/Conditional Access acceptance; expired,
revoked or wrongly scoped token rejection; client claims challenges; negative
issuer/tenant/session/account-type and replay tests; verified external reviewer
approval; restricted PostgreSQL issuer role and atomic issuer→writer tests;
custom Next.js BFF confirmation; real operator DEV acceptance; cost review and
explicit permission for any paid tenant or identity features. No prompts,
agents, generated claims or frontend confirmations are security boundaries.

**No deployment, production authorisation, external API calls or billable
resources are introduced by this candidate.**

Microsoft references:
- https://learn.microsoft.com/en-us/entra/identity-platform/access-token-claims-reference
- https://learn.microsoft.com/en-us/entra/identity-platform/claims-challenge
- https://learn.microsoft.com/en-us/entra/identity-platform/developer-guide-conditional-access-authentication-context
