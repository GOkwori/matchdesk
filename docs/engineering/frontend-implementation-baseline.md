# MatchDesk — Frontend Implementation Prompt

> Paste this whole document into your coding agent (Claude Code, GitHub Copilot agent, Cursor, etc.) at the root of the MatchDesk repository. Put `docs/design-brief.md` (the Sunset Studio design enhancement prompt) in the repo first; this prompt refers to it.

---

## 0. Your role and how to work

You are a principal frontend engineer and accessibility specialist building the MatchDesk demo for the Microsoft x Premier League "Inside the Game" Developer Hackathon. The result will be shown live to judges, so it must be fast, flawless on any screen, fully accessible, and tell a clear story in under three minutes.

Working rules:
1. **Inspect before you build.** Read the existing repo, `README`, `docs/design-brief.md` and any Batch 1 baseline. Follow existing conventions. Do not overwrite approved Batch 1 work without listing the change and the reason.
2. **Work in phases (Section 13).** At the end of each phase, stop and report: what was built, test results, screenshots at 390px / 1024px / 1440px, and any deviations from this brief.
3. **Never fake quality.** Don't skip, weaken or delete a failing test to get green. Fix the cause or report it.
4. **Truth over polish.** This is a synthetic demo. Never imply live data, real publishing, real partners or real players.
5. Repository: personal GitHub (`gokwori`). Hosting: Azure Static Web Apps on the personal Azure tenant. Never commit secrets.

---

## 1. Product and success criteria

**MatchDesk** turns football match events into verifiable stories. AI drafts insights, a deterministic engine verifies every claim against the event log, and a human producer approves before anything goes out.
Tagline (verbatim): **AI-assisted. Verified. Human-led.**

The demo succeeds when a judge can, unaided and in under 3 minutes:
1. Understand what MatchDesk does from the landing screen in ≤10 seconds.
2. See a key moment, open its evidence, and understand *why* a claim is verified or not.
3. Watch a draft get blocked, fixed, re-verified and become eligible.
4. See the fan-facing story and its "How we checked this" panel on a phone.

Everything that doesn't serve these four outcomes is secondary, and should be hidden behind progressive disclosure.

---

## 2. Tech stack (use unless the repo already dictates otherwise)

- **Next.js (App Router) + React + TypeScript (`strict: true`, `noUncheckedIndexedAccess: true`)**, built as a **static export** (`output: 'export'`) so the demo is fast, cacheable, SEO-friendly and works with no backend.
- **Styling:** Tailwind CSS v4 driven entirely by CSS custom-property design tokens (Section 5). No hard-coded colours or spacing in components.
- **Accessible primitives:** Radix UI (Dialog, AlertDialog, Tabs, Tooltip, Popover, Toast, Select, Switch, Slider). Use these instead of building your own focus traps.
- **Icons:** Lucide (tree-shaken).
- **Data validation:** Zod schemas for every data file.
- **State:** URL search params are the source of truth for shareable view state (`?t=67:12&moment=M-05&claim=CL-0214`). A small Zustand store holds session-only state (draft edits, dismissed banners, demo-tour progress).
- **Charts:** lightweight SVG components written in-house (momentum line, stat bars, pitch diagram). No heavy chart library.
- **Testing:** Vitest + Testing Library, `vitest-axe`, Playwright (+ `@axe-core/playwright`), Lighthouse CI, `size-limit`.
- **Quality tooling:** ESLint (`next/core-web-vitals`, `jsx-a11y` strict, `@typescript-eslint` strict), Prettier, Stylelint, Husky + lint-staged, Conventional Commits.
- Pin exact versions in the lockfile. Use Node LTS.

---

## 3. Data: one canonical synthetic match

All UI content is derived from data, never hand-typed into components.

Files in `/src/data/`:
- `match.nbr-riv.json`: fixture, teams, cast, replay metadata.
- `events.nbr-riv.json`: the **1,284-event** synthetic log. Generate it with a **seeded, deterministic script** (`scripts/generate-events.ts`) so every run produces identical output. The scripted key events must be exactly:

