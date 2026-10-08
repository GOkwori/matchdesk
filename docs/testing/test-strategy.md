# Test strategy and regression gates

## Implemented regression coverage

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

Hosted Python 3.12, Ruff, mypy, dependency audits, Next.js production build, real
PostgreSQL/runtime checks, Chromium regressions, source security and native-image security
now run as recurring protected gates. Phase 2A additionally tests the orchestration
control plane through retry, timeout, recovery and verification-hand-off edge paths.

Frontend unit coverage, reviewed visual/accessibility baselines, live AI evaluations,
load tests, durable application persistence, restore/rollback and cloud security remain
later-phase work. No unavailable check is replaced by a green badge.

## Regression updates

Use `PYTHONPATH=backend/src python -m scripts.export_contracts` to detect drift.
`--write` is an explicit authoring action, never a test repair. Review every changed
schema, assign a version change where a published contract changes, explain the reason
and retain independent assertions. Visual baselines need equivalent review later.

## Evidence interpretation

Line and branch coverage apply only to the implemented `matchdesk` Python package.
They do not measure completion of the whole product, frontend, infrastructure or future
algorithms. Supplementary interpreter results do not certify the target runtime.
