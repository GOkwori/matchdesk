# Dependency resolution and hosted qualification

Recorded: 8 October 2026. Status: lock candidates generated; application qualification pending.

## Resolver evidence

[Resolver run 37750187622](https://github.com/GOkwori/matchdesk/actions/runs/37750187622)
ran against source `1bdc9fdf06f12840e1e43969d523babaf847cdf6`.
It used Python 3.12.15, Node 22.16.0, npm 10.9.2 and uv 0.10.0.
The job resolved 36 Python package entries (including the virtual project) and 60
npm package entries from the existing manifests. No dependency constraints were changed.
Consult the [machine-readable manifest](dependency-resolution-20261008.json) for exact
versions, source identities, content hashes and limitations.

Python resolution used `uv lock --python 3.12 --no-build`; npm used
`npm install --package-lock-only --ignore-scripts --no-audit --no-fund`.
The resolver checked the public registry hosts and distribution integrity fields,
confirmed the manifests were unchanged and verified returned Git blob identities.
The workflow wrote candidate objects only; it did not advance a branch or approve a release.

The candidates are imported byte-for-byte for full CI qualification. These provenance
checks do not establish vulnerability freedom or runtime compatibility. Full dependency
security scanning, frontend execution and Python static/application checks remain gates.

## Build controls

Foundation CI retains the missing-lock check and uses `uv sync --locked` rather than
`--frozen` alone, so a stale manifest/lock pair is rejected. Frontend installation uses
`npm ci`. Python 3.12.15 and Node 22.16.0 identify the qualification runtimes; GitHub
Actions are referenced by inspected full commit IDs.

Python tests, lint, formatting and strict type checks report independently; frontend
qualification runs in a separate read-only job. A failed check remains a failed check.
Run-specific artifacts retain source IDs, dependency hashes, JUnit, coverage and logs.
When formatting fails, a formatter-generated patch is saved as a suggestion for review,
not silently committed or counted as a successful check of the original source.

The one-time dependency bootstrap workflow is removed after resolution. The remaining
CI workflow has read-only repository permission and no cloud credentials. PR #1 stays
in draft and `main` is unchanged. Phase 0 is not certified by adding lockfiles.
