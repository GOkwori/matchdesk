# Current progress

Date: 8 October 2026. Stage: Phase 0. Gate: BLOCKED, not certified.

## Implemented locally

Immutable version-1 domain contracts; strict event validation; event content hashing;
read-only health/schema/validation API; body-size protection; automated boundary and
regression tests; schema snapshots; comment and documentation checks.

The Next.js workbench, Docker topology and foundation CI are authored but not yet
fully executed. They must not be described as a working full-stack deployment.

## GitHub import and hosted qualification

Personal repository access is confirmed. The 123-file foundation was imported into
`GOkwori/matchdesk` on `development` at commit
`964fb8c5caae8cb9fc0955c3bf12bd3768b28040` on 8 October 2026, 08:19:46 UTC.
Its Git tree matches the original local snapshot exactly. `main` remains at the
licence-only bootstrap; [PR #1](https://github.com/GOkwori/matchdesk/pull/1) is a draft.

The first [hosted run](https://github.com/GOkwori/matchdesk/actions/runs/37749144657)
failed at **Require reviewed dependency locks**. `uv.lock` and
`apps/web/package-lock.json` are missing. Checkout and Python/Node setup passed;
dependency installation, application tests, static analysis and the frontend build
were skipped. The gate must remain in place while genuine lockfiles are resolved.
This run is not a product test pass and did not execute application assertions.

The [import and CI record](evidence/github-import-20261008.md) preserves the source
identity and first hosted outcome. Both branches currently report `protected: false`;
repository protection is outstanding, not implicitly provided by a draft PR.

The original local Python 3.13.5 results remain supplementary evidence. Target-runtime
Python 3.12 qualification, resolved dependencies, Docker/PostgreSQL integration and the
full frontend checks remain outstanding. Earlier package-registry and runtime
limitations are historical observations, not proof that every future runner lacks access.

## Tests and corrections

The first test run found three boundary defects: strict tuple fields rejected normal
HTTP JSON arrays; bool True was accepted as period 1; integer 1 was accepted as the
synthetic flag. The implementation was corrected and the tests retained. Schema
checking also detected array limits emitted as string-length keywords during the fix;
the annotation order was corrected without regenerating the reviewed snapshots.
A later schema-description-only clarification explains that a VerificationResult
contract is not itself the numerical checker. That description update was inspected
explicitly before refreshing its pre-release snapshot; no constraints were removed.

The [evidence index](evidence/INDEX.md) links the actual results. Later tests may increase
the count; consult the source-bound report rather than infer a result from this prose.

## Remaining Phase 0 work

Resolve and pin dependencies on the target runtimes, execute Ruff/mypy, build and test
the actual Next.js application, run Compose, configure protections
and obtain passing hosted CI results. No phase completion, owner approval or production release
is recorded. Azure discovery and all provisioning remain unexecuted.
