# UI overhaul evidence — locked Sunset Studio frontend (16 Oct 2026)

Screens rendered from the production build (`next build` + `next start`) in headless Chromium.
Targets live in [`docs/design/locked/screenshots`](../../design/locked/screenshots).

| File | Route | Viewport |
|---|---|---|
| `welcome-d.png` | `/` | 1440 |
| `tour1-d.png` | `/match/nbr-riv?tour=1` (Overview + guided tour) | 1440 |
| `moments-d.png` | `/match/nbr-riv/moments?moment=M-05` | 1440 |
| `evidence-0214-d.png` | `/match/nbr-riv/evidence/CL-0214` | 1440 |
| `composer-d.png` | `/producer/compose/D-031` (initial, blocked) | 1440 |
| `queue-t.png` | `/producer/queue` (icon rail) | 820 |
| `overview-m.png`, `story-m.png` | Overview, fan story (tab bar / public page) | 390 |
| `design-system-d.png` | `/design-system` | 1440 |

Local checks on this source (not CI qualification):
- `e2e/specs/studio-locked-design.spec.mjs`: 36/36 passed (12 journeys × desktop, tablet, mobile).
- Existing `sunset-v3*` specs against the moved legacy routes: 253 passed, 98 skipped (by design), 0 failed.
- axe-core WCAG 2.2 A/AA on 11 studio routes × 1440/820/390: 0 violations; no horizontal overflow; no console errors.
- `npm run typecheck`, `next build`, `scripts/check_comments.py`, `scripts/check_ts_syntax.cjs`: pass. No dependency or lockfile changes.

Full-page captures show the sticky sidebar at viewport height and the fixed phone tab bar at its viewport position.
