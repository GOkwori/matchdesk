# Documentation map

Every document in the repository, grouped by purpose. The [README](../README.md) is the place to start;
the [judging guide](competition/judging-guide.md) is the quickest route through the working demo.

## Current implementation and authority

| Document | Purpose |
| --- | --- |
| [Implementation inventory](implementation-inventory.md) | Current implemented, deployed, demonstration-only and unqualified capability boundaries |
| [Release and acceptance status](operations/release-status.md) | Exact source/deployment SHAs, CI outcomes and independent holds |
| [Architecture diagram register](diagrams/README.md) | Rendered diagrams with inspectable editable sources |
| [Ownership, contributions and provenance](engineering/ownership-and-provenance.md) | Founder ownership, development tools and non-retroactive Git attribution |

## Project

| Document |
| --- |
| [Why I am building MatchDesk](project-story.md) |
| [Project specification](project-specification.md) |
| [Current progress](PROGRESS.md) |
| [Design overview and references](design/README.md) |

## Competition

How to judge, present and trace the entry. Start with the judging guide.

| Document |
| --- |
| [Demo script (under 2 minutes)](competition/demo-script.md) |
| [MatchDesk judge golden path — offline synthetic qualification](competition/judge-golden-path-local.md) |
| [Judging guide](competition/judging-guide.md) |
| [Project pitch](competition/pitch.md) |
| [Requirement traceability](competition/traceability-matrix.md) |

## Solution design

The system, chapter by chapter: what it does, how the trust boundaries work, and what each part guarantees.

| Document |
| --- |
| [Product overview](solution-design/01-overview.md) |
| [Architecture and trust boundaries](solution-design/02-architecture.md) |
| [Data contracts and temporal semantics](solution-design/03-data-model.md) |
| [Metric dictionary](solution-design/04-metrics.md) |
| [Deterministic moment detection](solution-design/05-moment-detection.md) |
| [Runtime agents and orchestration](solution-design/06-agents-and-orchestration.md) |
| [Verification and publication design](solution-design/07-verification.md) |
| [API reference](solution-design/08-api.md) |
| [Producer experience and foundation workbench](solution-design/09-ux.md) |
| [Infrastructure and deployment](solution-design/10-infrastructure.md) |
| [Threat model and security controls](solution-design/11-security.md) |
| [Responsible AI and evidence limitations](solution-design/12-responsible-ai.md) |

## Architecture decision records

Why the main technical choices were made. ADR-0005 has two records, kept under their original numbers because earlier evidence refers to them.

| Document |
| --- |
| [Agent Framework orchestration](decisions/ADR-0001-agent-framework.md) |
| [Python and FastAPI](decisions/ADR-0002-python-fastapi.md) |
| [PostgreSQL persistence](decisions/ADR-0003-postgresql.md) |
| [SSE and HTTP commands](decisions/ADR-0004-sse.md) |
| [Preserve owner controls across briefing differences](decisions/ADR-0005-baseline-conflicts.md) |
| [ADR-0005: Resolve dependency incompatibilities without relaxing checks](decisions/ADR-0005-build-compatibility.md) |
| [ADR-0006: Built foundation containers and revision-bound browser results](decisions/ADR-0006-foundation-runtime.md) |
| [ADR-0007: Replace the vulnerable ASGI dependency baseline](decisions/ADR-0007-patched-asgi-dependencies.md) |
| [ADR-0008: Bind native scans to the tested runtime images](decisions/ADR-0008-runtime-image-gate.md) |
| [ADR-0009: Remove unused package managers from final service images](decisions/ADR-0009-runtime-package-managers.md) |
| [ADR-0010: Solo-maintainer review and protected promotion](decisions/ADR-0010-solo-maintainer-approval.md) |
| [ADR-0011 — Unified customer federation; separate workforce authority](decisions/ADR-0011-federated-authentication.md) |
| [ADR-0012: Development is the delivery branch](decisions/ADR-0012-development-as-delivery-branch.md) |

## Design

The studio's approved design, its assets and provenance, and the designs of individual features.

| Document |
| --- |
| [Ask MatchDesk](design/ask-matchdesk.md) |
| [Sunset Studio - screen and asset register](design/asset-register.md) |
| [Sunset Studio - design approval and provenance](design/design-approval.md) |
| [Sunset Studio - engineering and content guardrails](design/implementation-guardrails.md) |
| [MatchDesk over MCP](design/mcp.md) |
| [Sunset Studio v3 — screens 01–02 implementation acceptance (11 October 2026)](design/sunset-v3-implementation-acceptance-20261011.md) |
| [Sunset Studio v3 — Screens 05–07 qualification and visual review](design/sunset-v3-screens05-07-qualification-20261011.md) |

## Design briefs

The owner's briefs and the assessment the studio was built against, kept as a record.

| Document |
| --- |
| [Frontend implementation baseline (brief, 11 October 2026)](design/briefs/frontend-implementation-baseline.md) |
| [Implementation brief: locked Sunset Studio design](design/briefs/locked-design-implementation-brief.md) |
| [Sunset Studio design brief (v3)](design/briefs/sunset-studio-design-brief.md) |
| [MatchDesk — UI Overhaul Assessment & Redesign Plan](design/briefs/ui-overhaul-assessment-20261016.md) |

