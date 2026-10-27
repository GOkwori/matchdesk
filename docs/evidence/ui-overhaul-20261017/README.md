# Real data + remaining screens (17 Oct 2026)

Rendered from the production build in headless Chromium.

| File | Route | Viewport |
|---|---|---|
| `live-d.png` | `/match/nbr-riv/live` | 1440 |
| `tactical-d.png` | `/match/nbr-riv/tactical` | 1440 |
| `insights-d.png` | `/match/nbr-riv/insights` | 1440 |
| `evidence-0214-d.png` | `/match/nbr-riv/evidence/CL-0214` (figures from the event log) | 1440 |
| `publish-d.png` | `/producer/publish/D-031` | 1440 |
| `activity-d.png` | `/workspace/activity` | 1440 |
| `settings-m.png` | `/workspace/settings` (5-tab bar) | 390 |
| `about-d.png` | `/about` | 1440 |

Local checks on this source (not CI qualification):
- Backend: 1,218 tests passed; coverage 95.37% (gate 90%); ruff, ruff format, mypy clean; `scripts.export_demo_data --check` OK.
- `e2e/specs/studio-locked-design.spec.mjs`: 51/51 passed (17 journeys × desktop, tablet, mobile).
- Existing `sunset-v3*` specs: 253 passed, 98 skipped (by design), 0 failed. One earlier run had a single timing failure that did not reproduce in two reruns.
- axe-core WCAG 2.2 A/AA on 18 studio routes × 1440/820/390: 0 violations; no horizontal overflow; no console errors.
