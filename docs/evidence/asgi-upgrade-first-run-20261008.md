# Patched ASGI upgrade: retained first qualification failure

Recorded: 8 October 2026. First candidate source:
`f4ba80f56ef0e8dbac51f69464b8feac5f19d861`.

## What ran

[Foundation CI run 37757401157](https://github.com/GOkwori/matchdesk/actions/runs/37757401157)
reached the Python tests but failed while importing the test configuration. The new
Starlette TestClient raised `StarletteDeprecationWarning`: its legacy HTTPX path is
deprecated and the supported client is HTTPX2. No application test count can be
reported for that collection failure. Static checks and schema checks passed.

The Python artifact 11540991511 was downloaded and matched SHA-256
`c9c32a696e91e6fa17ee4ae59d91aed6f67903d7d0b82158c98d78a34fd789e1`.
Its source-commit record matches the candidate above. The log is retained in that run.
[Dependency audit 37757401236](https://github.com/GOkwori/matchdesk/actions/runs/37757401236)
passed its Python, application-npm and browser-harness audit steps on this first
candidate. A successful audit did not excuse the failed test collection.

## Correction

Replace test-only `httpx==0.28.1` with `httpx2==2.13.1` following the
[Starlette TestClient documentation](https://starlette.dev/testclient/) and the
[HTTPX2 release](https://pypi.org/project/httpx2/2.13.1/). The application uses neither
client in its runtime layer at this stage. No import alias, monkey patch or warning
suppression is introduced. All existing test assertions remain unchanged.

[Resolver run 37757588800](https://github.com/GOkwori/matchdesk/actions/runs/37757588800)
resolved and installed the modified graph and imported the client with `-W error`.
It also confirmed that `TestClient` subclasses `httpx2.Client`. The committed regression
in `backend/tests/test_dependency_boundary.py` repeats that compatibility assertion.
Independent CI, integration and audit runs must still qualify the final commit.

The [candidate manifest](test-client-candidate-20261008.json) records real versions
and file hashes. Artifact 11541161275 matched SHA-256
`9078b60f05b41a70481d268942f189b18965183451d7fb02ec10d1a9d21f535c`.
The narrow manifest diff replaces only the HTTP client in the test dependency group;
the actual resolver updates its transitive packages. The temporary resolver is removed.

## Merge boundary

The [patched ASGI decision](../decisions/ADR-0007-patched-asgi-dependencies.md) remains
subject to final qualification. Source scanning, native image scanning, repository
protections and owner review are separate foundation requirements. This note records
neither a main merge nor a production release.
