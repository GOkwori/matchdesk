# First built-runtime integration attempt

Source: `3b0ae4ae9569ebe97c0bae286720515ea50731ed`.
[Run 37755125431](https://github.com/GOkwori/matchdesk/actions/runs/37755125431),
attempt 1: **FAILED**. Artifact 11539118448 was downloaded and verified against
SHA-256 `680dad446b171d9debb24444cb60e3330e6fb6ecdd499e0bf5e4063c8a337757`.
The artifact's source-commit record matches the source above.

The standalone web and API images built and all three containers became healthy.
Five runtime groups passed: isolation/least privilege, liveness versus readiness,
real HTTP validation/hash stability, invalid/oversized input handling and actual
web-to-API forwarding. The sixth group failed: a deliberately wrong PostgreSQL
password was accepted over loopback TCP. Later runtime groups did not execute.

The database's initialisation defaults allowed trust authentication on loopback;
a configured password was not sufficient to test the intended all-TCP policy.
The correction explicitly requests `--auth-host=scram-sha-256` during initdb and
sets `POSTGRES_HOST_AUTH_METHOD=scram-sha-256`. These settings affect new volumes
only. Existing installations require a separately reviewed pg_hba.conf migration;
no existing user database is reset by this correction. The original wrong-password
assertion remains unchanged and must pass in a fresh isolated rerun.

Browser results: **9 passed, 15 failed, no skipped tests** across 24 Chromium cases.
All 15 failures came from a strict locator matching both the workbench error and
Next.js's separate route-announcer alert. Tests now scope the alert to the named
Validation result panel, retaining the original visibility/content assertions.
Acceptance, keyboard operation and the input-revision race passed at all three
viewport sizes. These are not three different browser engines.

Failed traces, screenshots, container logs and runtime reports are retained rather
than overwritten. No phase or production approval follows from this attempt. The
next source requires its own independent foundation, integration and advisory audits.
