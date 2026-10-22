# P3/P4 disposable integration checkpoint

This draft candidate is based on PR #89 and additionally stages the independent
P4 grant issuer, staging and atomic execution modules from PR #102.

The original P3 migration files (006 through 009) remain unchanged; the
P4 grant, issuer and staging migrations are staged as 010, 011 and 012.
The old UUID-grant test role is renamed only inside its synthetic CI fixture,
to avoid collisions with the P4 atomic-grant test roles. The CI sequence
qualifies both independent paths, with grant issuer/stager physical-role checks
and P4 writer qualification before the older P3 Psycopg recovery tests.

**IMPORTANT — not an operational producer integration.** The Boolean-grant
and UUID-grant P3 API adapter still exist as default-unmounted DEV-only tests.
The P4 atomic writer is separately exercised, but there is no verified
HTTP-to-issued-grant bridge, no live Entra Conditional Access assertion,
and no authenticated human signature issuer wired to the HTTP router.
They MUST NOT be activated or treated as an alternate write authority.
A further review must remove operational fallback paths and bind real
verified operator intent to execution atomically.

No production migration, cloud deployment or publication authority is approved.
The draft must independently pass all four workflows at its exact head.
