# Repository controls: owner review and activation

Status: **prepared, not applied**. The repository rulesets read returned an empty
list on 8 October 2026. The existing GitHub connection can publish development
changes but its installation does not have repository-administration permission.
No temporary workflow or token is used to bypass that boundary.

## Proposed two-branch policy

[main.json](rulesets/main.json) requires a pull request, one independent approval,
last-push approval, resolved review conversations and all eight current check names.
Checks are bound to the observed GitHub Actions integration ID 15368 rather than an
arbitrary status publisher. Force pushes, branch deletion and nonlinear main history
are prohibited. No bypass actor is pre-authorized. An owner-approved foundation
merge would use squash or rebase under these controls; production release remains a
separate decision.

[development.json](rulesets/development.json) proposes history safeguards only: no
force push or branch deletion. It allows the already-used two-branch development
workflow to obtain checks on each push, with promotion gated at main. It also allows
a normal merge from main back into development after a squash release, without a
force reset. It does not pretend to enforce a pre-push green check on untested code.

**Review this distinction before activation.** The original brief asked for required
PR checks and a review on both branches while also discussing feature branches.
Requiring a PR into development is not compatible with a strict two-branch workflow
unless the working process changes. These files are a proposal that preserves the
current two-branch execution model; they are not evidence that George approved a
review-policy change or that either branch is protected.

The main policy deliberately retains an independent review. The PR author cannot
supply that approval. Name an authorized reviewer, or explicitly decide on a documented
solo-maintainer alternative before changing this requirement. An assistant's status
report, a comment posted under the owner account, or a green build is not a review.

## Activate using the repository owner's session

1. Open the repository's Settings, then Rulesets. Choose New ruleset, then Import a
   ruleset. Select the downloaded main.json, review the target and eight check names,
   and create it. Keep the enforcement Active and the bypass list empty.
2. Review the development-policy distinction above before importing development.json.
   Do not apply it as a substitute for a stronger policy without an explicit decision.
3. Re-read the active rulesets and branch rules, and check PR #1's merge controls.
   Verify the native-images failure blocks promotion, all required checks are present,
   and an independent approval is required. Record actual rule IDs and configuration.

Importing these settings does not merge PR #1. Do not activate auto-merge, delete
branches or change workflow secrets as part of this step. No access token needs to
be shared in chat. If administration is unavailable in the connection, these actions
must stay in the owner's authenticated GitHub session.

## Verification before merge

The final head must have all mandatory checks completed successfully and a real review
under the chosen policy. Confirm the reviewed SHA immediately before merging. Preserve
development and verify the resulting main commit independently. The current native
image findings remain blocking even after rulesets are active.

## Sources

- [Managing and importing GitHub rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/managing-rulesets-for-a-repository)
- [Repository rules REST contract](https://docs.github.com/en/rest/repos/rules#create-a-repository-ruleset)
- [Foundation merge checklist](foundation-merge-checklist.md)
