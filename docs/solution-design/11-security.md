# Threat model and assurance boundaries

**Status:** source security and runtime/native-image CI checks passed on
`f65e07e94e30a9280a720d31863f22fbc1f5a62f`, but the synthetic Azure demo is **not a production
security-certified environment**. The older claim "no cloud/model
resources connected" is no longer current.

## Trust boundary matrix

| Boundary | Implemented control | Still not qualified |
| --- | --- | --- |
| Browser → demo API | Same-origin Next.js proxy; bounded request bodies; synthetic fixtures | Generic public read-only endpoint abuse/load assessment |
| MCP client → demo API | Host-enabled read-only tools; no publisher operations | External-user auth/tenant scoped quotas beyond demo |
| Foundry agent → verifier | Scoped tools, typed claim contracts, bounded revisions | Model output never an authorisation decision |
| Producer requests → domain store | Synthetic/disposable PostgreSQL CAS, audit, deny paths | Trusted workforce Entra/MFA, exact resource grant in live host |
| Demo producer → publication | Browser-only simulated approval/retry | Real destination, real signed approval, real audit publication |
| CI → build/release | Locked dependencies, pinned Actions, CodeQL, gitleaks, native images | Independent penetration test, source provenance/signing policy |
| Public Azure → billing | Process-local model/voice limits, optional budget alert | Persistent global quotas, verified invoices, hard financial ceilings |

## Explicit threat classes

Treat direct MCP/API/tool invocation, caller spoofing, forged JWTs,
tenant swapping, replay, prompt injection, stale source SHA, poisoned
evidence, dependency compromise, unauthorized publication, leaked
secrets and source/security gate bypass as in scope. Model prompts
and guardrails are **not** security or permission boundaries.
Each privileged operation requires independent actor/resource/action
authorisation at execution time and denies by default.

## Known failures, outstanding external evidence

- [Integration run 40129492295](https://github.com/GOkwori/matchdesk/actions/runs/40129492295)
  failed desktop tactical colour-contrast on attempt one, then passed
  runtime-browser and native-images on attempt two at the same SHA.
  This does **not** demonstrate a source-level accessibility fix.
- [Manual WCAG issue #52](https://github.com/GOkwori/matchdesk/issues/52)
  remains open and NOT RUN with independent assistive technology.
- [Security/recovery issue #63](https://github.com/GOkwori/matchdesk/issues/63)
  tracks negative-path, data-recovery and independent assurance holds.
- [Owner controls issue #65](https://github.com/GOkwori/matchdesk/issues/65)
  remains open for exact design originals and human-only decisions.

All passwords, API keys, private content, access tokens and unredacted
traces must remain outside public evidence. See [SECURITY.md](../../SECURITY.md).