## Operations

Deploying, running, costing and tearing down the services.

| Document |
| --- |
| [Azure demo: the studio and the API on Container Apps](operations/azure-demo.md) |
| [Azure deployment plan: sign-in and hosted backend](operations/azure-deployment-plan.md) |
| [MatchDesk continuous delivery supervisor — milestone 1](operations/continuous-delivery-supervisor.md) |
| [Cost assessment](operations/cost-estimate.md) |
| [MatchDesk delivery orchestration — controlled implementation](operations/delivery-orchestrator.md) |
| [Foundation merge checklist](operations/foundation-merge-checklist.md) |
| [ID3H controlled migration and customer-authentication release gate](operations/id3h-controlled-release.md) |
| [MatchDesk local control host — inert activation candidate](operations/local-control-host.md) |
| [MatchDesk offline worker activation preflight](operations/offline-worker-activation.md) |
| [Repository controls: owner review and activation](operations/repository-controls.md) |
| [Foundation operations runbook](operations/runbook.md) |
| [Teardown policy](operations/teardown.md) |

## Testing

Test strategy, methods, manual runbooks and review sheets.

| Document |
| --- |
| [Locked dependency advisory audits](testing/dependency-audits.md) |
| [AI evaluation methodology](testing/eval-methodology.md) |
| [Foundation runtime qualification](testing/integration-foundation.md) |
| [MatchDesk — audience, recovery and manual accessibility assurance handoff](testing/issues-62-63-52-assurance-handoff-20261020.md) |
| [Spanish and French review sheet](testing/language-review-es-fr.md) |
| [Runtime image security](testing/runtime-image-security.md) |
| [MatchDesk studio — manual accessibility runbook (WCAG 2.2 AA)](testing/studio-accessibility-manual-runbook.md) |
| [Sunset Studio v3 — manual accessibility acceptance runbook](testing/sunset-v3-accessibility-manual-runbook.md) |
| [Sunset Studio v3 — accessibility Phase 2 qualification protocol](testing/sunset-v3-accessibility-phase2.md) |
| [Sunset Studio v3 — accessibility observation record template](testing/sunset-v3-accessibility-session-template.md) |
| [Test strategy and regression gates](testing/test-strategy.md) |

## Engineering

Standards for code and documentation, the workflow, and implementation notes for the producer and identity work.

| Document |
| --- |
| [Delivery backlog](engineering/BACKLOG.md) |
| [Code comments, docstrings and maintainability](engineering/coding-standard.md) |
| [Compatibility and package preflight](engineering/compatibility.md) |
| [Engineering workflow](engineering/development-workflow.md) |
| [MatchDesk Documentation Standard](engineering/documentation-standard.md) |
| [Frontend hardening (17 October 2026)](engineering/frontend-hardening.md) |
| [MatchDesk frontend — Phase 1 adoption and guardrails](engineering/frontend-phase1-decisions.md) |
| [Producer action-grant atomicity — design gate (P4 / Issue #61)](engineering/producer-atomic-grant-protocol.md) |
| [Producer authorization contract reconciliation — DEV integration candidate](engineering/producer-grant-integration-contract.md) |
| [Producer grant issuance preflight — draft / no grant authority](engineering/producer-grant-issuance-preflight.md) |
| [Producer host-confirmation operational acceptance — DEV-only contract](engineering/producer-host-confirmation-operational-acceptance.md) |
| [P3/P4 disposable integration checkpoint](engineering/producer-p3p4-convergence-readiness.md) |
| [Producer workforce step-up identity boundary — candidate](engineering/producer-step-up-identity-boundary.md) |

## Evidence

Dated records of what was run, measured and checked, with links to CI runs. The [evidence index](evidence/INDEX.md) lists them newest first; the most relevant to the competition:

| Document |
| --- |
| [Release candidate and live checks, 23 October](evidence/release-live-checks-20261023.md) |
| [Verifier benchmark and speed, 24 October](evidence/verifier-benchmark-20261024.md) |
| [Spanish and French language review, 23 October](evidence/language-review-es-fr-20261023.md) |
| [Azure deployment record, 23 October](evidence/azure-deployment-20261023.md) |
| [Azure live checks, 23 October](evidence/azure-live-checks-20261023.md) |
| [Competition build record, 22 October](evidence/competition-build-20261022.md) |
| [Studio WCAG 2.2 audit, 22 October](evidence/studio-wcag22-audit-20261022.md) |

## Elsewhere in the repository

| Location | What it holds |
| --- | --- |
| [`labs/auto_eventing`](../labs/auto_eventing/README.md) | The auto-eventing lab: render, detect and score |
| [`infra`](../infra/README.md) | Bicep templates for the Azure demo and the target platform |
| [`SECURITY.md`](../SECURITY.md) | How to report a vulnerability |
| [`LICENSE`](../LICENSE) | MIT licence |
