# MatchDesk frontend — Phase 1 adoption and guardrails

**Baseline approved:** 11 October 2026. The owner-approved implementation prompt is archived in [frontend-implementation-baseline.md](frontend-implementation-baseline.md). The referenced design enhancement prompt is [docs/design-brief.md](../design-brief.md).

**Phase 1 status: IN PROGRESS — NOT YET QUALIFIED.** Do not confuse baseline adoption with a complete 14-screen implementation, accessibility certification or hosting approval.

## Architecture decisions and compatibility holds

- **Keep Next.js App Router, pinned React, TypeScript and existing lockfiles.** The repository's actual application lives in `apps/web`, not a new root `/src`. TypeScript is already strict. Enable `noUncheckedIndexedAccess` only alongside review/remediation of any newly discovered type errors, never by weakening existing gates.
- **Preserve the existing `/` foundation workbench and its same-origin `/api` rewrite.** It currently exercises a real Python HTTP boundary in Compose; silently swapping to `output: 'export'` or moving the homepage would break demonstrated behaviour and CI. A separately built/static demo can be considered after its content and route plan have their own acceptance tests.
- **Preserve `/sunset-v3`** as an isolated non-executing, synthetic frontend review route. The implementation commit for screens 01–04 predates this baseline adoption; it is not proof that the new phase has qualified.
- **No unconditional Azure deployment.** The user's personal account / startup credits are a proposed future billing route, not a verified authenticated subscription. Hosting, runtime choice, estimated running cost, alternatives, deprovision path and explicit approval must be reviewed before creating resources.
- **No sign-in simulation as a verified session.** The design brief's cast labels and the phrase “signed-in” are illustrative; no valid identity or role exists in the local demo. Approval and publication stay disabled and cannot be authorised by a UI badge.
- **Never invent a full event log.** The new prompt requests 1,284 events, but only the named key moments and aggregate totals are available in the approved visual script; seeded filler cannot serve as proof of reconciled football statistics or source evidence. Generate/validate event-level data only after a reviewed deterministic fixture design; do not fabricate intermediate stats or claim verdicts.
- **Do not draw synthetic x/y points or momentum values where no data exists.** The original v3 design brief restricts these representations to actual observed event coordinates. Screens without such data must display an explicit absent-data state.
- **Adopt Radix, Tailwind, Zod, Zustand and other new dependencies incrementally** after exact versions and locked changes are qualified in CI; do not add unverified packages to the existing foundation lockfile. Keep custom dialog focus controls guarded and tested until replacement is verified.
- **Visual authority:** [the design brief](../design-brief.md) provides the locked palette and says stadium lighting belongs to presentation boards rather than inside the app; where the implementation prompt differs about imagery, do not silently change the design. Treat all 14 screens as approved design scope, not as completed application pages.
- **Original assets:** keep historical Batch 1 and Batch 2 PNG provenance immutable. The seven recovered Batch 1 originals are **not yet committed** to GitHub; a prepared offline Git patch does not make the archive complete. No substitutions.
- **Verification:** a complete phase requires actual typecheck/build, lint and security checks, automated viewport screenshots at 390/1024/1440 and a deviations record. NVDA, VoiceOver, TalkBack, WCAG contrast and Lighthouse budgets must not be claimed passing without those executions.
- **Development only:** no force-push, no broad branch creation, no `main` promotion, no customer-provider activation, no database migrations, no cloud spend, no authorisation relaxation.

## Phase sequence

1. Foundation tokens, labelled navigation, route architecture, accessible shell and new test gates (this phase).
2. Deterministic event/claim contract and evidence-grounded engine.
3. Reusable accessible components and defensive state gallery.
4. Synthetic match → evidence → draft → audience journey.
5. Remaining screens and core route migration behind compatibility checks.
6. Guided presentation, replay and offline recovery.
7. Full accessibility, responsive, performance, security and content acceptance.
8. Presentation and release-readiness evidence.

**A phase stops on failing CI or absent evidence.** The attached brief's target metrics remain acceptance goals, not observed test results.

## AA palette and label acceptance (11 October 2026)

The delivered v3 uses the design's source palette except for one **accessibility-bound text swatch**: the dark `--md-subtle` value from the original brief (`#768898`) measures approximately **3.68:1 against `#23303c` raised panels** and **4.39:1 against `#19222d` panels**. It cannot satisfy the brief's 4.5:1 text requirement. The implementation uses `#8b9bac` (approximately **4.73:1** against the raised panel) and records the divergence rather than pretending exact colour compliance. Decorative `--md-line` remains unchanged; a new `--md-ui-stroke` token distinguishes essential control boundaries at or above 3:1 on each theme's backgrounds. Secondary labels, metadata, chips and mobile navigation are raised to a **12px minimum**.

New Playwright checks sample the actual rendered custom-property values for both themes, all three surfaces, legible foreground tokens and essential UI outlines. They are automated contrast/typography checks, **not** a replacement for an axe pass or manual screen-reader/zoom testing.
