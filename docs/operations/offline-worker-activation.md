# MatchDesk offline worker activation preflight

This milestone validates the minimum requirements for a locally hosted, operator-approved worker. **It does not install, start or schedule any worker.** No paid resource is created.

## Operator requirements

Use a dedicated unprivileged Linux account and a rootless local Docker daemon. Install a separately reviewed coding image pinned by its actual `sha256` repository digest. Do not place GitHub tokens or model/API keys in the worker process environment. Keep the SQLite database and output evidence outside the repository with local backup and restrictive file permissions.

The preflight checks an exact Git commit, a clean tracked tree, the rootless Docker security option, and the presence of the pinned image digest. No network request, image pull, deployment or coding work is performed. Operator-controlled Docker configuration, host ACLs, image trust, OS patching and emergency stop controls require independent acceptance.

The existing execution loop remains explicitly opt-in. Its `--cycles` argument is bounded and is **not** an always-running daemon. Do not enable a systemd service, cloud-hosted runner, notification delivery, or a model until separately qualified. Worker responses are proposals awaiting independent review—not approval to merge or publish.

## Next activation gates

- Independently qualify the actual image and trusted agent executable, immutable source snapshot, and sandbox protections.
- Provide a dedicated, restart-managed host with durable storage, backups, a single supervisor identity, and an emergency stop.
- Verify worker heartbeat and job timeout recovery without concurrent stale workers.
- Configure authenticated notification sender identity, optional GitHub write access constrained to existing issue comments, and verified end-to-end delivery.
- Enforce usage/spend ceilings before model access; any new paid service requires explicit owner approval.
- Perform a real supervised offline rehearsal and record exact evidence before any hands-off service start.

For current status, inspect `docs/engineering/delivery-workstreams.json` and GitHub issue #60. Pending human accessibility and original-image provenance evidence is not replaceable by automation.
