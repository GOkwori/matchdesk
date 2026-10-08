# Hosted foundation runtime and browser qualification

Recorded: 8 October 2026. Tested source:
`15996afa3219020c44dc1ff8f353e87d93e921e6`.

**Runtime/browser scope: PASS. Overall Phase 0 and production release: BLOCKED.**
The independent [dependency audit](dependency-audit-20261008.md) found unresolved
Python advisories. This report does not waive them or qualify unimplemented features.
Any commit that adds this report is a later documentation commit, not the tested
source identified above.

## Actual executions

| Scope | GitHub run | Observed outcome |
|---|---|---|
| Python and frontend build | [37755579407](https://github.com/GOkwori/matchdesk/actions/runs/37755579407) | PASS |
| Built runtime and browser | [37755579408](https://github.com/GOkwori/matchdesk/actions/runs/37755579408) | PASS |
| Dependency advisory audit | [37755579414](https://github.com/GOkwori/matchdesk/actions/runs/37755579414) | FAIL: Python advisories |

All three refer to the source above. Python 3.12.15 ran 77 tests with zero failures,
errors or skips. The implemented package covered 250/250 statements and 70/70 branch
opportunities. Ruff, formatting, strict mypy (seven source files), contract snapshots,
115 documentation points across 19 Python files, and 47 document checks passed.
The frontend's type check and optimized build also passed. Coverage does not include
future simulation, analytics, model orchestration or publication code.

## Runtime assertions

Nine groups passed against actual containers, from 09:18:22.294 to 09:18:35.656 UTC:

1. Isolated Compose project, non-root API/web processes, read-only API/web root
   filesystems, dropped capabilities, no-new-privileges, loopback-only application
   ports and no PostgreSQL host port. Test and quality packages were absent from the API runtime.
2. Liveness returned 200 while unimplemented product readiness remained 503.
3. Real HTTP structural validation returned the correct flags and a repeatable content digest.
4. Invalid fields returned 422 without reflecting the marker; oversized requests returned 413.
5. The standalone Next.js server forwarded requests to the actual API and preserved its digest.
6. Wrong PostgreSQL TCP passwords failed and the configured password succeeded.
7. PostgreSQL committed one probe row, rolled back another and rejected a duplicate primary key.
8. The committed probe row survived a PostgreSQL container restart.
9. The API recovered after its own container restart; the web-to-API path and readiness state remained correct.

The probe table was removed, then the workflow removed its own isolated containers
and volumes. These are database topology and restart checks, not implemented event
persistence, migration verification, backup restoration or disaster-recovery certification.
The PostgreSQL image entrypoint is not claimed to have the API/web non-root settings.

The web container ran `node server.js`, not `next dev`. Runtime image IDs were:

| Container | Observed local image ID |
|---|---|
| API | `sha256:189392c67cac1131327bcef406b17a39c84fe6707aafed7463a0e76d2cc0bfca` |
| Web | `sha256:0d109047635c0eafa0c909a32cf9b04e37248b94f813ec7f0548a4d9ba01439c` |
| PostgreSQL | `sha256:e8538db784b854a9baac5c1be6d059dcf0db257af2d94c8c5807b5fc15f11222` |

These are observed runtime image identities, not signed registry release digests or security attestations.

## Browser assertions

Playwright 1.63.0 ran **24 cases: 24 passed, zero failures/errors/skips/flaky cases**.
The run began at 09:19:03.713 UTC and reported 10.375 seconds for the browser suite.
This is suite duration, not a product latency or load-test result.

Eight scenarios ran at desktop (1440x1000), tablet (820x1180) and mobile (390x844)
viewports in Chromium. They covered actual acceptance, invalid boolean rejection,
local malformed-JSON rejection, oversized requests, a labelled network-fault fixture
with recovery, a labelled untrusted-response fixture, stale in-flight response
invalidation after editing, and keyboard submission. Retries were disabled.

Initial and accepted-state screenshots are retained. These are visual inspection
artifacts, not approved pixel-diff baselines, and the viewport profiles do not establish
Firefox/WebKit coverage or a full accessibility audit.

## Source-bound artifacts

Downloaded archives were verified against GitHub's SHA-256 values, and their
`source-commit.txt` records were checked against the tested source.

| Artifact | ID | SHA-256 |
|---|---|---|
| Runtime/browser | 11540365212 | `04e54218509e329e4894b57246b193d4502489ff4a9278356565bcb738adfae1` |
| Python foundation | 11539259579 | `6e838fe192d7bbb285d662a5ae2136b3544d1956d4211eb3d2b1482600200cff` |
| Dependency audit | 11539138855 | `add81776d8553227744a95a6b79d1fae475b751802b6d00832dcdc1d2d09bee8` |

Artifacts are retained through 7 December 2026; these summaries remain in Git history.
The [first failed integration run](integration-first-run-20261008.md) remains part of
the record. Its wrong-password assertion was retained; new databases now initialise
TCP authentication explicitly with SCRAM. The browser alert locator was scoped to the
workbench panel rather than Next's separate route announcer. Neither failure was
hidden by skipping tests, retries or relaxed assertions.

No Azure deployment, live model call, main merge, release tag or owner release approval
occurred. Repository protections, Python advisory remediation, image/OS scans, secret
scanning, static application security analysis and remaining phase acceptance are open.
