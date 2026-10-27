# Foundation operations runbook

## Local API

With the recorded Python dependencies installed, run `make api`. Query `/api/health`
for process liveness; `/api/ready` deliberately returns 503. Stop the process before
changing dependencies. No user data or external model endpoint is required.

## Full-stack prerequisite recovery

Use a machine with Python 3.12, Node 22, Docker and working PyPI/npm access. Run
`make setup`, inspect the resolved lockfiles and pins, then run `make lint` and
`make foundation`. Generate local credentials with `python -m scripts.create_local_env`.
This refuses to overwrite an existing .env and never prints secret values.

Run `make dev`. Test the actual web-to-API validation path and database service separately.
Do not interpret a running PostgreSQL container as an application persistence test.
Restricted PostgreSQL adapters and customer migrations have been exercised on
disposable integration databases; these results do not authorize a live migration,
customer sign-in or recovery operation. See the
[ID3H controlled release hold points](id3h-controlled-release.md).

## Repository publication

Confirm that gokwori/matchdesk exists and is included in the connected GitHub installation.
Inspect it again before applying this snapshot; do not overwrite pre-existing work.
Publish only reviewed source and evidence. Configure main/development protections with
a feasible approval model. GitHub cannot accept owner self-approval as independent review.
Verify hosted checks rather than infer them from the local result.

## Cloud and rollback

`make deploy` intentionally fails in Phase 0. No cloud rollback procedure can be declared
tested without an actual deployment. Before provisioning, discover exact Azure IDs,
permissions, region, model quota and approved cost envelope. Keep secrets outside source.
