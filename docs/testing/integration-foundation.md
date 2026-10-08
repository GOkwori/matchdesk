# Foundation runtime qualification

The integration gate exercises the built Python API and standalone Next.js server
with an isolated PostgreSQL 16 container. It does not qualify the future match engine,
AI agents, editorial publishing, database repositories, migrations or cloud deployment.
The full integration and end-to-end requirements remain in the test strategy.

## Reproducible inputs

The browser harness lives in `e2e` with a separate npm lock so browser tools never
enter the application's runtime dependencies. Playwright 1.63.0 resolves its matching
Chromium binary. Desktop, tablet and mobile are viewport profiles of Chromium, not
three different browser engines. Container base images use immutable registry digests.
Candidate metadata was resolved in GitHub run 37754604886 at source
`51de5484b5d32e056f118b55a03f0b7bba666a39`; artifact 11539741590 has SHA-256
`d5a0343fc70948dbb25e22dfe9a748470224ae2dcee352baac2c214e797901d1`.
Resolution is not a vulnerability audit or a runtime pass.

The web image builds with a non-secret `MATCHDESK_API_ORIGIN=http://api:8000`.
Next.js compiles rewrites at build time: changing this value requires rebuilding.
A runtime-configurable authenticated BFF remains a later production requirement.

## Runtime assertions

The API and web run without root, with read-only root filesystems, dropped Linux
capabilities and no-new-privileges. PostgreSQL has no published host port. API and web
ports bind only to loopback. Health means process availability; `/api/ready` must
continue to return 503 while full product dependencies are unimplemented.

Database tests create a disposable probe table in the isolated CI database, verify
commit/rollback and uniqueness, test password-based TCP, and retain a row across a
container restart. This is PostgreSQL topology/durability evidence, not proof that the
application already stores events. The API is exercised with real HTTP requests before
and after a separate API restart, then the browser workbench is tested against it.

## Failure visibility and safety

Each run uses `matchdesk-it-<run-id>-<attempt>` as its Compose project. The runtime
script refuses ordinary project names. Only that ephemeral project's containers and
volumes are removed during cleanup. No Azure resources, repository-write credential,
model credentials or production database are used. Logs and screenshots contain only
synthetic fixtures. Container environment blocks and generated passwords are excluded
from retained metadata. Retries are disabled in browser tests.

Screenshots are inspection evidence, not approved pixel-regression baselines.
Controlled browser failures are explicitly named test fixtures. No result from those
fixtures is presented as a spontaneous model or service error. Each report must name
the tested commit, image identities, test counts and unresolved gates.

## Running the browser harness

Start the reviewed Compose topology with a generated local password using the normal
project setup. Install with `npm ci --ignore-scripts --prefix e2e`, then from `e2e` run
`npx --no-install playwright install --with-deps chromium` and `npm test`. Browser
tests do not reset a database. The destructive restart/probe test is CI-only and refuses
the ordinary `matchdesk` project. Review its source before using an isolated local copy.
