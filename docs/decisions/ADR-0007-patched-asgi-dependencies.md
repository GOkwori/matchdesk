# ADR-0007: Replace the vulnerable ASGI dependency baseline

Date: 8 October 2026. Status: selected for qualification; merge approval pending.

## Context

The [dependency audit](../evidence/dependency-audit-20261008.md) reported eight
advisory IDs across AnyIO 4.13.0, Starlette 0.50.0 and pytest 9.0.2. The earlier
[compatibility decision](ADR-0005-build-compatibility.md) restored functional checks,
but that result did not establish security. Its historical test evidence is retained.

## Decision

Replace FastAPI 0.128.2 with 0.142.4 and pytest 9.0.2 with 9.0.3. Constrain Starlette
to 1.7.0 and AnyIO to 4.15.1 within their upstream declared dependencies. These are
constraints, not overrides that force an incompatible resolver result. Keep Pydantic,
Uvicorn, frontend dependencies, application code, warnings-as-errors, schema snapshots,
strict type checking, body limits and all existing regression assertions unchanged.

The ordinary Python installation must use the committed lock. Upstream release notes
and package metadata were inspected; the metadata is preserved in the
[candidate manifest](../evidence/patched-python-candidates-20261008.json).
FastAPI 0.142.4 declares Starlette >=0.46.0; Starlette 1.7.0 declares AnyIO >=4,<5.
The selected versions satisfy those declared boundaries. The updated FastAPI brings
an OpenTelemetry API dependency into the lock; this does not configure an exporter,
prove tracing, connect Foundry or authorize cloud calls.

## Resolution evidence

[Resolver run 37757055331](https://github.com/GOkwori/matchdesk/actions/runs/37757055331)
used Python 3.12.15 and uv 0.10.0 against PyPI, without source builds or package
version overrides. Lock resolution, installation and `uv pip check` succeeded.
The source for candidate generation was `ce3b571ca543039bdd9992b3c4be597c4e6a1fcf`.
The output is a real generated lock, not a hand-written approximation.

Artifact 11541225002 was downloaded and checked against SHA-256
`7efdaa5698e0427ef7a1b5217e80fd455ff857b6f487a227d9dcbd5d9ddf3cee`.
Candidate files matched the manifest hashes and the stored Git object identities.
Only the two dependency files and the provenance manifest are imported; the temporary
resolver workflow is removed. Resolution is not application or security qualification.

## Required validation

Foundation CI, Foundation integration and Dependency audit must all run on the same
committed candidate. Preserve the Python tests, all nine runtime groups and all 24
browser cases. Inspect any new warnings, schema drift, request-handling differences
or advisory results. Do not suppress warnings, regenerate snapshots without review,
ignore advisory IDs or lower audit thresholds to make this update pass.

Native image/OS scanning, static application security analysis, secret scanning and
repository protections remain separate foundation gates. A foundation merge records
a qualified engineering baseline; it is not a production deployment or completion
of the simulator, agents or producer workflow. No merge is authorized by this ADR.

## Alternatives and trade-offs

Keeping the old compatibility pin leaves known findings unresolved. Forcing only a
new Starlette beneath the old FastAPI bypasses coherent dependency selection. The
chosen framework update changes a wider upstream surface, so the complete boundary,
browser and container tests are required before acceptance. A clean audit describes
known advisories at scan time, not proof that the software has no vulnerabilities.

## Primary references

- [FastAPI release notes](https://fastapi.tiangolo.com/release-notes/)
- [Starlette release notes](https://starlette.dev/release-notes/)
- [AnyIO version history](https://anyio.readthedocs.io/en/stable/versionhistory.html)
- [pytest changelog](https://docs.pytest.org/en/stable/changelog.html)
