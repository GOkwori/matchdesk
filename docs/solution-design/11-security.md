# Threat model and security controls

Status: foundation controls tested locally; product/cloud security not qualified.

| Threat | Implemented foundation response | Required production extension |
|---|---|---|
| Oversized JSON | Actual byte counting before parsing | Platform quotas and load qualification |
| Type confusion | Strict primitives and explicit bool/integer checks | Contract checks at every untrusted boundary |
| Input disclosure | Validation errors omit submitted values | Redaction across logs and traces |
| Event/evidence mutation | Immutable models and canonical digests | Authoritative store revisions and access control |
| Forged verification | No publishing route; structure explicitly not truth | Server-owned verification plus actor-bound approvals |
| Session crossing | No sessions exposed yet | Opaque credentials, scoped queries, CSRF and isolation tests |
| Prompt injection | No model tools connected | Treat source text as data, scoped allowlisted tools, adversarial evals |
| Dependency compromise | No release is certified | Lockfiles, scans, signed provenance and image review |
| Cross-realm privilege escalation | Offline workforce JWT and server-owned role contracts | Reject customer and generic issuers at producer boundary; separate tenant, audience and signing-key trust |
| Social account merging | No account-linking endpoint | Immutable broker subject identity; fresh dual proof and consent before linking; never auto-merge by email |
| Login CSRF / session substitution | No federated login enabled | Browser code+PKCE, state, exact callback, HttpOnly Secure SameSite BFF session, CSRF and logout |
| JWT key substitution | Explicit RS256, issuer-bound key resolver | Trusted issuer JWKS refresh/rotation and negative-path token tests |
| Privileged account abuse | Host-defined role/session grants | MFA/conditional access, permission revocation, step-up and audited approval |
| Unapproved identity spending | No identity resources provisioned | MAU/add-on cost estimate, budget and explicit owner approval |

[ADR-0011](../decisions/ADR-0011-federated-authentication.md) locks
customer federation through External ID and separate workforce Entra sign-in.
Neither set of live providers nor authenticated session endpoints is configured.

The current process is not an authenticated operator service. Restrict it to local
development. Browser controls alone can never authorise producer operations. Private
keys, tokens and deployment identifiers must not appear in source, screenshots or reports.
