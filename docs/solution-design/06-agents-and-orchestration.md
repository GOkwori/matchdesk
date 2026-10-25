# Runtime agents and orchestration

**As-of 25 October 2026:** Implemented four-specialist Agent Framework
workflow, with recorded and separately triggered **live Microsoft Foundry**
executions. The prior "design only; no Foundry endpoint connected" statement
was superseded by historical live run and Azure deployment records.

![Agent verification](../diagrams/agent-verification-implemented.svg)

[Editable diagram source](../diagrams/agent-verification-implemented.mmd)

| Specialist | Purpose | Enforcement boundary |
| --- | --- | --- |
| Tactical Analyst | Read match events and metrics, propose observations | Scoped read-only tools, no evidence mutation |
| Narrative Composer | Construct evidence-linked sentences and claim objects | Draft only; bounded attempts |
| Editorial Reviewer | Inspect supported claims and word choices | Cannot override deterministic verifier |
| Audience Adapter | Prepare personalised EN/ES/FR and fan/analyst/caption variants | Must retain verified source claims; no human sign-off implied |

The workflow controller owns order, timeout, retry budget, provider error
handling, evidence binding and eligibility to advance. The model is not
authoritative. The concrete runner is in
[`backend/src/matchdesk/domain/agent_workflow.py`](../../backend/src/matchdesk/domain/agent_workflow.py)
and the optional live route is in
[`backend/src/matchdesk/api/agent_routes.py`](../../backend/src/matchdesk/api/agent_routes.py).

## Live/demo evidence

The [competition build record](../evidence/competition-build-20261022.md)
documents three live Foundry runs and the actual rejection/revision behavior.
The [verifier benchmark](../evidence/verifier-benchmark-20261024.md)
is synthetic and separate from model evaluation. The live run endpoint is
opt-in, limited to one active run, five-minute spacing, 12 runs/day and
a six-minute runtime timeout **within one process**. These are not
durable, multi-replica cost caps.

Recorded model traces and deterministic scripted rehearsals are clearly
distinguished from new live inference in the studio. Live production
model changes and increased spend require independent operator approval.

## Not the coding-delivery orchestrator

The `scripts/delivery_*.py` workstreams / issue #60 are
**read-only delivery-control rehearsal and scheduling designs**. Passing
[PR #79](https://github.com/GOkwori/matchdesk/pull/79) and
[delivery control](https://github.com/GOkwori/matchdesk/actions/runs/40162579945)
does **not** activate a local always-on coding executor, tool credentials,
release authority or a persistent service.
