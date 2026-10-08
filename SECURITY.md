# Security status and reporting

This is a local foundation, not a production deployment. Do not expose it as a
completed production service or connect confidential data. All example data is
synthetic. The validation endpoint is read-only and cannot publish narratives.

Implemented controls include bounded request bodies, strict event contracts,
immutable records and validation errors that do not echo submitted values.
Authentication, session isolation, private database access, model quotas,
secret scanning, dependency scanning and cloud threat testing remain release gates.

For a security report, contact the repository owner privately through GitHub when
the repository is provisioned. Private vulnerability reporting must be enabled
and verified before a public deployment. Do not publish credentials or exploit
payloads containing private data in public issues.
