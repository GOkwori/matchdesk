# MatchDesk continuous delivery supervisor — milestone 1

**Scope:** durable state engine and bounded worker reservation, not unattended coding.

The project needs a continuous delivery *service*, not merely a CI observer. This
milestone introduces `scripts/delivery_supervisor.py`, an on-disk SQLite queue
and nine restart/failure regression tests. Its command line supports status,
reservation and expired-lease recovery without a remote executor, credentials,
network access or billable services.

## Durable state and safety boundaries

- The validated issue/phase manifest supplies a maximum of four concurrent
  engineering reservations. Human-only gates are never reserved as coding jobs.
- SQLite transactions serialize concurrent reservations and survive a process
  crash. Expired worker leases can be recovered; attempts are capped at three.
- Manifest issue or type drift is blocked against persisted task identity.
- Dependency edges require a **VERIFIED** parent state. A closed issue alone
  is not evidence; no CLI operation in this milestone can assert VERIFIED.
- Worker returns can only queue, block or request review. They cannot
  certify themselves. Owner-input alerts are deduplicated in a local outbox.
- The default application, main branch, production, cloud billing, model APIs,
  secrets, authorisation policy and privileged publication are unchanged.

## Activation and missing capabilities

The supervisor is deliberately not running continuously in GitHub Actions.
GitHub-hosted jobs end, its cron belongs to the default (protected main)
branch, and all state on a hosted runner is disposable.

**Production-grade autonomous delivery still requires** a persistent
host, dedicated least-privilege execution credentials, verified coding-agent
installation and usage ceiling, durable remote backup, state/lease ownership,
authenticated alert transport, real signed acceptance receipts, execution
policy and independent merge/release approval gates.

A safe long-lived worker must **not** use this queue as a permission to merge,
invoke arbitrary tools, create cloud resources or publish. The next milestone
must add a provider-neutral executor with path-scoped PR-only patch proposals,
hardened sandbox and explicit spend controls, then qualify crash/recovery and
notification delivery. Do not equate an internal reservation with running code.

## Dry run

```bash
python3 -m unittest discover -s scripts -p 'test_delivery_supervisor.py' -v
python3 scripts/delivery_supervisor.py --db artifacts/delivery/state.sqlite3
python3 scripts/delivery_supervisor.py --db artifacts/delivery/state.sqlite3 --worker demo-worker
python3 scripts/delivery_supervisor.py --db artifacts/delivery/state.sqlite3 --recover
```

The `--worker` option is **only an internal reservation** and does not
spawn a process. Keep the SQLite file outside version control and back it up
before any deployment. GitHub Actions tests use isolated disposable fixtures.

## Required completion condition

No task reaches VERIFIED without independently checked exact-head CI, evidence,
scope-bound acceptance and any applicable human sign-off. Final success means
every required build, integration, accessibility and asset gate is satisfied,
not merely that synthetic tests passed. The 26 October submission deadline
does not relax those criteria.