| Moment | Clock | Event | Description | Score |
|---|---|---|---|---|
| M-01 | 27:40 | E-0561 | Yellow card, Haddad (RIV #6) | 0–0 |
| M-02 | 34:18 | E-0688 | GOAL Okafor (NBR #9), right-footed, open play | 1–0 |
| M-03 | 41:03 | E-0790 | GOAL Lindqvist (RIV #11), finish from cut-back | 1–1 |
| — | 45:00 | E-0841 | Half-time | 1–1 |
| M-04 | 58:03 | E-1359 | Corner, Northbridge | 1–1 |
| M-05 | 58:17 | E-1366 | GOAL Okafor, header from the corner | 2–1 |
| M-06 | 63:04 | E-1402 | Yellow card, Mensah (NBR #4) | 2–1 |
| M-07 | 67:08 | E-1421 | Substitution, Riverside | 2–1 |

  Background events (passes, shots, fouls, corners) must reconcile to these totals at 67:12: possession 58/42, shots 14/9, on target 6/3, corners 6/3, fouls 8/11, yellows 1/1, reds 0/0. The log contains **no tracking, xG, or computer-vision data**.
- `claims.json` and `drafts.json`: D-031 v3 (CL-0213 Verified, CL-0214 Verified, CL-0215 Pending, CL-0216 Failed → Not eligible) and D-029 v2 (4/4 verified → Eligible, not approved, not published). Exact wording is in `docs/design-brief.md` §2.
- Cast: Dana Price (Producer, signed-in), Sam Reed (Verification analyst), Priya Shah (Editor), "MatchDesk" (system). Timestamps are 11 Oct 2026, Europe/London.

**Verification engine** (`/src/engine/`): pure, framework-free TypeScript functions.
- `statsAt(events, clock)` returns all match stats at any replay time.
- `verifyClaim(claim, events, clock)` returns `{ structural: Valid|Invalid, factual: Verified|Pending|Failed|NotVerifiable, evidenceIds[], calculation, reason }`.
- `draftEligibility(draft)` returns `{ eligible, blockingClaims[], message }`.
- It must be deterministic and side-effect free. The UI never decides a verdict itself; it always calls the engine.

---

## 4. Information architecture and routes

Every screen is a real, deep-linkable URL. Static-generate all routes with `generateStaticParams`.

| # | Screen | Route | Indexable |
|---|---|---|---|
| 01 | Welcome | `/` | Yes |
| 02 | Match overview | `/match/nbr-riv` | Yes |
| 03 | Live intelligence | `/match/nbr-riv/intelligence` | No |
| 04 | Tactical analysis | `/match/nbr-riv/tactical` | No |
| 05 | Moments & timeline | `/match/nbr-riv/moments/[momentId]` | No |
| 06 | AI insights | `/match/nbr-riv/insights` | No |
| 07 | Evidence explorer | `/match/nbr-riv/evidence/[claimId]` | No |
| 08 | Review queue | `/producer/queue/[draftId]` | No |
| 09 | Composer | `/producer/compose/[draftId]` | No |
| 10 | Publication journey (future state) | `/producer/publish/[draftId]` | No |
| 11 | Audience story | `/story/okafor-header-restores-northbridge-lead` | Yes |
| 12 | Activity & settings | `/workspace/activity`, `/workspace/settings` | No |
| 13 | Notification library | `/design-system/notifications` | Yes |
| 14 | Defensive states | `/design-system/states` | Yes |
| — | About / how verification works | `/about` | Yes |
| — | 404 / error | `not-found`, `error` | No |

**Navigation model (avoid overload):**
- Sidebar grouped into **four journey stages**, collapsed to icons below 1280px and replaced by a bottom tab bar (Match · Verify · Produce · Story) below 768px:
  - **Match:** Overview, Live intelligence, Moments, Tactical, AI insights
  - **Verify:** Evidence explorer
  - **Produce:** Review queue, Composer, Publication (tagged "Future state")
  - **Audience:** Story
  - Utility (footer of sidebar): Activity, Settings, Design system
- Show at most **one primary action per screen**. Secondary actions go in menus or "More".
- Every screen ends with a **"Next step" card** that links to the logical next screen in the journey, carrying context (e.g. from moment M-05 → "Check the evidence for this goal" → `/evidence/CL-0213`).
- Breadcrumbs on all non-root screens; the browser back button must always restore the previous view, including tab and selection state.
- **Context carries across screens:** the selected moment, claim, draft and replay time persist via URL params.
- Detail panels open as a right-side panel on desktop and as a full-screen sheet on mobile, both deep-linkable.
- A **command palette** (`Ctrl/⌘ + K`) to jump to any screen, moment, claim or draft, fully keyboard and screen-reader accessible.
- Labels "Preview", "Planned" and "Future state" make it clear what is real in the demo.

---

## 5. Design system implementation

Follow `docs/design-brief.md` §3 exactly. Tokens live in `/src/styles/tokens.css` as CSS custom properties and are mapped into Tailwind's theme.

**Dark (default, "Sunset Studio"):**
`--bg #10151C · --panel #19222D · --raised #23303C · --line #32404E · --text #F5F7FA · --muted #A7B4C2 · --subtle #768898 · --accent #FF9159 · --accent-soft #FFC084 · --on-accent #22140C · --success #70D8A9 · --info #7BC5FA · --warn #F6C46B · --error #FF858E · --pitch #0B4039`

**Light theme:** derive a light palette (warm off-white background, white panels, dark text, a darkened accent for text and icons on light surfaces). Every pair must pass the contrast test in §9.

**Rules:**
- Type: Inter for UI, IBM Plex Mono for IDs, clocks and calculations. Self-host fonts with `next/font`, `font-display: swap`, subset to Latin, preload only the primary weight.
- Fluid type with `clamp()`; 8px spacing scale; 12px card radius; 2px accent focus ring with offset, visible on every interactive element.
- Status is always **icon + text + colour**, never colour alone.
- Respect `prefers-color-scheme` on first visit, then the user's choice in Settings (persisted in `localStorage`, with try/catch). No flash of the wrong theme: set the theme attribute in an inline head script.
- Support `forced-colors: active` (Windows High Contrast): use system colours, never hide borders or focus.
- The stadium-light imagery is used only on the Welcome hero, as an optimised AVIF/WebP with a solid fallback colour. No photo-real players anywhere.

Build a documented component library in `/src/components/` (Button, IconButton, Chip/StatusChip, Banner, Toast, Dialog, AlertDialog, Sheet, Tabs, DataTable, ScoreHeader, ReplayScrubber, StatBar, MomentumChart, PitchDiagram, EvidenceRow, ClaimChip, DiffView, EmptyState, ErrorState, Skeleton, Stepper, NextStepCard, CommandPalette). Each component needs props typed, every state covered (default, hover, focus, active, disabled, loading, error), and a test file.

---

## 6. Interactivity: what makes the demo stand out

1. **Replay scrubber (signature interaction).** A global scrubber in the score header lets the presenter move the replay clock from 00:00 to 67:12, with play/pause and 1×/4×/16× speeds. Score, stats, timeline, momentum chart and claim verdicts all update from `statsAt()` and `verifyClaim()`. Example: drag to 40:00 and CL-0213 "Okafor scored both goals" becomes *Not verifiable yet*.
   - Keyboard: arrows ±1 s, PageUp/PageDown ±1 min, Home/End. Buttons for "Previous/Next key moment". This is the WCAG 2.5.7 alternative to dragging.
   - Screen readers: announce only key-moment changes via a polite live region, at most once every 2 seconds. Never announce every tick.
2. **Live re-verification in the Composer.** Editing the narrative updates claim chips in real time. Removing the "first brace of the season" sentence removes CL-0216; marking CL-0215 as an interpretation clears it from facts. The eligibility banner then animates from "Not eligible" to "Eligible". This is the hero moment of the pitch.
3. **Evidence drill-down.** Click any claim chip anywhere to open the evidence panel: Claim → Metric → Source events (clickable, jumps the scrubber to that event) → Calculation → Verdict.
4. **Request-changes flow** on Review queue: an accessible dialog with a required reason, validation, a loading state and a success toast, then the draft status updates in the queue.
5. **Resilience demo panel** (Demo mode only): toggles to simulate offline, timeout, stale data, permission denied and edit conflict, rendering the matching Defensive State in context. Shows judges the defensive design working live.
6. **Guided demo tour:** a 6-stop tour (Welcome → Moment M-05 → Evidence CL-0213 → Review queue D-031 → Composer fix → Audience story). Next/Back/Skip, keyboard operable, focus moved to each stop's heading, can be restarted from Settings. A "Reset demo" action restores the initial state.
7. **Presenter mode** (`?presenter=1`): optimised for a 1920×1080 projector, with larger base type, higher-contrast borders and hidden secondary chrome.
8. **Micro-interactions:** 150–250 ms transitions on state changes, number tweening for stats, and View Transitions API for route changes where supported. **All motion disabled under `prefers-reduced-motion` and the Settings toggle.**

---

## 7. Responsive requirements

- **Mobile-first CSS.** Use container queries for components and media queries only for page layout.
- Test widths: **320, 360, 390, 414, 768, 1024, 1280, 1440, 1920**, plus landscape phone (844×390).
- Layout behaviour:
  - < 768: bottom tab bar, single column, detail panels become full-screen sheets, tables become stacked cards, scrubber collapses to play/pause + key-moment buttons with an expandable full scrubber.
  - 768–1279: icon-rail sidebar, two columns where useful.
  - ≥ 1280: full sidebar, three-zone layouts (list · detail · context).
- **No horizontal page scrolling at any width**, including at 320 CSS px and at 400% zoom on 1280 (WCAG 1.4.10 Reflow). Wide data tables scroll inside a labelled, focusable region.
- Touch targets ≥ 44×44 px on touch devices, ≥ 24×24 px minimum everywhere (WCAG 2.5.8).
- Text spacing overrides (WCAG 1.4.12) must not clip or overlap content.
- Safe-area insets for notched phones; `100dvh` instead of `100vh`.
- Pitch diagrams and charts scale with `viewBox`; labels never drop below 12px.

---

## 8. Accessibility (WCAG 2.2 AA as the floor)

- Semantic landmarks (`header`, `nav`, `main`, `aside`, `footer`), one `h1` per page, and a logical heading order.
- A "Skip to main content" link as the first focusable element.
- On route change, move focus to the page `h1` and update the document title.
- Full keyboard operation: logical tab order, no traps, Escape closes overlays and returns focus to the trigger, roving tabindex in tabs/menus/lists.
- Keyboard shortcuts use modifiers or can be turned off (WCAG 2.1.4), and are listed in a `?` help dialog.
- Focus is never hidden behind sticky headers or banners (WCAG 2.4.11): use `scroll-padding`.
- Every form field has a visible label. Errors are described in text, linked with `aria-describedby` and announced, and nothing the user typed is lost on error.
- Charts and pitch diagrams have a text summary plus a "View as table" toggle with equivalent data.
- The replay clock is not read out continuously. Use live regions sparingly and politely; reserve assertive announcements for blocking errors only.
- Toasts must not disappear while hovered or focused, have a minimum 6 s duration, and their content stays available in the Activity log.
- Language set (`lang="en-GB"`), accessible names on all icon buttons, decorative icons `aria-hidden`.
- Plain-English microcopy, UK spelling, no AI jargon. Define "eligible", "verified" and "not verifiable" in a tooltip glossary.
- Manual checks in addition to automated tests: NVDA + Chrome, VoiceOver + Safari (macOS and iOS), TalkBack + Chrome, keyboard only, 200% and 400% zoom, Windows High Contrast. Record results in `docs/accessibility-report.md`.

---

## 9. Performance, SEO, security and resilience

**Performance budgets (fail CI if exceeded):**
- Lighthouse (mobile, simulated throttling) ≥ **95** for Performance, Accessibility, Best Practices and SEO on every indexable route; Accessibility = **100** target.
- LCP < 2.0 s, CLS < 0.05, INP < 200 ms, TBT < 150 ms.
- Initial JS ≤ 170 KB gzip per route (`size-limit`), CSS ≤ 40 KB gzip.
- Code-split heavy screens (Composer diff, Tactical) and lazy-load below-the-fold panels.
- Images in AVIF/WebP with explicit dimensions; no layout shift from fonts.

**SEO (for indexable routes):**
- Unique `<title>` and meta description per route via the Metadata API; canonical URLs; Open Graph and Twitter card tags with generated OG images (1200×630) per indexable page.
- `sitemap.xml` and `robots.txt` generated at build. Workspace and producer routes get `noindex`.
- JSON-LD: `SoftwareApplication` for the product and `WebSite` on home. **Do not** mark the synthetic match up as a real `SportsEvent` or `NewsArticle`.
- Semantic HTML, descriptive link text, meaningful `alt` text, and a crawlable `/about` page explaining verification.
- `manifest.webmanifest`, favicons and theme-colour for both themes.

**Security and privacy:**
- `staticwebapp.config.json` with strict security headers: Content-Security-Policy (no `unsafe-eval`; nonce or hash for the theme script), `Strict-Transport-Security`, `X-Content-Type-Options`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` (camera, microphone and geolocation off), `frame-ancestors 'none'`.
- No third-party trackers or cookies. If analytics are needed, use a cookieless, privacy-friendly option and say so in `/about`.
- Dependency audit in CI (`npm audit --audit-level=high`) plus Dependabot.

**Resilience:**
- Every screen has designed Loading (skeleton), Empty, Error, Offline and Partial-data states matching screen 14.
- A route-level error boundary with a friendly message, a reference ID and a Retry action.
- A service worker precaches the app shell and data so the **demo works fully offline**. The venue Wi-Fi must not be able to break the presentation.

---

## 10. Content and truth guardrails (enforced by tests)

- The synthetic-replay banner is present on every match, producer and audience screen.
- No real brands: Premier League, Opta, X/Twitter, Sky, club names or real player names.
- No "Published" or "Live" states. Approve and Publish are disabled and labelled **"Planned"**. Screen 10 is labelled **"Future state"**.
- No xG, player tracking, defender positions or CV confidence scores.
- AI insights always carry "Interpretation · Needs human review" and cite event IDs only.
- No dates before 2026.

---

## 11. Automated testing and regression strategy

All suites run in CI on every pull request; all must pass before merge.

| Layer | Tool | What it proves | Gate |
|---|---|---|---|
| Static | `tsc`, ESLint (jsx-a11y strict), Stylelint, Prettier | Type safety, a11y lint, style consistency | 0 errors, 0 warnings |
| Data | Vitest + Zod | Every data file validates; generator is deterministic (hash snapshot) | Pass |
| Canonical facts | Vitest | `statsAt('67:12')` equals the brief's totals; each scripted event exists with the correct ID, clock and score; claim verdicts and draft eligibility match the brief | Pass |
| Engine | Vitest | All verdict branches, edge clocks (00:00, 45:00, 67:12), tolerance boundaries | **100% branch coverage** on `/src/engine` |
| Components | Vitest + Testing Library + `vitest-axe` | Every state renders correctly; keyboard behaviour; no axe violations | ≥ 90% line coverage overall |
| Token contrast | Vitest | Compute WCAG ratio for every text/background and UI/background token pair in both themes | Text ≥ 4.5:1 (large ≥ 3:1), UI ≥ 3:1 |
| E2E journeys | Playwright (Chromium, Firefox, WebKit + Pixel 7 and iPhone 14 emulation) | Journeys J1–J5 below | Pass on all projects |
| Keyboard-only | Playwright | J1–J4 completed with keyboard only; focus visible at every step; focus returns after dialogs | Pass |
| Accessibility | `@axe-core/playwright` | Every route × dark/light × 390/1440, and every open dialog and sheet | **0 violations** |
| Responsive | Playwright | `scrollWidth <= clientWidth` at all widths in §7; reflow at 320px; no clipped text with WCAG 1.4.12 spacing applied | Pass |
| Visual regression | Playwright `toHaveScreenshot` | Every route × 390/1024/1440 × dark/light, plus key component states; animations disabled, dynamic regions masked | ≤ 0.1% pixel diff |
| Content guardrails | Playwright / build scan | Built HTML scanned for banned terms (Opta, Premier League, Twitter, "Published", "xG", years < 2026); banner present on required routes | 0 matches |
| Performance | Lighthouse CI + `size-limit` | Budgets in §9 | Fail on regression |
| SEO | Playwright + build checks | Titles, descriptions, canonical, OG tags, sitemap and robots correct; `noindex` on private routes; valid JSON-LD | Pass |
| Links | Build crawler | No broken internal links or missing assets | 0 broken |
| Offline | Playwright (`context.setOffline(true)`) | Demo tour completes offline after first load | Pass |

**User-journey E2E tests:**
- **J1 Judge first impression:** land on `/`, understand the value proposition, start the demo tour, reach the audience story in ≤ 8 interactions.
- **J2 Verify a moment:** open M-05 → evidence for CL-0213 → click source event E-1366 → scrubber jumps to 58:17.
- **J3 Fix a blocked draft:** queue → D-031 shows "Not eligible" → Composer → remove CL-0216 and reclassify CL-0215 → re-verify → "Eligible" → Approve shown as Planned.
- **J4 Request changes:** dialog validation error → enter reason → success toast → status updates → entry appears in Activity.
- **J5 Fan on mobile:** iPhone viewport, open story, expand "How we checked this", open "Not verifiable" explanation, share buttons disabled and labelled "Planned".
- **J6 Replay:** scrub to 40:00 → score 1–1, CL-0213 not verifiable yet; Home/End and key-moment buttons work.
- **J7 Resilience:** each fault toggle renders the right defensive state with a working recovery action.

**Determinism for visual tests:** run Playwright in the official Playwright Docker image so fonts render identically; freeze time to 11 Oct 2026 19:00 Europe/London; seed all randomness; wait for fonts with `document.fonts.ready`. Commit baselines to the repo. Baseline updates need a deliberate `--update-snapshots` commit with before/after images in the PR description.

---

## 12. CI/CD (GitHub Actions)

- Workflow on every PR: install (cached) → lint and typecheck → unit and component tests with coverage → build → E2E, a11y, responsive and visual tests (sharded) → Lighthouse CI → size-limit → content and SEO checks.
- Upload Playwright HTML report, traces, screenshot diffs and the Lighthouse report as artifacts.
- Azure Static Web Apps: preview environment per PR, posted as a PR comment; production deploy from `main` only after all checks pass.
- Branch protection on `main`: required checks, linear history.
- Nightly scheduled run of the full suite against production.

---

## 13. Delivery phases (stop and report after each)

1. **Foundations:** project setup, tokens, fonts, themes, layout shell, navigation, routing, CI skeleton, contrast tests.
2. **Data and engine:** event generator, schemas, `statsAt`, `verifyClaim`, `draftEligibility`, canonical-facts tests at 100% engine coverage.
3. **Component library:** all components with states, tests and axe checks; `/design-system/notifications` and `/design-system/states` built from them.
4. **Core journey screens:** 01, 02, 05, 07, 08, 09, 11 with the replay scrubber, evidence drill-down and live re-verification.
5. **Remaining screens:** 03, 04, 06, 10, 12, About, 404.
6. **Demo layer:** guided tour, presenter mode, resilience panel, reset, command palette, offline support.
7. **Hardening:** full E2E, visual baselines, Lighthouse budgets, SEO, security headers, manual screen-reader pass, `docs/accessibility-report.md`.
8. **Presentation polish:** OG images, final copy review against §10, a 3-minute demo script in `docs/demo-script.md`, and a recorded backup video of the full tour.

---

## 14. Definition of done

- [ ] All 14 screens plus About and 404 built, deep-linkable, and consistent with `docs/design-brief.md`.
- [ ] Every number on screen comes from the data and engine; canonical-facts tests pass.
- [ ] Journeys J1–J7 pass on Chromium, Firefox, WebKit and mobile emulation, including keyboard-only.
- [ ] 0 axe violations on all routes and themes; manual screen-reader checks recorded.
- [ ] No horizontal overflow from 320px to 1920px; reflow, zoom and text-spacing checks pass.
- [ ] Lighthouse ≥ 95 in all four categories on indexable routes; bundle budgets met.
- [ ] Visual regression baselines committed and green.
- [ ] Security headers and CSP verified on the Azure preview.
- [ ] Demo works offline, resets cleanly, and runs end to end in under 3 minutes.
- [ ] `README` covers setup, scripts, test commands, architecture, known limitations, and what is synthetic or planned.

When finished, report: a summary of what was built, links to the preview deployment and test reports, any deviations from this brief with reasons, and the known limitations.