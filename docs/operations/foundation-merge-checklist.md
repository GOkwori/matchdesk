# Foundation merge checklist

Status: proposed merge procedure; not an approval or evidence of a completed merge.

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

On `main`, require a pull request and the uniquely named checks: `foundation`, `web`,
`runtime-browser`, `dependencies`, `codeql-python`, `codeql-javascript-typescript` and
`history-secrets`. Add the native-image check once it exists and has been qualified.
Require up-to-date checks and resolved conversations. Disable force pushes and branch
deletion, and apply the policy to administrators rather than relying on a bypass.

The build brief calls for a required approving review. A PR author cannot approve
their own PR. An independent authorized reviewer is therefore needed for that policy;
do not count an assistant message or a self-authored comment as a GitHub review. Any
alternative solo-maintainer policy must be explicitly decided and documented, not
silently weakened during this merge.

Keep `development` as the working branch and prevent forced updates/deletion. Do not
add a PR-only update policy that makes the agreed two-branch development workflow
impossible without first agreeing a revised branch strategy.

These are settings to apply/verify, not a claim that they are enabled. The protected
branch administration read returned 403. Do not provide access tokens or passwords
in chat to work around that permission boundary.

## Merge and follow-up

Keep PR #1 in draft until the remaining gates are met. Then record the reviewed head,
mark it ready, obtain the required review and merge through the protected GitHub PR
path. Do not force-update `main`, bypass failing checks or delete `development`.

After the merge, inspect the resulting commit and run the same relevant checks on
`main`. Record the merge and qualification evidence separately. A release tag or
Azure deployment requires its own explicit decision; neither is implied by this
foundation merge.

## References

- [GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub required reviews](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/approving-a-pull-request-with-required-reviews)
- [Current qualification evidence](../evidence/security-remediation-20261008.md)
