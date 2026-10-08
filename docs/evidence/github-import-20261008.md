# GitHub import and first hosted qualification

Recorded: 8 October 2026. Scope: source import, not production qualification.

## Source identity

| Item | Observed value |
|---|---|
| Repository | `GOkwori/matchdesk` |
| Target branch | `development` |
| Remote bootstrap parent | `d8e8d7eb0473f24399e3771e0bea36449c4d4502` |
| Remote import commit | `964fb8c5caae8cb9fc0955c3bf12bd3768b28040` |
| Import commit timestamp | 2026-10-08T08:19:46Z |
| Original local history snapshot | `0449bcc1b25589b3415b9c0418733efb371c042d` |
| Exact snapshot tree | `d6d21c53a62dd3026664e095d88fb7dc91a0d4b0` |
| Files in imported snapshot | 123 |

The original remote branches still contained only the licence. Previously uploaded
Git objects had not been attached to `development`. Recovery restored two historical
execution-log files to their original bytes, yielding the same complete tree as the
local history snapshot. The new commit preserves the remote bootstrap as its parent;
the branch update was non-forced and checked against its expected head.

This is an additive snapshot import. The original local commits remain available in
the separate history bundle; they were not represented as ancestors of the new remote
commit. Matching trees establish source equivalence, not runtime correctness or a
cryptographically signed release.

The import excluded private implementation prompts and credentials. A bounded pattern
scan found no account-email, private-key, GitHub-token or Azure connection-secret
matches. This scan does not replace a full secret or security audit.

## First hosted execution

- [Foundation CI run 37749144657](https://github.com/GOkwori/matchdesk/actions/runs/37749144657)
- [Foundation job 113217795927](https://github.com/GOkwori/matchdesk/actions/runs/37749144657/job/113217795927)
- Trigger: push; source: `964fb8c5caae8cb9fc0955c3bf12bd3768b28040`.
- Runner label: `ubuntu-24.04`.
- Job started: 2026-10-08T08:20:11Z.
- Job completed: 2026-10-08T08:20:24Z.
- Result: **FAILURE** at **Require reviewed dependency locks**.

Checkout, Python setup and Node setup succeeded. The repository does not yet contain
`uv.lock` or `apps/web/package-lock.json`. Package installation, application tests,
static checks and the web build were skipped after that failure. No numerical test
pass rate, frontend build success or Python 3.12 application qualification can be
inferred from this run. The missing-lock check remains enabled.

The earlier 77 passing tests are retained as historical local Python 3.13.5 evidence
in the [evidence index](INDEX.md), not relabelled as hosted results.

## Review and remaining boundaries

[PR #1](https://github.com/GOkwori/matchdesk/pull/1) was created as a draft at
2026-10-08T08:20:58Z. Its initial diff adds 122 files because the licence already
existed. Follow-up documentation commits may add to that diff without altering the
exact imported snapshot identified above.

`main` is unchanged and both branches reported `protected: false` in the read-back.
No merge, release tag, Azure resource, model call or production approval occurred.

Next qualification work: resolve and review real dependency locks, run the target
runtimes and static checks, build and exercise the frontend and database topology,
configure repository protections and retain the resulting source-bound evidence.
