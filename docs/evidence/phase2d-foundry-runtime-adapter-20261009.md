# Phase 2D Agent Framework / Foundry runtime adapter qualification — 9 October 2026

Status: **ADAPTER QUALIFIED / LIVE QUALIFICATION BLOCKED**.

Qualified adapter source:
`42894407299d4b0a0594f88d364dc8b92586a845`.

This evidence covers the bounded P2-04 runtime adapter only. It does not claim that a
real Microsoft Foundry model call has completed successfully.

## Implemented runtime boundary

The P2-04 adapter now provides:

- an asynchronous specialist execution boundary over the existing P2-03 role scope;
- explicit fail-closed activation through `MATCHDESK_FOUNDRY_ENABLED`;
- required `FOUNDRY_PROJECT_ENDPOINT` and `FOUNDRY_MODEL` configuration;
- one ephemeral in-process Agent Framework agent per specialist turn;
- structured `RuntimeProposal` output that reuses the existing `Claim` contract;
- a maximum output-token ceiling of 1,200 tokens per specialist turn;
- `store=False` on each live runtime invocation;
- role-specific instructions that preserve evidence and authority boundaries;
- host-produced role-scoped read snapshots rather than unrestricted data access;
- audience adaptation restricted to evidence and verification records;
- no approval or publication field in specialist responses;
- lazy optional-runtime imports so disabled/uninstalled live dependencies fail closed.

The adapter remains subordinate to the P2-01 orchestration controller and P2-03
specialist authority boundary. It cannot advance workflow state, mutate deterministic
evidence, approve content or publish output.

## Hosted adapter qualification

All normal repository workflows passed on the exact clean adapter source:

| Workflow | Run | Result |
|---|---:|---|
| Foundation CI | 37880853903 | PASS |
| Dependency audit | 37880853720 | PASS |
| Source security | 37880853746 | PASS |
| Foundation integration | 37880853750 | PASS |

Foundation CI executed 257 tests on Python 3.12.15. Total measured package coverage
was 96.68%. The new `foundry_runtime.py` module measured 81% coverage because the
real Microsoft client construction/network path was intentionally not executed without
qualified live dependencies and credentials. Contracts/comments/docs, Ruff, formatter
checks, strict mypy and source-integrity checks passed.

Foundation integration passed real HTTP/runtime and PostgreSQL restart checks, locked
Chromium regressions, exact runtime-image scans and the independent native-image verdict.

## Retained candidate history

The first P2-04 adapter candidate passed all 257 behavior tests but failed repository
quality gates for two helper docstrings, import ordering/formatting and strict mypy
imports of optional packages that were not present in the reviewed lock. The adapter
was repaired by keeping optional Microsoft imports genuinely lazy through
`importlib`, adding the missing documentation and applying the exact formatting
changes.

A later dependency-declaration attempt added explicit candidate pins for
`agent-framework-foundry==1.14.1` and `azure-identity==1.26.0`. The repository's
locked-dependency gate correctly rejected that source because `uv.lock` had not been
resolver-generated for the new graph. No lock was guessed, no `--locked` control was
weakened and no dependency gate was bypassed. The unqualified declarations were
reverted and the temporary resolver workflow was removed before the clean adapter
qualification above.

## Live-qualification blockers

P2-04 cannot be marked TESTED until both blockers are resolved:

1. **Reviewed live dependency lock**
   - the approved Agent Framework / Foundry dependencies must be added to
     `pyproject.toml`;
   - the repository's pinned `uv` resolver must generate the matching `uv.lock`;
   - the resulting graph must pass the existing dependency/security gates.

2. **Usable Foundry runtime configuration**
   - a real `FOUNDRY_PROJECT_ENDPOINT`;
   - a real `FOUNDRY_MODEL` deployment name;
   - an authenticated credential context accepted by the approved runtime path.

No Foundry project, deployment or other Azure resource was provisioned as part of this
qualification. No live model invocation has been claimed.

## Next controlled action

P2-04 remains open and blocked at live qualification. Once the dependency lock and
runtime configuration are available, execute one bounded live specialist smoke test,
capture model/deployment identity, token usage, latency and structured output, then run
the P2-05 failure/retry/model-evaluation suite before Phase 2 review.
