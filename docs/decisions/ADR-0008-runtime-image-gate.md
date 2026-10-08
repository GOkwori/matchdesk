# ADR-0008: Bind native scans to the tested runtime images

Date: 8 October 2026. Status: implemented for qualification; results pending.

## Context

The foundation's lockfile audits cover declared application dependencies, not every
package in the container filesystem. A separately rebuilt scan image could also differ
from the image that passed runtime tests. The foundation merge checklist therefore
requires native image evidence before promotion.

## Decision

Scan the actual API, web and PostgreSQL image IDs while the integration containers
still exist. Reuse a single freshly downloaded Trivy database for this collection and
retain its timestamp and byte identity. Keep evidence collection separate from the
`native-images` verdict, and require populated OS/application inventories before
accepting a zero-finding report. Report all severities and unfixed vulnerabilities.
There are no vulnerability exemptions in the initial policy.

The scanner archive is pinned to the official 0.75.0 Linux-64bit release asset and
its verified SHA-256. The job has no repository-write or Azure/model credentials.
Reports remain source/run/image-bound artifacts. They do not claim production approval.

## Alternatives and consequences

Scanning a mutable tag after the tests is simpler but does not establish byte identity.
A second rebuild wastes runner time and can change image IDs. Combining all status
checks into one badge obscures whether a failure concerns functionality or security.
The selected design adds an explicit check without rebuilding or relaxing prior gates.
An unavailable scanner/database or an incomplete report fails qualification rather
than returning a clean result. Existing functional checks can still report their own
outcomes while the image-security gate blocks promotion.

## Validation

The gate has synthetic negative regression tests. Actual results and any remediation
must be recorded separately in `docs/evidence/`; this ADR is not execution evidence.
See the [test method](../testing/runtime-image-security.md).
