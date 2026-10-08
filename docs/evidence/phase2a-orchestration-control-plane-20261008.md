# Phase 2A bounded orchestration control-plane qualification — 8 October 2026

Status: **TESTED** on development source
`fdb2acab1007a83377208406f9b3b69e2849aac2`.

This evidence covers P2-01 only: the model-independent deterministic control plane
that governs specialist order, typed workflow state, retry budgets, timeout
classification, verification hand-off and restart recovery. It does not certify
Microsoft Agent Framework, Foundry, a live model, durable workflow persistence,
producer publication or Azure deployment.

## Implemented control plane

The Phase 2A workflow locks four specialist roles in this order:

1. `tactical_analyst`;
2. `narrative_composer`;
3. `editorial_reviewer`;
4. `audience_adapter`.

The controller owns authority over role order and execution budgets. A specialist
cannot advance itself, skip another specialist, bypass deterministic verification,
extend its retry budget or reopen a terminal workflow.

`WorkflowState` binds one workflow to match, replay, replay revision and moment
identity. It records current role, completed roles, specialist attempts, recovery
count, workflow status and terminal reason.

Default role policy is two attempts per specialist with a 30-second controller
timeout. Policies are typed and bounded. A runtime result received after its policy
timeout is classified as a timeout even if the runtime reports success.

## Verification and recovery boundaries

A successful editorial-review attempt moves the workflow to
`awaiting_verification`; it does not advance directly to audience adaptation.

Audience adaptation becomes eligible only after an external deterministic
verification gate explicitly passes. A failed verification can rewind to narrative
composition and editorial review only while both role-local attempt budgets remain.
Once that bounded revision budget is exhausted, the workflow enters fallback rather
than looping indefinitely.

Restart recovery is explicit and does not skip the current role or verification gate.
The version-1 control plane permits two recoveries; a third recovery moves the
workflow to fallback.

Blocked outcomes are immediately terminal. Completed, fallback and blocked workflows
cannot be recovered.

## Fail-closed regression coverage

The Phase 2A tests establish:

- the exact four-role sequence;
- audience adaptation cannot run before deterministic verification;
- retryable failures retain the same specialist until budget is exhausted;
- retry exhaustion enters fallback;
- duration above role timeout is controller-classified as timeout;
- a blocked outcome is immediately terminal;
- failed verification rewinds only within the narrative/editorial revision budget;
- a second verification failure after budget exhaustion falls back;
- recovery is bounded and cannot reopen terminal workflows;
- out-of-order role execution fails closed;
- missing or mismatched role policies fail closed;
- malformed persisted states are rejected;
- invalid/boolean/negative duration inputs and blank audit reasons are rejected;
- a pre-exhausted restored retry budget cannot execute another attempt;
- completed-role history remains unique;
- verification cannot bind outside the editorial hand-off.

## Hosted qualification

All required hosted workflows passed on the exact source above:

| Workflow | Run | Result |
|---|---:|---|
| Foundation CI | 37830905932 | PASS |
| Dependency audit | 37830906052 | PASS |
| Source security | 37830905951 | PASS |
| Foundation integration | 37830905979 | PASS |

Foundation CI executed 226 tests on Python 3.12.15. Across the implemented
`matchdesk` package it measured 880 statements and 290 branches with 99.32% total
combined coverage. The new `orchestration.py` module measured 132 statements and
54 branches with **100% statement and branch coverage**. Ruff lint, formatter checks
and strict mypy passed; the frontend build remained green.

Foundation integration passed real HTTP/runtime checks, PostgreSQL restart
persistence, locked Chromium regressions, complete scans of exact runtime-tested
image identities and the independent native-image verdict.

## Retained earlier attempts

The first P2-01 candidate on source
`5bd0215a2eca0b7bf366e3e42b1d40add6ccf221` passed the behavioral tests and strict
mypy but failed Ruff import ordering and one formatter rule. The exact generated
style corrections were applied without changing behavior.

A later edge-coverage candidate
`e49508ddf9fa08f689eaeeb70bf2f465885cf90f` passed 226 tests and reached 100%
coverage for the orchestration module, but the formatter correctly required one
blank-line normalization in the expanded test file. That exact formatter patch
produced the fully green source recorded above.

No quality gate was disabled, suppressed or waived.

## Boundaries

P2-01 is a deterministic control plane only. It does **not**:

- execute Microsoft Agent Framework or Foundry;
- invoke a language model;
- establish model quality or evaluation evidence;
- persist workflow state durably;
- implement the claim verifier itself;
- authorize publication;
- provision Azure resources;
- establish production readiness.

P2-02, deterministic claim verification against Phase 1 evidence and registered
metric formulas, is the next controlled Phase 2 work item.
