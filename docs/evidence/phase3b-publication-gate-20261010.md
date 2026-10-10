# Phase 3B exact-binding publication gate qualification — 10 October 2026

Status: **TESTED** for the pure-domain authorisation boundary.

Qualified source: `1cf95c850b609e7906e25550f1d4d9a53a6f0384` on `development`.

## Scope

P3-02 introduces `authorize_publication` as a pure, side-effect-free publication
authorisation guard. It accepts only the exact current `ApprovalBinding` that the
producer approved after reverification. The immutable result retains the exact
binding and host-supplied producer/publisher actor provenance.

The regression cases cover:

- acceptance of the exact current approved content/evidence/version/language/persona binding;
- rejection of unverified, pending and rejected review states;
- invalidation when a newer revision opens;
- rejection of version, content, evidence, language or persona drift;
- rejection of a forged approved status without an approval audit;
- rejection of a later audit entry contradicting the current approval;
- rejection of a blank host-established publisher identity.

The domain gate does **not** authenticate an actor, read a trusted server-side
approval store, publish content, issue a delivery event or provide an API/UI
command. Those are separate integration, persistence and producer-desk controls.

## Exact-head hosted qualification

| Workflow | Run | Result |
|---|---:|---|
| Foundation CI | [38015851840](https://github.com/GOkwori/matchdesk/actions/runs/38015851840) | PASS |
| Dependency audit | [38015851831](https://github.com/GOkwori/matchdesk/actions/runs/38015851831) | PASS |
| Source security | [38015851810](https://github.com/GOkwori/matchdesk/actions/runs/38015851810) | PASS |
| Foundation integration | [38015851847](https://github.com/GOkwori/matchdesk/actions/runs/38015851847) | PASS |

Foundation CI ran 290 Python tests on Python 3.12.15 with 96.73% total
branch-aware package coverage, passed strict Ruff lint and formatting, strict
mypy, contract/document checks and the frontend production build. Foundation
integration passed its runtime/browser and native-image security jobs.

The preceding source `b833df0c0439033965459f209bd0039022c78939`
failed Foundation CI [37972382798](https://github.com/GOkwori/matchdesk/actions/runs/37972382798)
solely on Ruff `I001` in the test import grouping. All Python tests, type
checks and the frontend build had passed. The reviewed repair removed one
blank import separator, without changing runtime behaviour or weakening a gate.

P3-02 is **TESTED** for domain authorisation only. P3-03 broadcast output
contracts are next. No main promotion, production publication or Azure
deployment is authorised by this record.
