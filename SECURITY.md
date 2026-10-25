# Security posture and responsible disclosure

**Reviewed source:** `f65e07e94e30a9280a720d31863f22fbc1f5a62f` (25 October 2026). MatchDesk has a public
**synthetic-only Azure competition demonstration**; it is **not** a certified
production broadcaster or a trusted customer/producer identity service.

## Implemented defenses (scope-limited)

- Strict input contracts and bounded request bodies; deny-by-default FastAPI route
  mounting for privileged producer/customer identity operations.
- Same-origin API proxy and a separate, disabled workforce producer BFF route;
  browser UI is not an authorisation boundary.
- Checked registered metrics, typed event/evidence identities, cross-runtime
  parity assertions, restricted PostgreSQL test roles, and version-bound
  approval/revocation behavior in disposable or browser-demo scope.
- Source scanning, dependency audits, CodeQL, secret-history checks, locked
  dependencies, native-image scans and exact-head CI.
- Pinned CI actions, read-oriented delivery-control workflows, and owner-gated
  Azure deployment.
- Runtime model and optional Speech call budgets are process-local; they are not
  an Azure-account spending cap and can reset across replica/process restarts.

## Outstanding security gates

- Real workforce Entra authentication, MFA, step-up, resource-specific action
  authorisation and real publishing destinations are **not activated**.
- Independent penetration test, threat modelling review, realistic recovery and
  disaster-recovery acceptance are **not completed**.
- Manual WCAG 2.2 AA and assistive-technology review are **NOT RUN**; an automated
  colour-contrast failure remains an unresolved reliability signal.
- No licensed external match feed is connected or approved for production.
- Development-to-main promotion, real producer writes, notifications, coding
  executor activation and billable infrastructure changes remain separate
  approval decisions. CI success is not an authorisation to perform them.

See [detailed threat model](docs/solution-design/11-security.md),
[current release gate](docs/operations/release-status.md), and
[assurance issue #63](https://github.com/GOkwori/matchdesk/issues/63).

## Reporting

Report suspected vulnerabilities privately to the repository owner using
an established private GitHub channel, if available. Private vulnerability
reporting configuration is not verified here. Do not post access tokens,
private data or exploit payloads in public issues.
