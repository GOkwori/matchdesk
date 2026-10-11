# MatchDesk - approved front-end design references

**Approved visual direction:** Sunset Studio (Colour Option F), 11 October 2026.
**Scope:** 14 responsive screen designs (desktop and mobile review).
**Archive state:** PARTIAL - seven Batch 2 interactive HTML prototypes are committed here; the original PNG renders and seven Batch 1 raster screens have not yet been imported.

This is the authoritative *approved visual direction* for future MatchDesk front-end work. Approval of the mock-ups is not approval to enable production login, producer mutations, publishing, or other privileged features. The present API and security boundaries remain authoritative.

## Start here

- [Approval and design provenance](design-approval.md)
- [Fourteen-screen asset register](asset-register.md), including missing raw assets
- [Implementation and truthfulness guardrails](implementation-guardrails.md)
- [Producer UX architecture](../solution-design/09-ux.md) - existing foundation history is retained

## Available review prototypes

- [08 Producer Review Queue](prototypes/08-producer-review-queue.html)
- [09 Story & Commentary Composer](prototypes/09-story-commentary-composer.html)
- [10 Review & Publication Journey (Future State)](prototypes/10-review-publication-future-state.html)
- [11 Audience Experience](prototypes/11-audience-experience.html)
- [12 Activity, Audit & Settings](prototypes/12-activity-audit-settings.html)
- [13 Notification & Dialogue Library](prototypes/13-notification-dialogue-library.html)
- [14 Defensive States](prototypes/14-defensive-states.html)

Each prototype is a self-contained concept with inline CSS, SVG and local demo interactions. Open a trusted local copy to review; do not deploy these HTML files directly to the Next.js application. Interactions, fixture values and badges are illustrative and must not be mistaken for verified backend state.

## Preserved design language

- Dark premium sports-media UI: background `#10151c`, panel `#19222d`, raised surface `#23303c`, primary sunset accent `#ff9159`, warm highlight `#ffc084`, light text `#f5f7fa` (observed in the archived Batch 2 source).
- Responsive navigation and layouts for mobile, tablet, laptop and desktop; semantic state icons and text, clear focus indicators, accessible controls and a light/dark design treatment.
- Custom in-app **success, information, warning and error** banners, plus accessible custom confirmation dialogues. Never use `window.alert`, `window.confirm`, `window.prompt`, the browser Notification API or operating-system notifications.
- Explicit differentiation of synthetic replay, deterministic verified evidence, AI interpretation, pending/failed checks, human approval eligibility and confirmed publication.
- Human control: AI proposes; verified server-side policy and the authorised human decide; approval is not publication.

**Important:** Visual concepts contain known design-data and accessibility discrepancies; [implementation-guardrails.md](implementation-guardrails.md) is required reading before implementation. The screenshot-only sources are NOT silently replaced with generated alternatives.
