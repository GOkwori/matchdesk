# MatchDesk P5 — opt-in localhost judge workbench (candidate)

**Status: implementation merged into `development` via PR #80; all five automated workflows, including the localhost judge browser, passed at the original exact head. Human rehearsal and independent accessibility acceptance remain NOT RUN. Any later modification requires fresh exact-head gates. Related issue: #64.**

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

### Windows PowerShell — clean local operator rehearsal

The preceding shell examples use POSIX syntax. For Windows PowerShell, use two
**local** terminals, on the same trusted workstation. Do not use a remote Codespace,
WSL-to-LAN port forward, reverse proxy, public preview or production service.

In a **fresh disposable checkout**, from the repository root, first select the
current PR candidate. The checkout must be clean; record the exact commit you
actually test rather than assuming any SHA in this document stays current:

```powershell
git fetch origin feature/p5-judge-demo-integration-20261020
git switch --detach FETCH_HEAD
git rev-parse HEAD
if (git status --porcelain) { throw "Use a clean checkout for acceptance." }
```

**Terminal 1 (repository root)** — install the approved locked Python and
web dependencies, then start only the dedicated judge host:

```powershell
uv sync --locked --python 3.12 --group test --group quality
npm ci --prefix apps/web --ignore-scripts --no-audit --no-fund
$env:PYTHONPATH = (Join-Path (Get-Location) "backend\src")
uv run --no-sync python -m matchdesk.api.judge_local_host
```

**Terminal 2 (from the same checkout's repository root)** — enable only
the isolated Next.js browser bridge and bind strictly to loopback:

```powershell
Set-Location .\apps\web
$env:MATCHDESK_LOCAL_JUDGE_ENABLED = "1"
.\node_modules\.bin\next.cmd dev --hostname 127.0.0.1 --port 3000
```

Open **http://127.0.0.1:3000/judge** on that workstation only. Use the
[operator acceptance record](judge-operator-acceptance-record.md) and capture
actual observations rather than copying CI results into human-review fields.
Keep bearer values, browser network logs, cookies and environment variables
out of screenshots or review attachments. Stop both local processes when done
and explicitly end any active browser session first.

Open http://127.0.0.1:3000/judge on that workstation. Use **Start demo → Replay → Reset → Replay → End session**. Every session has an opaque expiring bearer stored only in volatile React state, with at most eight instances, 15-minute TTL, atomic reset and old-token revocation. Refreshing the page loses that browser capability. Nothing enters cookies, query parameters or browser storage.

The fixed-target Next.js bridge permits only create, read fixture replay, reset and close. It rejects untrusted Host/origin, cross-site intent, forwarded metadata, cookies, unknown paths, token queries and malformed credentials. These protections are *not* workforce authentication or authority to review/publish.

## Required qualification

- Five exact-head mandatory CI checks green: Foundation CI, Foundation integration, Source security, Dependency audit and Judge loopback browser.
- Scoped security review plus local browser smoke of deterministic replay, nine unreviewed variants, failed false claim, disabled producer/publication, second-session isolation, reset/replay/end and custom error banners.
- Negative tests for remote clients, Host/Origin spoofing, forwarded metadata, excessive bodies, expired tokens and default-disabled bridge.
- Responsive layout, keyboard navigation, contrast/focus and independent WCAG 2.2 AA review; sanitize browser screenshots and exclude secrets.
- Record human rehearsal outcome and evidence with exact tested SHA; do not infer demo acceptance from a CI result.

Focused test command from repository root:
```bash
PYTHONPATH=backend/src uv run --no-sync python -m pytest -q backend/tests/test_judge_sessions.py backend/tests/test_judge_local_routes.py backend/tests/test_judge_golden_path.py
```

The original seven Batch 1 PNGs, WCAG assessment, identity, privileged producer steps, publication, promotion to main and competition submission remain separately gated. This change does not authorize paid provisioning or a production deploy.
