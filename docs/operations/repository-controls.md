# Repository controls: owner review and activation

Status: **solo-maintainer policy approved; import files prepared, not activated**.
George approved the policy on 8 October 2026; see
[ADR-0010](../decisions/ADR-0010-solo-maintainer-approval.md).
The latest rulesets read was empty. The existing repository connection can publish
development changes but returned HTTP 403 for branch-protection administration.
No temporary workflow or token is used to bypass that boundary.

## Approved two-branch policy

[main.json](rulesets/main.json) requires a pull request, resolved review conversations
and all eight current checks. Additional approving reviews are set to zero and
last-push approval is disabled. Final owner approval of the exact head remains
required by the operating procedure; it is not an independent GitHub review.
Checks are bound to the observed GitHub Actions integration ID 15368 rather than an
arbitrary status publisher. Force pushes, branch deletion and nonlinear main history
are prohibited. No bypass actor is pre-authorized. An owner-approved foundation
merge would use squash or rebase under these controls; production release remains a
separate decision.

[development.json](rulesets/development.json) retains history safeguards only: no
force push or branch deletion. It allows the approved two-branch development
workflow to obtain checks on each push, with promotion gated at main. It also allows
a normal merge from main back into development after a squash release, without a
force reset. It does not pretend to enforce a pre-push green check on untested code.

The original brief's additional-reviewer requirement is explicitly superseded for
this solo-maintainer workflow. Optional reviews remain possible, and an unresolved
review conversation is not silently dismissed. This approval does not weaken any
security check or waive any finding. It is also not evidence that the import files
have been applied or either branch is protected.

## Activate using the repository owner's session

1. Open the repository's Settings, then Rulesets. Choose New ruleset, then Import a
   ruleset. Select the current main.json, review the target and eight check names,
   and create it. Keep enforcement Active and the bypass list empty. Confirm zero
   required approvals and no last-push approval. Do not use the older one-review file.
2. Import the current development.json and verify that it targets only development
   and prohibits force pushes and deletion without imposing an additional PR branch.
3. Re-read active rulesets and branch rules, and check PR #1's merge controls. Verify
   the native-images failure blocks promotion and all required checks are present.
   Record actual rule IDs and effective settings, including any other applicable rule.

Importing these settings does not merge PR #1. Do not activate auto-merge, delete
branches or change workflow secrets as part of this step. No access token needs to
be shared in chat. If administration is unavailable in the connection, these actions
must stay in the owner's authenticated GitHub session.

## Verification before merge

The final head must have all mandatory checks completed successfully. George then
reviews and explicitly approves the exact head and base SHAs and referenced evidence.
Record the decision and time. This procedural sign-off is not mechanically enforced
by the zero-review ruleset, so automation must not infer merge authority from green
checks. Any head or base change requires renewed sign-off and current qualification.

Confirm the reviewed SHA immediately before merging through the protected PR path.
Preserve development and verify the resulting main commit independently. The current
native image findings remain blocking even after rulesets are active. No security
waiver, final merge approval or Azure deployment is implied by the policy approval.

## Sources

- [Managing and importing GitHub rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/managing-rulesets-for-a-repository)
- [Available rules and approving-review settings](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)
- [Repository rules REST contract](https://docs.github.com/en/rest/repos/rules#create-a-repository-ruleset)
- [Foundation merge checklist](foundation-merge-checklist.md)
