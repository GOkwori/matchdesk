# Foundation merge checklist

Status: **COMPLETE**. Phase 0 foundation merged, remediated and post-merge qualified on 8 October 2026.

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

These settings are now active and were read back through the repository ruleset API.
The main ruleset has no bypass actors and requires the eight named checks with strict
up-to-date status checks. Development prevents non-fast-forward updates and deletion.

## Merge and follow-up

PR #1 was explicitly approved for exact head
`ed3ec4a84deca06d4530866e051b8deeeae05f0e` against base
`d8e8d7eb0473f24399e3771e0bea36449c4d4502`, then squash-merged through the
protected path. The resulting main commit was
`f62d8ccc2c02f36a707a6e24c6640c449048d941`.

The squash exposed a commit-fingerprint lineage issue in the exact secret-scan
classification. PR #14 repaired only that workflow logic, retained the synthetic key
control and broad-exclusion prohibition, and was explicitly approved for exact head
`e53d1b12b778b18f78b1eff2b0dc862b85ef6f67` against base
`f62d8ccc2c02f36a707a6e24c6640c449048d941`. Its protected squash merge produced
the final Phase 0 main commit `773ba7cc2da60d14e5a1e3106b61fa202c93624b`.

The final main commit then passed all eight required checks. Full closure evidence is
recorded in [Phase 0 closure evidence](../evidence/phase0-closure-20261008.md).

A release tag or Azure deployment still requires its own explicit decision; neither
is implied by this foundation closure.

## References

- [GitHub protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub ruleset controls](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets)
- [Current qualification evidence](../evidence/native-image-remediation-20261008.md)
