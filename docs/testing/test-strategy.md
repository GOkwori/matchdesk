# Test strategy and regression gates

## Implemented foundation coverage

The test suite covers strict primitive handling, event-specific fields, frozen records,
canonical identities, half-open windows, stoppage-time clock semantics, evidence
uniqueness, numerical units and the separation of structural validity from truth.
HTTP tests use the actual ASGI application, including malformed JSON, sanitised errors,
nonexistent publishing routes, body-size enforcement, chunked requests and disconnects.
A seeded 500-sample coordinate check is not labelled a Hypothesis property suite.

Schema exports are compared byte-for-byte with the initial snapshots. Tests also verify
that array limits use minItems/maxItems rather than string minLength/maxLength keywords.
Schema normalisation changes must not be hidden by automatically overwriting a baseline.

Repository utilities have tests for documentation/comment failure detection. Comments
and test docstrings explain the intended invariant rather than restate assertions.

## Gates still required

Python 3.12, Ruff, mypy, dependency resolution and audits, generated TypeScript contracts,
Next.js production build, frontend unit tests, Playwright end-to-end/visual/accessibility,
real PostgreSQL integration, Docker builds, hosted CI, live AI evaluations, load tests,
restore/rollback and cloud security must run before their phases can pass.

No unavailable check is replaced by a green badge. The complete Phase 0 gate remains
blocked while its required tooling and remote CI have not executed.

## Regression updates

Use `PYTHONPATH=backend/src python -m scripts.export_contracts` to detect drift.
`--write` is an explicit authoring action, never a test repair. Review every changed
schema, assign a version change where a published contract changes, explain the reason
and retain independent assertions. Visual baselines need equivalent review later.

## Evidence interpretation

Line and branch coverage apply only to the implemented `matchdesk` Python package.
They do not measure completion of the whole product, frontend, infrastructure or future
algorithms. Supplementary interpreter results do not certify the target runtime.
