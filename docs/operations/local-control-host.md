# MatchDesk local control host — inert activation candidate

**Status: NOT INSTALLED, NOT STARTED, NO CODING EXECUTOR.** This milestone adds a Linux-only preflight and an opt-in, bounded *control-only* process. It is not the autonomous coding service, and no always-on host has been qualified.

## Operator requirements

- A dedicated **non-root Linux user**, a clean pinned source checkout, and a private external state directory owned by that same user with mode `0700`.
- Put the SQLite state and single-instance lock in that directory; both are private regular files and must be outside the source checkout.
- Provide the exact reviewed 40-character `development` SHA. Pinning a checkout does not grant permission to update, merge or deploy.
- Remove all model, cloud and GitHub tokens from the environment. The control process does not connect to a coding model, Docker, GitHub or the notification API.

The preflight runs read-only local Git commands. It does **not** create the state directory, install a service, grant authority or start work:

```bash
# Illustrative only: paths, permissions and SHA must first be independently verified.
python3 scripts/delivery_host_control.py \
  --source /srv/matchdesk-checkout --source-sha <EXACT_APPROVED_40_HEX_SHA> \
  --db /var/lib/matchdesk-control/state.sqlite3 \
  --lock /var/lib/matchdesk-control/control.lock
```

With separately approved operator intervention, `--run --cycles 10 --interval 30` performs finite, restart-manager-friendly **control-only** cycles. It recovers expired work reservations and reports durable queue status; it **does not claim new work or execute a coding agent**. A non-blocking OS-level lock prevents duplicate local processes. Recheck the source SHA and storage permissions on every cycle. A failed preflight must stop the service, not fall back to privileged execution.

## Prerequisites before any persistent service

1. Independently validate actual user, host, filesystem permissions, source SHA and external SQLite backup/restore procedure; inspect symlink and file ownership.
2. Qualify service-manager hardening, restart and stop behavior, and recovery of in-flight leases on the real host; this PR does **not** install or enable a service.
3. Independently qualify an approved digest-pinned sandbox coding image, its entrypoint, tool authorizations, limits and offline execution, then require new reviewed activation gates before code generation.
4. Separately prove authenticated alert delivery and remote reconciliation before enabling notifications.
5. Apply explicit owner approval to real provider/model spend, new infrastructure, privileged actions, production and merges. Manual accessibility and exact approved design assets remain independent holds.

The scheduler's GitHub cron is not active on `development` because scheduled workflows execute from the default branch. A successful synthetic or control-only test is not evidence of 24/7 runtime. See [issue #60](https://github.com/GOkwori/matchdesk/issues/60) for the delivery scope.
