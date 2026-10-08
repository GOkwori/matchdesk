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

The current process is not an authenticated operator service. Restrict it to local
development. Browser controls alone can never authorise producer operations. Private
keys, tokens and deployment identifiers must not appear in source, screenshots or reports.
