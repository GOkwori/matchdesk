# Foundation merge checklist

Status: solo-maintainer review policy approved; no final merge approval or merge.

## Scope of this milestone

Merge the qualified engineering foundation separately from the complete MatchDesk
product. The simulator, analytics, Foundry agents, producer workflow and personalised
outputs are later milestones. Their absence does not require keeping the foundation
PR open until the entire product is finished. A foundation merge is not an Azure
deployment, public launch or production-readiness claim.

## Required foundation evidence

- The exact proposed head passes Foundation CI, Foundation integration, Dependency
  audit and Source security. Read results, not only green badges. A later head needs
  its own qualification; failed and partial runs remain in the evidence index.
- Native container/OS scanning covers the actual API, web and PostgreSQL images and
  records scanner/database versions and image identities. Open findings require
  explicit remediation or a justified risk decision, not a blind threshold change.
- Secret findings are reviewed with evidence. The 13 historical source-file digests
  are classified narrowly and recomputed by CI; no blanket path/rule exemptions exist.
- Repository protections are configured and independently confirmed. A draft PR is
  not branch protection. The current connector cannot administer those settings.
- The owner reviews the exact source, remaining limitations and evidence, then gives
  an explicit foundation-merge decision. No generated report grants itself approval.

## Repository settings to verify

On `main`, require a pull request and all eight uniquely named checks: `foundation`,
`web`, `runtime-browser`, `native-images`, `dependencies`, `codeql-python`,
`codeql-javascript-typescript` and `history-secrets`. Require up-to-date checks and
resolved conversations. Disable force pushes and branch deletion, and apply the
policy to administrators rather than relying on a bypass.

George approved the [solo-maintainer policy](../decisions/ADR-0010-solo-maintainer-approval.md)
on 8 October 2026. Set additional approving reviews to zero and last-push approval
to false. This explicitly replaces the brief's independent-review requirement but
not the owner's final exact-commit sign-off. The latter is a procedural control,
not a GitHub approving review, and is not inferred from a passing workflow.

Keep `development` as the working branch and prevent forced updates/deletion. Its
approved history safeguards allow ordinary development commits and post-push tests;
promotion remains a protected PR into main. Do not add a third branch, automatic
merge or deployment as part of this policy change.

These are settings to apply/verify, not a claim that they are enabled. The protected
branch administration read returned 403. Do not provide access tokens or passwords
in chat to work around that permission boundary.

## Merge and follow-up

Keep PR #1 in draft until the remaining gates are met. Record the PR number, full
head SHA, base SHA, qualification runs, limitations and explicit owner decision with
a recorded time. Mark it ready and merge through the protected GitHub PR path only
after that sign-off. A later head or base change invalidates this approval and needs
fresh qualification and renewed owner sign-off. Do not force-update `main`, bypass
failing checks or delete `development`.

After the merge, inspect the resulting commit and run the same relevant checks on
`main`. Record the merge and qualification evidence separately. A release tag or
Azure deployment requires its own explicit decision; neither is implied by this
foundation merge or by approval of the solo-maintainer policy.

## References

- [GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub ruleset controls](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)
- [Current qualification evidence](../evidence/native-image-remediation-20261008.md)
