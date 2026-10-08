# Secret scan: classification of historical file digests

Recorded: 8 October 2026. Initial scanned source:
`91f72d5bb75fc5146921d1f759dba3435907a8de`.

[Source security run 37758452671](https://github.com/GOkwori/matchdesk/actions/runs/37758452671)
ran Gitleaks 8.30.1 against reachable history. It reported 13 generic-api-key findings
in 17 scanned commits. The raw scan failed; this failure is retained, not called a
clean first run. The redacted artifact 11541326973 matched SHA-256
`4e858a4fe0737b5a00b3e8727573216d0f855999846d3163c33f74e751f410ae`.

## Classification and independent checks

Each reported value is a published SHA-256 digest of a source or schema file, not an
API credential. The rule matched names containing `api` next to the digest value.
All 13 were checked individually: the source manifests against the imported source
snapshot; the contract manifest against the OpenAPI JSON; and the two formatter hashes
against the reproduced formatter output and its already-recorded Git blob identities.
The original scan report remains available with every fingerprint.

The [review record](secret-scan-reviewed-digests-20261008.json) lists the immutable
commit/path/rule/line fingerprint, the hashed file and the recomputed digest. CI must
recompute those digests from Git objects and re-read the exact flagged historical line
before generating an ignore file in the runner's temporary directory. It fails if the
line, digest, source object, count or allowed historical commit does not match.

There is no blanket exclusion for documentation, contracts, file extensions, hashes or
API-key rules. The exceptions are only these 13 immutable historical fingerprints;
a new finding at the same path on another commit is not exempted. An ephemeral
synthetic-key control must still be detected with the same generated ignore file.
The control is generated outside the checkout, is not a working credential and is
redacted in the report. No live credential or user secret is used for that test.

## Reporting boundary

A subsequent successful scan means zero unresolved findings **after these 13 verified
non-secret classifications**. It must not be described as a first scan with no findings.
This review does not waive any dependency vulnerability or prove that every possible
secret can be detected. Native container/OS scanning, repository protections and
explicit foundation approval remain separate requirements.
