# Phase 0 completion backlog

| ID | Work | Acceptance evidence |
|---|---|---|
| F0-01 | Establish target GitHub repository access | Repo read succeeds; no existing work overwritten |
| F0-02 | Resolve dependency locks and exact frontend type pins | Reviewed uv.lock/package-lock; clean frozen install |
| F0-03 | Run target Python 3.12 and static checks | pytest, Ruff and mypy results on pinned runtime |
| F0-04 | Generate client types and execute Next.js build | Contract drift check, type check and production build |
| F0-05 | Execute Docker topology and browser flow | Logs, browser tests and actual screenshots |
| F0-06 | Add and qualify scans/branch protections | Hosted configuration readback, scan and CI run URLs |
| F0-07 | Review Phase 0 | Recorded owner decision after required checks pass |

Phase 1 starts only after the foundation gate is resolved. Optional integrations may
not displace incomplete mandatory work.
