# Threat model and security controls

Status (26 October 2026): the public Azure competition demo is deployed and has scoped read-only MCP tools, deterministic claim verification, an internal-only API behind the public studio, managed identity for cloud access, and CI security/dependency checks. It is not a production-qualified authenticated producer/publishing service. See [Azure demo operations](../operations/azure-demo.md), [current progress](../PROGRESS.md) and [requirements traceability](../competition/traceability-matrix.md).

| Threat | Implemented foundation response | Required production extension |
|---|---|---|
| Oversized JSON | Actual byte counting before parsing | Platform quotas and load qualification |
| Type confusion | Strict primitives and explicit bool/integer checks | Contract checks at every untrusted boundary |
| Input disclosure | Validation errors omit submitted values | Redaction across logs and traces |
| Event/evidence mutation | Immutable models and canonical digests | Authoritative store revisions and access control |
| Forged verification | Server-owned claim verification, browser re-checks and structural-only contracts kept separate; demo publication is browser-local | Authenticated actor-bound approval and real publication authorization at execution |
| Session crossing | Public demo does not expose authenticated producer sessions | Opaque credentials, scoped queries, CSRF and isolation tests for production |
| Prompt injection | Bounded model roles and role-scoped read-only tools, with deterministic verification before audience claims | Adversarial evaluations and independently enforced identity/authorization at each privileged tool boundary |
| Dependency compromise | Locked dependencies, hosted source/security checks and image qualification for competition build | Production provenance, scanning and response/patch process |
| Cross-realm privilege escalation | Offline workforce JWT and server-owned role contracts | Reject customer and generic issuers at producer boundary; separate tenant, audience and signing-key trust |
| Social account merging | No account-linking endpoint | Immutable broker subject identity; fresh dual proof and consent before linking; never auto-merge by email |
| Login CSRF / session substitution | No federated login enabled | Browser code+PKCE, state, exact callback, HttpOnly Secure SameSite BFF session, CSRF and logout |
| JWT key substitution | Explicit RS256, issuer-bound key resolver | Trusted issuer JWKS refresh/rotation and negative-path token tests |
| Privileged account abuse | Host-defined role/session grants | MFA/conditional access, permission revocation, step-up and audited approval |
| Unapproved identity spending | No identity resources provisioned | MAU/add-on cost estimate, budget and explicit owner approval |

[ADR-0011](../decisions/ADR-0011-federated-authentication.md) locks
customer federation through External ID and separate workforce Entra sign-in.
Neither set of live providers nor authenticated session endpoints is configured.

The hosted demo is publicly accessible for synthetic, non-publishing scenarios. It is not an authenticated operator service; real producer operations remain blocked pending independently enforced sign-in, authorization and human approval at execution. Browser controls alone can never authorize producer operations. Private
keys, tokens and deployment identifiers must not appear in source, screenshots or reports.
