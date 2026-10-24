# MatchDesk delivery orchestration — controlled implementation

Status: **coordination foundation, not an activated coding executor**.
Baseline: 15 October 2026; issue [#60](https://github.com/GOkwori/matchdesk/issues/60).
Internal submission target: **26 October 2026**.

## What is automated

The committed machine-readable [workstream register](../engineering/delivery-workstreams.json)
links four engineering lanes and two human-input gates. The stdlib-only
`scripts/delivery_orchestrator.py` independently reads the live protected
`development` commit, workstream issues, four required workflow groups and
the `runtime-browser` / `native-images` checks. It validates the manifest,
rejects graph cycles and unbounded engineering concurrency, and emits
`plan.json` plus a GitHub summary with exact-source check verdicts.

The [GitHub Actions coordinator](../../.github/workflows/delivery-orchestrator.yml)
runs manifest regression tests and can inspect the four lanes in parallel.
This is **read-only scheduling/readiness and CI observation**, not simultaneous
coding or independent WCAG acceptance. `READY_FOR_EXECUTOR` means queued.

### Authoritative queue

| Lane | Issue | Independent near-term goal |
| --- | --- | --- |
| Producer | [#61](https://github.com/GOkwori/matchdesk/issues/61) | DEV-only authenticated commands, auditable exact-version decisions |
| Audience | [#62](https://github.com/GOkwori/matchdesk/issues/62) | Nine persona/language outputs with claim integrity, offline first |
| Assurance | [#63](https://github.com/GOkwori/matchdesk/issues/63) | Security, negative-path and recovery evidence |
| Demo | [#64](https://github.com/GOkwori/matchdesk/issues/64) | Resettable synthetic local judge journey and submission pack |
| Owner inputs | [#65](https://github.com/GOkwori/matchdesk/issues/65) | Seven exact Batch 1 PNGs, identity/cost approval and release signoff |
| Independent accessibility | [#52](https://github.com/GOkwori/matchdesk/issues/52) | Real human/device WCAG evidence; **NOT RUN** |

Baseline Phase 0, Phase 1 and Phase 2 milestones are already completed for
their recorded, limited scopes. The 14 Sunset Studio screens have synthetic
implementations. PR #59 provides opt-in, read-only workforce producer
inspection, **not** an operational approval/publication service.

## Scheduling and owner notifications

A workflow `schedule` event executes **only from the GitHub default branch**
(`main`). This repository deliberately keeps `main` protected and unchanged.
Until exact-SHA owner-approved promotion of this new workflow onto `main`,
the GitHub cron in the workflow is **not running**. The PR can qualify on
`development`, and a later merge to `development` can trigger its push
event, but neither implies an unattended recurring schedule.

Owner-input notifications may be supplied by a separately configured,
condition-based scheduled assistant task. The repository must never claim that task
is active just because this document exists. Notify only on newly required
or materially changed owner actions, linking exact blockers/PRs; suppress
routine green or unchanged hold alerts.

## Coding executor activation — a separate controlled gate

A read-only planner cannot write code. True unattended parallel coding requires
an **authorised, credentialed execution service** such as GitHub Copilot
coding agent or the supported OpenAI Codex GitHub Action. Neither is installed
or granted spending authority by this coordination change.

Before enabling workers, explicitly approve and record:

1. Chosen executor, service eligibility, credential custodian, model and
   forecast/maximum API or Copilot usage; disable paid overages by default.
2. One isolated ephemeral branch/worktree per task (no permanent extra
   branch), pinned `development` base, task-specific path and permission
   scope, independent artifact/evidence and bounded retries.
3. Coding containers with no deployment/publishing/secrets access and no
   repository write token during untrusted model execution. Promote proposed
   patches only through separately authenticated, strictly scoped PR creation.
4. CI and security qualification on each exact PR head; serialize conflicting
   integrations and recheck the combined development SHA.
5. Fail-closed handling for credential gaps, permission changes, token/cost
   ceilings, uncertain evidence and dependency conflicts. Separate live
   identity tests and independent manual accessibility checks remain genuine
   human gates.

Do **not** grant coding agents access to GitHub production environments,
billing, main protection bypass, customer identity stores or privileged
producer/publish endpoints. Agent output is untrusted proposed code, never
permission to access a downstream action. Main promotion always requires an
explicit, exact-head and exact-base owner decision.

## Execution and verification

Local offline preview (never an authoritative result):

```bash
python3 -m unittest discover -s scripts -p 'test_delivery_orchestrator.py' -v
python3 scripts/delivery_orchestrator.py --offline --output-dir artifacts/delivery
```

Authoritative live read with GitHub's **read-only** token permissions
`contents:read`, `issues:read`, `actions:read`, `checks:read`:

```bash
GITHUB_TOKEN=... python3 scripts/delivery_orchestrator.py --github --output-dir artifacts/delivery
```

Never paste or commit a token. A missing token/API error fails closed.
The token environment variable above is an example of local environment
injection, not a request to share a secret in chat.

The planner never opens issues, sends unsolicited messages, signs approvals,
pushes code, merges PRs, publishes content, deploys, provisions Azure resources
or claims that a human/manual test passed.

## Completion rules and rollback

Work is complete only after real implementation, tests, exact-head evidence,
reviewed API/contract/docs changes and any applicable human acceptance.
Closing an issue is *not* sufficient: the planner intentionally emits
`CLOSED_AWAITING_EVIDENCE_REVIEW`. Synthetic security/identity checks cannot
substitute for real provider federation/MFA, real payment authorization,
professional accessibility testing or live publication proof.

The orchestration source is reversible by an ordinary reviewed PR that removes
its manifest, script, tests and workflow. No persistent infrastructure or
secrets are provisioned. The owner may close the queue or disable a scheduled
task independently without affecting the existing application.
