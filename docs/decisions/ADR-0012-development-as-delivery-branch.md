# ADR-0012: Development is the delivery branch

Decision date: 22 October 2026. Owner: George Okwori.
Status: **PROPOSED — needs the owner's approval and two repository settings only the owner can change**.

## Context

[ADR-0010](ADR-0010-solo-maintainer-approval.md) gated delivery at `main`: `development` kept only
history safeguards, and work would be promoted to `main` through a protected pull request.

That promotion has not happened since Phase 2. Everything since then, including the hosted competition
build (https://matchdesk-seven.vercel.app, built from `development` @ `ed9ff4d`), lives on `development`.
Meanwhile:

- `main` is still the default branch, so anyone opening the repository sees a Phase 2 README.
- `main`'s required checks fail on `main`'s own older lock file, secret-scan list and image evidence
  (seen on #121), and its ruleset has no bypass actors.
- `main` requires linear history. A squash or rebase promotion would create commits whose secret-scan
  fingerprints have not been reviewed. The scan covers every branch and accepts only exact reviewed
  fingerprints, so CI would turn red everywhere until a follow-up review is merged.
- `development` itself requires neither a pull request nor passing checks.

## Decision (proposed)

1. Make `development` the default branch.
2. Protect `development` like a delivery branch: require a pull request (no approvals needed for a solo
   maintainer) and six checks from GitHub Actions: `foundation`, `web`, `runtime-browser`,
   `native-images`, `dependencies` and `history-secrets`. Keep the no-force-push and no-deletion rules.
   All six run on every pull request into `development` with no path filters, so none can be left
   pending. [development-delivery.json](../operations/rulesets/development-delivery.json) holds this
   configuration for import; the approved [development.json](../operations/rulesets/development.json) is
   unchanged until this ADR is approved.
3. Keep `main` unchanged as the Phase 2 baseline. Promoting `development` to `main` becomes a separate,
   planned task that includes the secret-scan fingerprint review it needs.

The tested submission build is preserved as the branch `release/submission-2026-10` (`ed9ff4d`). Tag
pushes are not available from the automation session.

## Owner actions

1. GitHub → Settings → General → Default branch → `development`.
2. GitHub → Settings → Rules → Rulesets → "MatchDesk development history safeguards": add **Require a
   pull request before merging** (0 approvals) and **Require status checks to pass** with the six checks
   above; or import [development-delivery.json](../operations/rulesets/development-delivery.json).
3. Change this ADR's status to APPROVED, with the date, and replace `development.json` with
   `development-delivery.json` (the repository policy test then follows the new file).
