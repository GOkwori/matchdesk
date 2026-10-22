# Producer grant issuance preflight — draft / no grant authority

The code in `producer_grant_preflight.py` verifies a **signed human-confirmation
envelope** and a **signature-verified, step-up delegated workforce access token**
against independently host-owned entitlements, case content and exact expected
generation. Its return object is an inert verification result, **not** a grant,
a one-time nonce reservation, approval to write, or a publication permission.

The host supplies an independently pinned Ed25519 confirmation public key and
a separately validated JSONB digest resolver; neither may come from an HTTP
request, prompt, browser storage or agent output. The confirmation issuer is
a distinct authority from the user access-token issuer. A signed confirmation
must be created only after a genuine accessible custom confirmation dialogue
and independent validation of the operator's current authority. Signed
confirmation generation is **not implemented** here.

The result must **not** be used to insert an action grant directly: a later
reviewed PostgreSQL issuance transaction must revalidate current entitlements,
operator identity, approval context, nonce freshness and expiration, and atomically
reserve the human confirmation ID with insertion of the one-use, case-hash-bound
grant. The issuer must use a physically distinct least-privilege login from the
existing restricted executor; no general-purpose API or browser may inherit it.
Issue expiration, revocation, concurrency, recovery and every negative path
require durable real-PostgreSQL tests before enabling issuance.

Live Entra Conditional Access/MFA acceptance, manual accessible operator tests,
production credentials, tenant provisioning, paid services, BFF integration,
publishing and deployment remain explicitly unapproved. The default application
does not mount or invoke this module. For any real auth context, verify tenant CA
policy actually enforces MFA; the presence of a signed `acrs` alone is not proof.
