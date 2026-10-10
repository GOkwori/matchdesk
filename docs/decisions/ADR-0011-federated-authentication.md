# ADR-0011 — Unified customer federation; separate workforce authority

Decision date: 10 October 2026. Owner: George Okwori.
Status: **APPROVED ARCHITECTURE, NOT YET DEPLOYED OR LIVE-QUALIFIED.**

## Decision

MatchDesk will offer a unified, branded customer sign-in experience through
**Microsoft Entra External ID (external tenant)**. Privileged producers and
administrators will authenticate through **separate workforce Entra ID**, with
a distinct issuer, audience, tenant-specific validation, MFA/Conditional Access
and independent server-owned MatchDesk role and session entitlements.

This decision is an explicit architecture approval. It does not create tenants,
register providers, spend money, grant product access, authorise publishing,
supersede test gates, or promote protected `main`.

## Locked account-type matrix

| Intended customer method | External ID integration | Current operational status |
|---|---|---|
| Google / Gmail | Google social federation | PLANNED, not configured |
| Apple | Sign in with Apple federation | PLANNED, not configured |
| Facebook | Facebook social federation | PLANNED, not configured |
| Personal Microsoft / Hotmail / Outlook / Live | Microsoft account (live.com) custom OIDC federation | PLANNED, not configured |
| Microsoft 365 / organisational Entra ID | Explicitly allowed Entra organisation via OIDC federation | PLANNED, not configured |
| Local email | External ID email OTP or email/password | PLANNED, not configured |
| Other enterprise | Individually approved OIDC or SAML/WS-Fed | PLANNED, provider review required |

Social and enterprise federation require **browser-delegated sign-in**;
External ID native authentication supports its local-account methods only.
Provider-specific credentials, redirect URIs and terms require explicit review.
Personal Microsoft-account federation is separate from organisational Entra
federation; do not assume a single generic Microsoft button supports both.

## Security and identity ownership

1. The browser/BFF uses OAuth 2.0 authorisation-code flow with PKCE, fresh
   state and nonce as appropriate, exact callback allowlist and no tokens in
   localStorage. Return tokens from Apple/Google/Facebook only to External ID:
   MatchDesk APIs accept **only validated broker-issued access tokens**.
2. Customer and workforce issuers, audiences, tenants, signing-key caches,
   API routes and session namespaces must remain **distinct**. The producer
   token validator must never accept `common`, `organizations`, customer
   `ciamlogin.com`, direct social access tokens, or JWT header-provided
   signing-key URLs. All signing keys are resolved from the exact server-approved
   issuer's JWKS. Unexpected or untrusted keys fail closed.
3. Create short-lived server-side application sessions with Secure, HttpOnly,
   SameSite cookies, session rotation, CSRF protections, revocation, timeouts,
   logout, audit and redaction. Browser-delegated social sign-in does not
   itself establish producer session authority.
4. Internal principal identity must be keyed by **trusted issuer + tenant +
   immutable broker subject/object identifier**, never an email string.
   Even a verified/shared email must **not automatically merge** accounts
   across Apple, Google, Microsoft or workforce identities. Account linking
   requires fresh proof of control of both accounts, explicit user consent,
   auditable changes and recovery/reversal.
5. MatchDesk grants fan/viewer, analyst, producer, administrator and individual
   match-session permissions from its **server-owned store**, not from a
   provider's profile, JWT-supplied roles, browser headers or self-registration.
   A valid customer token must never grant producer or administrator authority.
6. Producers and administrators use the separately governed workforce realm by
   default, with MFA/step-up appropriate to risk, scoped assignment, current
   entitlement lookup and immutable version-bound decisions. Agents have
   neither producer credentials nor publication authority.
7. Match judge sessions retain isolation, idempotent reset and immutable
   replay/session scope. Guests with elevated privileges or cross-tenant
   workforce sign-in require a separate reviewed exception.

## Implementation and acceptance order

P3-05-ID1 — Record this ADR, strengthen the offline workforce-issuer guard,
verify negative-path tests and exact-commit CI.

P3-05-ID2 — Build customer and workforce trust configuration, canonical
principal mapping, secure JWKS rotation/cache and server-owned entitlements
without enabling routes.

P3-05-ID3 — Integrate a BFF browser flow and safe session cookies, PKCE,
state, CSRF, token substitution/replay tests, logout and error redaction.

P3-05-ID4 — Qualify each activated provider (Apple, Google, Facebook, personal
Microsoft, organisational Entra, email) separately in a reviewed sandbox.
Verify consent, account collision, linking/recovery and provider failures.

P3-05-ID5 — Require stronger workforce identity, tenant/session access and
end-to-end authenticated producer mutations before publication can be enabled.
The publishing outbox and final owner gate remain independent.

## Cost and deployment governance

External ID uses a monthly-active-users (MAU) billing model and optional
premium add-ons. Before provisioning new identity services or paid provider
registrations, provide a cost estimate, free/no-cost alternatives, security and
privacy prerequisites, budget/limits, deprovision plan and George's explicit
approval. Do not create Azure tenants, billing relationships, app registrations,
subscriptions or credentials solely because this ADR was approved.

## Current limitations

`producer_identity.py` implements an offline RS256 workforce-token verifier
with host-provided trusted keys and entitlements; it is not configured live
against Entra or a customer broker. No Apple/Google/Facebook/Microsoft personal
social flow, password/OTP login, protected BFF session, production JWKS
rotation, authenticated producer HTTP mutation route or actual publishing
service exists in the running product. The implementation and provider status
must remain transparent in public evidence.

## Product references

- [External ID customer methods](https://learn.microsoft.com/en-us/entra/external-id/customers/concept-authentication-methods-customers)
- [Personal Microsoft account federation](https://learn.microsoft.com/en-us/entra/external-id/customers/how-to-microsoft-accounts-federation-customers)
- [Organisational Entra federation](https://learn.microsoft.com/en-us/entra/external-id/customers/how-to-entra-id-federation-customers)
- [External ID MAU pricing and billing](https://learn.microsoft.com/en-us/entra/external-id/external-identities-pricing)
