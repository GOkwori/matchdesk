# MatchDesk P5 — opt-in localhost judge workbench (candidate)

**Status: feature branch only. Do not claim completed live/browser qualification until exact-head CI gates, browser testing and a human rehearsal pass. Related issue: #64.**

The /judge screen is a disposable local-only synthetic football walkthrough: events, deterministic moment detection, explicitly scripted specialist proposal, verified claim, deliberate false-claim rejection, simulated producer review and nine scripted audience variants. None is live data, a model execution, authenticated producer approval, publication or independently reviewed translation.

## Trust boundary and startup

Run only on a trusted local workstation, not a LAN, reverse proxy, remote development environment, public tunnel or DNS. The normal `matchdesk.api.app:app` does not mount judge routes and the Next.js bridge is disabled by default. Do not alter standard Docker Compose or its existing rewrites to enable this.

From the repository root, install the approved locked dependencies using `uv sync --locked --python 3.12 --group test --group quality`. From `apps/web`, run `npm ci`.

Terminal 1 — from repository root:
```bash
PYTHONPATH=backend/src uv run --no-sync python -m matchdesk.api.judge_local_host
```

The dedicated Python host binds 127.0.0.1:8000, disables proxy address trust and access logs, accepts only exact local peer/Host/Origin/intent, and exposes no product identity or publication routes.

Terminal 2 — from apps/web (not default all-interface npm dev):
```bash
MATCHDESK_LOCAL_JUDGE_ENABLED=1 ./node_modules/.bin/next dev --hostname 127.0.0.1 --port 3000
```

Open http://127.0.0.1:3000/judge on that workstation. Use **Start demo → Replay → Reset → Replay → End session**. Every session has an opaque expiring bearer stored only in volatile React state, with at most eight instances, 15-minute TTL, atomic reset and old-token revocation. Refreshing the page loses that browser capability. Nothing enters cookies, query parameters or browser storage.

The fixed-target Next.js bridge permits only create, read fixture replay, reset and close. It rejects untrusted Host/origin, cross-site intent, forwarded metadata, cookies, unknown paths, token queries and malformed credentials. These protections are *not* workforce authentication or authority to review/publish.

## Required qualification

- Four exact-head mandatory CI checks green: Foundation CI, Foundation integration, Source security, Dependency audit.
- Scoped security review plus local browser smoke of deterministic replay, nine unreviewed variants, failed false claim, disabled producer/publication, second-session isolation, reset/replay/end and custom error banners.
- Negative tests for remote clients, Host/Origin spoofing, forwarded metadata, excessive bodies, expired tokens and default-disabled bridge.
- Responsive layout, keyboard navigation, contrast/focus and independent WCAG 2.2 AA review; sanitize browser screenshots and exclude secrets.
- Record human rehearsal outcome and evidence with exact tested SHA; do not infer demo acceptance from a CI result.

Focused test command from repository root:
```bash
PYTHONPATH=backend/src uv run --no-sync python -m pytest -q backend/tests/test_judge_sessions.py backend/tests/test_judge_local_routes.py backend/tests/test_judge_golden_path.py
```

The original seven Batch 1 PNGs, WCAG assessment, identity, privileged producer steps, publication, promotion to main and competition submission remain separately gated. This change does not authorize paid provisioning or a production deploy.
