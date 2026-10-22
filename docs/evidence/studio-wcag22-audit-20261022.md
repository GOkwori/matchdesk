# Studio WCAG 2.2 automated audit — 22 October 2026

Scope: every studio route plus the guided tour, at desktop (1440×900) and phone (390×844), on a local
production build of `development` @ `ed9ff4d` (the submission build). Synthetic data only.

This complements the existing axe sweep (zero violations on every page at three viewports) with checks
axe does not make. It is automated evidence, not a conformance claim; the human part is the
[manual runbook](../testing/studio-accessibility-manual-runbook.md).

## Findings and fixes

| WCAG 2.2 | Finding | Fix |
| --- | --- | --- |
| 2.4.11 Focus not obscured | On phones, controls near the bottom of long screens (composer actions, timeline items, settings links) scrolled under the fixed bottom tab bar when reached by Tab. Seven screens affected. | `scroll-padding-bottom` on the document at phone widths, equal to the tab bar's height, so focus scrolls clear of it. |
| 2.5.8 Target size | Standalone text links (breadcrumbs, "View all 7", "Evidence", "How verification works") were 20 px tall; the "Tool calls" toggles 18 px. | `min-height: 24px` on `.md-link`, breadcrumb links and the tool-call toggles. Links inside sentences keep the inline exception. |
| 2.4.3 Focus order / 4.1.2 | Guided-tour cards were reachable only after about 20 Tab presses, and Escape did not dismiss them. | When a stop opens, focus moves to its heading; Escape closes the tour. |
| 2.4.7 Focus visible | The replay slider reported no focus style. | False positive: the ring is drawn on the slider thumb (checked visually); no change. |

Already passing: one `h1`, one `main` and labelled navigation on every page; no skipped heading levels;
nothing animating with reduced motion requested; the search palette keeps focus inside and returns it
on Escape; composer verdicts are announced through status regions.

## Regression tests added

In `e2e/specs/studio-hardening.spec.mjs`, run at all three viewports:

- heading levels never skip; one `h1`, one `main`, labelled navigation, on every page;
- interactive targets are at least 24×24 px, apart from links inside sentences (measured after
  entrance animations settle);
- keyboard focus is always visible and never hidden under a fixed bar;
- with reduced motion requested, nothing keeps animating;
- a guided-tour stop takes focus, and Escape closes it.

Result: all studio browser tests pass (126 run, 3 deliberate cross-viewport skips).
