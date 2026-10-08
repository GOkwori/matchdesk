# First native runtime image scan

Source: `e8c76d093c4312c2ce74e1413cc77a36a5303b1c`.
[Foundation integration run 37764203563](https://github.com/GOkwori/matchdesk/actions/runs/37764203563), attempt 1.
Status: **native-images FAIL; no foundation merge or production approval**.

## Executed scope

The built API/web/PostgreSQL runtime passed its HTTP/restart tests and all 24 browser
cases. Trivy 0.75.0 was downloaded from its official release and its archive hash
verified before execution. It scanned the exact local Docker image IDs in the passing
runtime report. Three scanner processes completed successfully, retaining OS and
language inventories, unfixed findings and every reported severity. Successful
collection did not count as passing image security.

The native gate failed because the newly downloaded database's NextUpdate time had
already passed. Database metadata: UpdatedAt 7 October 2026 07:38:55 UTC; NextUpdate
8 October 2026 07:38:55 UTC; DownloadedAt 8 October 2026 10:35:08 UTC. These are the
upstream artifact's values, not timestamps invented by the application. Under the
initial project policy, this prevents a current clean qualification.

## Findings present in the retained reports

Manual analysis of the retained JSON also established these report-entry counts:

| Image | OS entries | Language entries | Total entries |
|---|---:|---:|---:|
| API | 264 | 6 | 270 |
| Web | 304 | 62 | 366 |
| PostgreSQL | 396 | 46 | 442 |

These are **package/advisory occurrences**, not 1,078 distinct vulnerabilities and not
1,078 demonstrated exploits. The same advisory may appear against multiple packages
and in more than one image. They reflect this particular database snapshot. The
reports include high and critical entries; no severity has been ignored.

The API's language findings were in base-image pip 25.0.1. The web image included
package-manager libraries outside the application's npm lock. PostgreSQL also included
findings in the Go components of its gosu executable. The earlier clean application
lock audits therefore did not establish clean runtime images. Package applicability,
reachability, distribution patches and available fixes still require review.

## Evidence integrity

Image reports artifact 11542969459: SHA-256
`4a9269108c6bc376d12af60c047a5ff5186f4e2ec678fe72c7f661d215a36020`.
Gate artifact 11543184743: SHA-256
`fec32a22f03ae4ac1ac134172a747e3636f3e04cf48e93019710b978d8d40a96`.
The reports archive was downloaded, its hash checked and all manifest-listed JSON
hashes verified. Its source binding matched the commit above. Raw artifacts are
retained for 60 days. This document is a later report, not that tested source.

## Corrections and next qualification

The follow-up makes overdue metadata visible alongside the findings instead of
returning only the first blocking reason. An overdue database remains blocking,
including when no vulnerabilities are reported. Two negative regression cases cover
this. All original inventory/source/image/freshness checks remain.

The two new Python files were also formatted from the hosted Ruff suggestion in
[Foundation CI 37764203647](https://github.com/GOkwori/matchdesk/actions/runs/37764203647).
That run passed 107 tests but correctly failed formatting. The retained patch was
applied to matching source; AST, docstrings and comment text were checked unchanged
before the separate diagnostic change and new tests. No failed check was disabled.

The first narrowly scoped image remediation removes unused pip/npm/Yarn/Corepack
from final API/web stages, with build-time absence checks. Build-stage dependency
installation remains unchanged. The actual images must be rebuilt, regression-tested
and rescanned; no improved finding count or complete fix is asserted here. The base
OS packages and PostgreSQL image have not been patched by this change.

All severities and unfixed findings remain visible and blocking under the current
policy. Any risk-acceptance policy requires a separate explicit owner decision and
finding-specific evidence; no waiver has been applied. Repository controls and an
independent approving review remain separate merge prerequisites.
