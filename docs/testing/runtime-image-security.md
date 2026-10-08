# Runtime image security

The `native-images` check qualifies the images used by the same run's runtime tests,
not a similarly named registry tag. This check is part of `Foundation integration`.
It complements the Python/npm lock audits and CodeQL; it does not replace them.

## Collection and evidence

After the HTTP/PostgreSQL and browser stages, the collector reads
`runtime-checks.json`, checks its source and isolated Compose project, and confirms
each container still uses its recorded image ID. Trivy 0.75.0 scans the local Docker
image by that ID. Registry fallback is disabled. The scanner executable is downloaded
from its official release and checked against the independently inspected archive
SHA-256 before execution. This verifies those bytes, not an author signature.

One freshly downloaded vulnerability database is used for all three scans. Collection
records database schema/update timestamps and the database byte hash, scanner version,
source commit, run/attempt, commands, image IDs, report hashes and process exit codes.
JSON reports include all detected OS/language packages and all reported severities,
including vulnerabilities for which no patch is available. No ignore file, VEX
exception, baseline or whole-directory exclusion is applied by this implementation.
Container environment variables and the disposable database password are not exported.

The raw reports are saved as `image-security-<run>-<attempt>`. A separate job downloads
that run's artifact and enforces the gate. A successful collector is not a security
pass. Artifacts and verdicts are retained for 60 days, including failed attempts.

## Fail-closed gate

`scripts/image_security.py` rejects missing/altered files, mismatched source/run/image
identity, scanner failures, stale databases, an end-of-life or unknown OS, and empty
inventories. It checks that Debian packages and each service's expected application
packages were actually detected. All three images must be present: API, web and
PostgreSQL. Database age is bounded to 48 hours and its next-update timestamp must
not have expired. All reported vulnerability entries block this initial gate,
including low, unknown and unfixed entries. Findings require remediation or a
separately approved, evidence-backed policy decision; the collector does not waive them.

The test fixtures in `backend/tests/test_image_security.py` are deliberately synthetic
scanner documents used to test rejection paths. They are not image scan results.
The suite verifies low/unfixed finding rejection, missing inventory, substituted image
IDs, end-of-life detection, altered artifacts, failed scanner codes and stale metadata.

## Scope and limitations

Coverage is Linux/amd64 and the package types supported by the pinned scanner. Native
binaries may embed components that package detection cannot identify. A clean scan is
not a penetration test, exhaustive binary analysis, signed release attestation, or
proof that no vulnerability exists. The runtime restart tests do not establish backup
restoration or application persistence. No scan result authorizes a merge or deployment.

## References

- [Trivy image options](https://trivy.dev/docs/v0.75/guide/references/configuration/cli/trivy_image/)
- [Trivy vulnerability databases](https://trivy.dev/docs/dev/configuration/db/)
- [Pinned scanner release](https://github.com/aquasecurity/trivy/releases/tag/v0.75.0)
- [Foundation merge checklist](../operations/foundation-merge-checklist.md)
