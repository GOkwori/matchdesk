# Native image qualification and first remediation

Recorded: 8 October 2026. Tested source:
`c0e8f5c731e8688ceed37145e0f17c07b768df89`.

**Functional scope: PASS. Native image security: FAIL. Foundation merge: BLOCKED.**
This report is committed after the tested source; its own commit is not relabelled
as the source that produced these results.

## Executed workflows

| Workflow or job | Run, attempt 1 | Result |
|---|---|---|
| Foundation CI | [37765164071](https://github.com/GOkwori/matchdesk/actions/runs/37765164071) | PASS |
| Foundation integration: runtime-browser | [37765163994](https://github.com/GOkwori/matchdesk/actions/runs/37765163994) | PASS |
| Foundation integration: native-images | Same run | FAIL |
| Dependency audit | [37765163986](https://github.com/GOkwori/matchdesk/actions/runs/37765163986) | PASS |
| Source security | [37765164003](https://github.com/GOkwori/matchdesk/actions/runs/37765164003) | PASS |

The integration workflow is therefore failed overall. Successful image collection
or successful application tests do not override the native-images verdict.

## Regression and build evidence

Python 3.12.15 ran **109 tests**, with zero failures, errors or skips. These include
the previous 78 foundation tests and 31 image-gate cases. The latter use explicitly
synthetic scanner reports to exercise identity, missing inventory, malformed evidence,
scanner errors, all-severity/unfixed findings and freshness controls. They are not
substitutes for the real image scans below.

Ruff, formatting, strict application type checks, unchanged contract snapshots,
136 documentation points across 22 Python files and 59 document checks passed.
The optimized Next.js build and TypeScript checks passed. Application package coverage
remained 250/250 statements and 70/70 branches; those figures do not cover every CI
script or any unimplemented football/AI feature.

Nine actual runtime groups passed from 10:42:51 to 10:43:04 UTC. They exercised the
existing container isolation, real HTTP boundaries, web-to-API forwarding, database
password/transaction/restart checks and API recovery. Playwright then ran 24 Chromium
cases at desktop, tablet and mobile sizes: 24 passed, zero failures, errors, skips or
flaky cases. Browser execution began at 10:45:45 UTC and took 11.673 seconds. These
are three viewports of one browser engine, not a full cross-browser qualification.

## Implemented reduction of unnecessary runtime components

The API runtime build uninstalled the base image's pip; the web runtime build removed
npm, Yarn and Corepack distributions and launchers. Build-stage dependency installation
was unchanged. Build logs show the absence assertions executing, and the final image
inventories no longer include those managers. The actual application still passed its
runtime/browser regression suite.

The same Trivy version and identical vulnerability-database bytes were used for the
[first scan](native-images-first-run-20261008.md) and this rescan. The database SHA-256
was `5f4b978a55284b1997dc31e9f2fc3f4f1abae80829f51451ade221d5675a69b9`.
The report-entry comparison is therefore not explained by changing advisory data:

| Runtime image | Before removal | After removal | Remaining composition |
|---|---:|---:|---|
| API | 270 | 264 | 264 OS; zero Python-package entries |
| Web | 366 | 304 | 304 OS; zero Node-package entries |
| PostgreSQL | 442 | 442 | 396 OS; 46 Go-component entries in gosu |
| Total | 1,078 | 1,010 | 68 occurrences removed |

These are package/advisory occurrences, **not distinct vulnerabilities or proven
exploits**. Repeated advisories across packages/images remain in the raw reports.
Severity totals in the rescan were 12 critical, 205 high, 430 medium, 353 low and 10
unknown occurrences. Scanner metadata supplied fixed versions for 128 occurrences:
82 in the web image's OS packages and 46 in PostgreSQL's Go components. Applicability,
reachability and distribution-specific fixes still need investigation. None is waived.

## Why the gate remains failed

The newly downloaded database still reported UpdatedAt 7 October 2026 07:38:55 UTC
and NextUpdate 8 October 2026 07:38:55 UTC; DownloadedAt was 10:46:02 UTC. The gate
reported **REFRESH_OVERDUE** at 10:46:25 UTC. A new download is not necessarily newer
advisory content. The initial project policy requires both a bounded database age
and an unexpired next-update timestamp. That policy has not been relaxed.

The follow-up retains both this freshness problem and all image findings in the
verdict. Previously the freshness exception hid the image counts in the verdict,
although raw findings were retained. Two new regression cases prove that an overdue
refresh remains failing both with and without vulnerabilities.

The all-severity policy is deliberately stricter than a risk-based release policy:
even low and unfixed findings block it. No risk acceptance is implicit in a passing
functional run. A change to that policy requires an explicit, documented decision,
not blanket exclusions or changing the scanner's exit code to obtain a green result.

## Image-bound evidence

| Runtime | Observed local image ID |
|---|---|
| API | `sha256:539517f61d3b3bae3076ace54932ebfd95f7eb831296eded2d7466e969ab565e` |
| Web | `sha256:f388ba39efdaf3af604ee5f7337d88035a15f7de80acc9f83492c9524b4f9663` |
| PostgreSQL | `sha256:e8538db784b854a9baac5c1be6d059dcf0db257af2d94c8c5807b5fc15f11222` |

These are actual runtime image identities, not signed public release digests.
Four downloaded archives were checked against GitHub's SHA-256 digests. The runtime,
verdict, manifest and Python result source records all match the tested source above;
the image manifest's per-file report hashes were also verified.

| Artifact | ID | SHA-256 |
|---|---|---|
| Python foundation | 11543702694 | `c638a3babbf4494470f8d55141f4d834691277f523939ec396a9c6891fe7d560` |
| Runtime/browser | 11544147490 | `64e7e1c7e8cfc7b2daa52195af89c1aa608e7000710b5c648c5d27a37e2a1c1c` |
| Image inventories/reports | 11543419305 | `fa6ee7b29a1f836ba05cec9070b2a2e9f172332631207154c27459e6f04122f7` |
| Image verdict | 11544227557 | `a8dc4945612c8dacb6eac039287bc9c69648c82c9f4894466d4e4dc88190b058` |

Artifacts are retained through 7 December 2026. Earlier failed scans and formatting
checks remain in the record. No finding was hidden by deleting scanner metadata.

## Remaining work and authority

Refresh and qualify the dated Node runtime/base image, investigate Debian/gosu
findings against actual shipped components and patched upstream releases, and obtain
fresh advisory data. Rebuild, regression-test and scan the exact candidate images.
Unfixed or non-applicable findings require explicit evidence and disposition rather
than an assumption of safety or an infinite sequence of identical reruns.

[Repository-control imports](../operations/repository-controls.md) are prepared for
owner review, not activated. The main proposal retains an independent review; the
development proposal explains the two-branch policy decision. The rulesets read was
empty and the connection has no administration authority. PR #1 remains draft; main
is unchanged. No release, Azure resource, live-model call or merge occurred.
