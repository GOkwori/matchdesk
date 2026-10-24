# Implementation brief: locked Sunset Studio design

The owner's implementation brief for rebuilding the studio to the approved, locked design in
[`docs/design/locked/`](../locked/README.md), written on 16 October 2026. It is kept as a record of the
requirements the studio was built against; the [frontend hardening note](../../engineering/frontend-hardening.md)
lists where the build deliberately departs from it. Related: the [UI overhaul assessment](ui-overhaul-assessment-20261016.md)
and the [design brief](sunset-studio-design-brief.md).

---

```text
ROLE
Principal product designer-engineer brief. Rebuild the MatchDesk frontend so it matches the
APPROVED, LOCKED design in docs/design/locked/ and is intuitive and interactive for first-time
and returning users. Visual fidelity to the locked screenshots is a hard requirement, not a
suggestion. Keep or strengthen every existing accessibility and regression test.

READ FIRST, IN THIS ORDER
1. docs/design/locked/README.md        - shell, components, copy, brand placement
2. docs/design/locked/screenshots/*.png - the visual targets (open every image)
3. docs/design/locked/reference-html/*  - exact markup, spacing, sizes, copy for each target
4. docs/design/locked/tokens.css        - locked tokens (tokens win over reference-html)
5. docs/design/briefs/ui-overhaul-assessment-20261016.md - root causes R1-R8 you are fixing
6. docs/design/briefs/sunset-studio-design-brief.md- canonical match script and content for other screens
7. apps/web/src/app/sunset-v3/*, e2e/specs/*, backend/src/matchdesk/domain/*

LOCKED DECISIONS (do not change without asking George)
- Look: Sunset Studio dark: canvas #0E1319, panels #151C25, orange gradient primary actions with
  DARK text, Plus Jakarta Sans + IBM Plex Mono, shield crests, glow only on hero and next-step.
- Shell: 240px gradient sidebar with icon+label nav in the README order; icon rail 768-1023px;
  4-tab bottom bar (Match / Verify / Produce / Story) below 768px.
- Logo: the orange panther (docs/design/locked/brand) + "MatchDesk" wordmark. Favicon set from
  the same folder via the Next.js app/icon conventions.
- Guided tour (6 stops) with the light pop-up card shown in 01-overview.png.
- Evidence uses the three-panel layout in 02-evidence.png.
- Composer shows inline claim highlights and live re-verification (03-composer.png).
- Trust: one "Synthetic replay" pill in the top bar; at most ONE contextual caveat per screen;
  no end-of-page disclaimer panels; no internal labels ("Screen 08", "Sunset Studio V3");
  unbuilt features hidden, except the single locked "Approve · Planned" control.

NON-NEGOTIABLES
- WCAG 2.2 AA: 0 axe violations on every route x 390/1024/1440; keyboard-complete journeys;
  focus ring = --md-focus; reduced motion honoured; reflow at 320px; 44px touch targets.
- Facts exactly as README section 4. No real brands, player photos, "Published" states, or white
  text on orange.
- Use tokens.css values. Three are deliberately corrected versus the mock-ups:
  --md-control-line #66778A, --md-danger-solid #CC3B40, success-solid for icons only.

PHASES - stop after each, report with screenshots at 390/1024/1440 next to the matching target

PHASE 1  Foundations
- Move tokens.css into the app; self-host fonts via next/font; add the brand assets
  (app/favicon.ico, app/icon.png, app/apple-icon.png, public/brand/, manifest).
- Real App Router routes (see README table + assessment section 6.3). "/" = Welcome; move the JSON
  workbench to /dev/workbench. Per-route metadata (title, description, OG). Back/Forward,
  refresh and shared links restore screen, tab, selection and replay time.
- Build the shell: sidebar, icon rail, bottom tab bar, top bar (H1, replay pill + popover,
  Ctrl K search, avatar), breadcrumbs.

PHASE 2  Component library (match 05-component-sheet.png)
- Button (primary/secondary/destructive/locked/loading), StatusChip, ClaimHighlight, Banner,
  Dialog (required reason, loading, error-in-dialog), Stepper, ScoreHeader (full + compact strip),
  ReplaySlider, KpiTile, NextStepCard, TourPopover, EvidenceRow, PitchDiagram, PossessionChart,
  StatBars (+ "View as table"), DefensiveState, Skeleton. Each with all states, tests and axe.
- Add a /design-system route that renders the sheet from the real components.

PHASE 3  Locked screens (pixel-close to the targets)
- 01 Overview, 02 Evidence, 03 Composer, 04 Fan story (+ 06 mobile pattern for every screen).
- Then the remaining screens using the same shell and components.

PHASE 4  Real data and interactions
- Deterministic northbridge_riverside scenario + scripts/export-demo-data.py (assessment 6.2);
  TypeScript verifier port with parity tests; replace placeholder calculation figures.
- Replay slider drives score/stats/timeline/verdicts; composer live re-verification (D-031 flips
  to Eligible); evidence trace + "Claim 59% instead" rejection; EN/ES/FR switch on the fan story;
  guided tour + "Continue where you left off" + Ctrl K palette + persisted preferences.

PHASE 5  Quality gates
- Keep all e2e specs green (update selectors for routes). Add journey tests (first-time tour,
  returning resume, composer flip, forged value, deep links, Back/Forward, mobile tabs).
- Visual regression baselines for the 4 locked screens + component sheet at 390/1024/1440 in the
  Playwright Docker image. Write docs/evidence/ui-overhaul/ with before / target / after triptychs.
- Lighthouse >= 95 (Accessibility 100) on indexable routes; JS <= 170KB gz per route;
  caveat-budget test (<= 1 caveat phrase per screen outside the replay pill).

ACCEPTANCE
- Side by side with docs/design/locked/screenshots, a reviewer cannot tell which is the target
  at a glance (layout, colour, type, spacing, iconography, logo).
- A first-time viewer completes the guided demo in under 3 minutes without help; a returning
  user resumes in one click; Back never leaves the app.
- List every deviation from the locked design with the reason. Do not silently "improve" it.
```
