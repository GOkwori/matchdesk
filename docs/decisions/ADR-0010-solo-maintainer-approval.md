# ADR-0010: Solo-maintainer review and protected promotion

Decision date: 8 October 2026. Owner: George Okwori.
Status: **APPROVED policy; GitHub activation remains unverified**.

## Context and decision

I have chosen a solo-maintainer workflow for MatchDesk. I will review the evidence
and explicitly approve the exact commit before it is merged to main. I am not
presenting that decision as an independent review of my own work.

George approved this policy in the project discussion on 8 October 2026. That
approval addresses the review-policy decision only. It does not approve PR #1,
a security exception, production readiness, a release tag or Azure deployment.
The original implementation brief's requirement for one approving review is
superseded for this solo-maintainer workflow; its testing and phase gates remain.

## Controls retained

Main still requires a pull request, all eight named checks from GitHub Actions,
up-to-date checks, resolved review conversations and linear history. Force pushes,
branch deletion and administrator bypass actors remain prohibited by the import
configuration. The required check names and their integration ID are unchanged.

The only semantic changes in `docs/operations/rulesets/main.json` are:

| Setting | Previous proposal | Approved value |
|---|---:|---:|
| `required_approving_review_count` | 1 | 0 |
| `require_last_push_approval` | true | false |

Both settings must change: a last-push approval requirement would still introduce
an additional-reviewer barrier. Optional reviews remain possible; stale-review
handling and conversation resolution remain enabled. No scanner, severity threshold,
exception list, required check or source-provenance control changes in this decision.

Development remains the working branch. Its history safeguards prohibit forced
updates and deletion, while ordinary commits trigger tests on that branch. Promotion
uses development to main. No third branch, automatic merge, release or deployment is
authorized by this decision. Keep development after promotion.

## Exact-commit owner sign-off

Before a merge, the owner must review the proposed head, target/base commit,
current qualification runs, unresolved review conversations, remaining limitations
and live branch controls. Record the PR number, full head SHA, base SHA, evidence
references, decision and recorded time. A later head or base change requires fresh
qualification and renewed sign-off; an earlier approval is not reusable.

Owner sign-off is a procedural control, not a native GitHub approving-review check.
A zero review count does not grant autonomous merge authority. Neither a passing
workflow nor a repository comment written on the owner's behalf proves a new owner
decision. Record only approval actually given for the identified commit. Merge
through the protected PR path, then qualify the resulting main commit separately.

## Trade-off and review trigger

This policy does not provide independent peer review. I accept that separation-of-
duties limitation for a solo project while retaining the automated checks and my
final decision. Revisit this policy when another maintainer joins or before a change
in operational scope warrants independent review. This is not acceptance of any
open image vulnerability or overdue advisory database.

## Activation and validation

The repository connection returned HTTP 403 for branch-protection administration,
and the rulesets read was empty when this decision was prepared. Versioning an
active import configuration does not activate it in GitHub. The owner must import
and verify the rules in an authorized session; no credential workaround is used.

Six regression cases in `backend/tests/test_repository_policy.py` check the exact
branch targets, absence of bypass actors, all eight checks, the approved review
settings and retained history safeguards. They validate files, not live GitHub
configuration or owner approval. Hosted qualification is reported separately.

See [repository controls](../operations/repository-controls.md) and the
[foundation merge checklist](../operations/foundation-merge-checklist.md).

## References

- [Available GitHub ruleset controls](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)
- [Importing and managing repository rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/managing-rulesets-for-a-repository)
