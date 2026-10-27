# MatchDesk — UI Overhaul Assessment & Redesign Plan

**Assessed:** `GOkwori/matchdesk`, branch `development` @ `5e433d5` (16 Oct 2026), app at `/sunset-v3`
**Method:** production build run locally; all 14 screens captured at 1440px and 390px; axe-core (WCAG 2.2 AA) scan on every screen; source review of `apps/web` and the backend domain engine; side-by-side comparison with the seven Sunset Studio mock-up boards.

---

## 1. Verdict

The current build is **technically sound but presentationally weak**. Accessibility, factual consistency and test discipline are genuinely good: axe found 0 violations on all 12 scanned screens, and every number matches the canonical match script. But it reads as a cautious compliance document rather than a product. Judges will see grey panels, empty pitches and the word "Planned" before they see what MatchDesk does.

The gap to the mock-ups is not mainly styling. It comes from five root causes (Section 3). Fix them in order and the visual polish follows naturally.

---

## 2. What to keep

| Strength | Evidence |
|---|---|
| Accessibility foundation | 0 axe violations across 12 screens; focus moved on screen change; real focus traps; skip link; 44px targets; forced-colours tokens; reduced-motion rule |
| Test discipline | 17 Playwright specs (213 functional + 3 visual tests per the progress log) covering keyboard, reflow, text spacing, contrast and focus transfer |
| Factual consistency | `demo-data.ts` matches the canonical script exactly: 2–1 at 67:12, Okafor 34' and 58', Lindqvist 41', D-031 / D-029 statuses |
| Design tokens | Sunset Studio colours in `tokens.css`, AA-corrected subtle text, light-theme set |
| Honest boundaries | No fake brands, no fake publishing, privileged actions are never enabled |

Don't throw these away. The overhaul should keep the test suite green and the token system intact.

---

## 3. Root causes of "basic"

### R1. The UI argues against itself (biggest problem)
- **About 140 caveat phrases across 12 screens, roughly 12 per screen** (counted from "synthetic / not live / planned / no tracking / unavailable / illustrative / demo / not published").
- **23 disabled controls** and **28 "Planned / Unavailable" labels** in the source.
- The core proof screen undermines the product's own value proposition. On Evidence (07): *"Event-level evidence not available in this frontend fixture"*, *"this demo cannot reproduce the calculation"*, *"Not independently evaluated in this preview."*
- Most screens end with a bordered disclaimer panel ("Security boundary", "Data limits", "Human authority", "Reference eligibility is not execution authority").

**Effect:** a first-time user learns what MatchDesk *can't* do before what it *does*. The mock-ups carry the same honesty in one banner plus status chips.

### R2. The frontend is starved of data while a real engine sits unused
- The UI has **7 hand-typed moments** and a stats table. The other 1,277 events don't exist in the frontend.
- The backend already has a **seeded simulator, 6 metric formulas, 5 moment detectors, `verify_claim()`, a judge golden path and 9 audience variants (EN/ES/FR × analyst/fan/caption)**, and the event contract already carries `location {x,y}`.
- The backend simulates a *different* match ("late_winner", home/away), so two truths exist and neither shows up in the UI.

**Effect:** empty pitches marked "Coordinates unavailable", "No measured momentum series is supplied", and verdicts that can only be "reference" verdicts. This is the single reason Tactical, Command Centre and Evidence look empty next to the mock-ups.

### R3. There is no real navigation
- The whole app is **one 342-line client component switching screens with `useState`**. The URL never changes from `/sunset-v3`.
- **The browser Back button leaves the app** and lands on `/`, which is the developer JSON "Foundation workbench".
- No deep links, no shareable screen, no refresh-safe state. **Every page title is "MatchDesk | Foundation workbench".**
- The site root `/` (what a judge opens first) is a JSON validation form.

### R4. Flat visual hierarchy compared with the mock-ups
- Every panel has the same weight (same border, radius, padding and background), so nothing leads the eye.
- **Icons are Unicode glyphs**: every sidebar item except Overview uses the same `◈`.
- **Inter is declared but never loaded** (no `next/font`), so judges on Windows will see Segoe UI.
- **There is no motion at all.** The only transition and animation rules in the CSS are reduced-motion overrides that turn motion *off*. Nothing responds or feels alive.
- No atmosphere: the mock-ups' stadium-light depth, glow on active states, icon tiles, gauges and pitch visuals are absent.
- CSS is minified onto single 3,000-character lines (`sunset.css` line 4), which makes design iteration slow and error-prone.

### R5. Repetition and internal labels eat the screen
- The full-size score header (about 150px) and the replay banner (about 70px) repeat on every screen. At 1440×900, **the first 435px of every screen is chrome before any content**.
- Internal production labels are shown to users: *"SUNSET STUDIO V3 · SCREEN 08 · SYNTHETIC PREVIEW"*, *"Sunset Studio / Screen 03 of 14"*.
- Raw IDs (E-1366, M-05, CL-0213) appear in nearly every line, which is useful to an analyst but noise to a first-time viewer.

### R6. Mobile is a squeezed desktop
- At 390px, the logo, theme dropdown, banner, kicker, title and "Refresh demo view" button fill the first screen. **The audience story (the "mobile-first" screen) starts below the fold.**
- The bottom bar crams 7 destinations into a 4-column grid; "Moments" is cut to **"M"** behind the More button.
- "More" lists all 14 screens as a flat list. That's a sitemap, not navigation.

### R7. The signature interactions are missing
- The Composer textarea doesn't re-verify anything; claim chips are static.
- There is no replay scrubber, no evidence trace, no guided tour, and no persona or language switch.
- Most clicks only change a selection highlight or show "Read-only preview".

### R8. The navigation labels mislead
- **"Settings & Help" opens the Notification Library**; **"Editorial Review" opens the Composer**.
- Design-system pages (13 Notifications, 14 Defensive States) sit inside the product navigation, as if users would visit them.
- "Matches · Planned" occupies prime navigation space.
- Twelve navigation items with no grouping.

---

## 4. Property-by-property scorecard

| Property | Score /10 | Evidence | Target |
|---|---|---|---|
| Visual design and polish | **4** | Flat panels, glyph icons, no imagery, system font fallback, no motion | 9 |
| Information architecture | **4** | 12 ungrouped items; mislabels (R8); design-system pages in product nav | 9 |
| Navigation and wayfinding | **3** | No URLs, Back exits the app, no breadcrumbs or stepper, no "where am I in the workflow" | 9 |
| First-time user onboarding | **3** | Hero then disclaimers; no tour; no explanation of the pipeline in context | 9 |
| Returning-user efficiency | **2** | No remembered state, no recents, no shortcuts or command palette, theme not persisted | 8 |
| Interactivity | **3** | Selection highlights only; no scrubber, live verification or trace | 9 |
| Data visualisation | **3** | Empty pitches, goal markers only, plain bar meters | 9 |
| Content and microcopy | **4** | Accurate but defensive and repetitive; internal labels exposed | 9 |
| Responsiveness | **6** | No overflow at any width (good); mobile hierarchy and bottom nav poor | 9 |
| Accessibility | **8** | 0 axe violations, focus management, reflow and contrast tests | 9+ (keep) |
| Performance | **7** | Small static bundle, no heavy libraries; fonts not optimised | 9 |
| SEO and metadata | **2** | One generic title and description for all screens; no OG tags or canonical; root is the dev tool | 8 |
| Trust and honesty | **7** | Honest, but over-applied to the point of undermining the value | 9 |
| Presentation readiness | **3** | A judge would struggle to see the "wow" in 3 minutes | 10 |

---

## 5. Mock-up vs current, screen by screen

| # | Mock-up shows | Current build | Fix |
|---|---|---|---|
| 01 Welcome | Big hero over a 3D pitch with event arcs and data bars; live score card with possession gauges; four coloured capability tiles | Hero with an empty pitch outline; generic 3-step cards; disclaimer box | Animated pitch hero with real event arcs from the log; score card with gauges; "Start guided demo" plus three persona entry points |
| 02 Overview | KPI tiles with coloured icon tiles; stats bars; "Latest significant moments" with verified chips | Close in structure, but flat; "Refresh demo view" adds nothing | Icon tiles, accent top borders, verified chips, possession donut; replace "Refresh" with "Continue: fix D-031" |
| 03 Command Centre | Momentum chart, shot map with markers, key stats table, live feed, selected-moment card with video thumbnail and linked claims | Goal-tick chart, empty pitch "Coordinates unavailable", long feed | Rolling possession momentum and shot map from engine data; selected moment with an animated pitch replay of the event sequence (no video) |
| 04 Tactical | Tactical pitch with team-coloured event markers, filters, insights with confidence chips, team comparison bars | Empty pitch, two dropdowns, "Data limits" panel | Event-location pitch (shots, passes into final third, set pieces) with team toggle and time-range slider; comparison bars; insights tagged "Interpretation" |
| 05 Moments | Visual timeline with thumbnails, selected moment with media and "why detected" signals | Good structure; text-only | Keep; add event-type icons, a mini pitch replay per moment, and "jump replay to here" |
| 06 AI Workspace | Agent tabs, stepper, insight cards with mini pitch visuals, error card with retry | Stepper marked "not run" everywhere; text cards | Show the 4 specialist roles running *scripted* proposals from the golden path, with a progress animation; one honest "Scripted · no live model" chip |
| 07 Evidence | Claims table plus an expanded proof chain: claim → metric → 412 source events → calculation → verdict | Proof chain says "cannot reproduce", "not available" | **Run the real verifier on real events.** Show the event count, a calculation that actually executes, and a mismatch demo (forged value fails) |
| 08 Producer queue | Queue with thumbnails, draft detail, eligibility checks, request-changes dialog | Similar, but dense text and a disclaimer footer | Add thumbnails or mini pitches, an eligibility checklist with icons, and a request-changes flow ending in a toast |
| 09 Composer | Rich editor, inline claim chips, side-by-side version diff, linked evidence cards, preview card | Plain textarea, static chips, 8 buttons (5 disabled) | Inline claim highlighting, **live re-verification as you type**, real diff, broadcast-style preview card; 2 visible actions |
| 10 Publication | Five-step stepper, destination cards, success and failure paths | Similar text version | Animated stepper, destination cards with "Planned" ribbon, success and failure illustrations |
| 11 Audience | **Phone mock-up** with story, verified chip, pitch visual, "How we checked this" accordion; share sheet | Desktop page; pitch overlay says "no event-position data"; crest inconsistent (blue R) | Render the story inside a phone frame on desktop and full-bleed on mobile; real corner → goal markers; language/persona switcher (9 variants) |
| 12 Activity & Settings | Audit table with avatars and filters, review queue, version history, settings with theme cards | Basic lists | Avatars, filters, relative times, settings as cards; theme and preferences persisted |
| 13 Notifications | Component library sheet | Fine as a library | Move to `/design-system`; out of product nav |
| 14 Defensive states | 16 state cards with mini illustrations | Good grid, generic | Move to `/design-system`; add mini illustrations; link from the resilience demo toggle |

---

## 6. UX recommendations

### 6.1 Replace caveats with one trust system
- **One persistent "Synthetic replay" pill** in the top bar (amber dot plus label). Clicking it opens a popover explaining the demo boundaries once. Remove the large dismissible banner from every screen after first view; show it once on first visit only.
- **Maximum one contextual caveat per screen**, and only where it changes how the user should read the data (e.g. "Interpretation · needs human review" on an AI insight).
- **Hide unbuilt features instead of disabling them.** Remove "Matches · Planned", "Sign in (Planned)", "Save version (Planned)" and "Publish (Planned)" from main surfaces. Collect future capabilities on one **Roadmap** card on the Publication screen. Keep exactly one locked "Approve" button where the human gate is the point of the story.
- Delete the end-of-screen boundary panels ("Security boundary", "Data limits", "Human authority"). Move that content to `/about#trust`.
- Remove internal labels ("SUNSET STUDIO V3 · SCREEN 08"). Use user-facing eyebrows ("Producer · Review").

### 6.2 Make the verification real (unlocks most of the visual gap)
- Add a `northbridge_riverside` scenario to the backend simulator that reproduces the canonical script exactly: **1,284 events with event coordinates**, the 7 key moments, and totals reconciling to 58/42, 14/9, 6/3, 6/3, 8/11, 1/1.
- Add `scripts/export-demo-data.py`, which runs the simulator, `detect_moments`, the metrics, `verify_claim` (for CL-0213 to CL-0216) and the audience variants, then writes `apps/web/src/data/*.json` at build time. Add a CI check that the export is deterministic (hash match).
- Port `verify_claim` and the metric formulas to TypeScript, or ship precomputed verdicts per replay minute, so the scrubber and composer can re-verify instantly offline.
- Result: verdicts become **"Verified"**, not "Reference verified"; shot maps, event pitches and momentum are honest because they're computed from event coordinates, not tracking. Keep "No player tracking" as a single footnote on Tactical.

### 6.3 Navigation model
- **Real routes** (`/`, `/match/nbr-riv`, `/match/nbr-riv/moments/M-05`, `/evidence/CL-0214`, `/producer/queue/D-031`, `/story/...`) with per-route titles. Back and Forward must work. Move the JSON workbench to `/dev/workbench`.
- **Four journey stages** as the main navigation, with a **pipeline stepper in the top bar** that shows where the user is:
  `Match → Verify → Produce → Audience`
  (Match: Overview, Live, Moments, Tactical, AI · Verify: Evidence · Produce: Queue, Composer, Publication · Audience: Story). Utilities go in the user menu: Activity, Settings, Design system, About.
- **"Next step" card** at the end of every screen, carrying context (M-05 → "Check the evidence for this goal").
- **Detail drawers instead of page jumps** for claims, events and drafts: a right-hand drawer on desktop, a bottom sheet on mobile, both deep-linkable (`?claim=CL-0214`).
- **Compact sticky score bar.** The full score card shows only on Overview. Elsewhere, a 56px sticky bar holds crests, score, clock and the replay scrubber.
- **Mobile:** a 4-tab bottom bar (Match · Verify · Produce · Story) with no horizontal scrolling. "More" becomes a short sheet for utilities only. The theme selector moves into Settings.

### 6.4 First-time user journey (for judges and new users)
1. **Landing (10 seconds to understand):** headline, one-line value, an animated 3-step strip (Detect → Verify → Approve) that plays once, and a primary **"Start the 3-minute guided demo"** button.
2. **Choose a lens:** three cards: *I'm a producer*, *I'm a fan*, *Just show me everything*. Each sets the starting route and tour.
3. **Guided tour with spotlight coach marks (6 stops):** Goal M-05 → Evidence CL-0213 (watch the calculation run) → Queue D-031 blocked → Composer: delete the unsupported sentence and watch it turn Eligible → Story on phone → Approve stays locked (the human gate). A progress indicator ("Step 3 of 6") is shown throughout; Skip, Back and Esc always work.
4. **Teaching empty states and first-use hints:** "Tip: click any claim chip to see its evidence", shown once and then remembered.
5. **Plain-language glossary tooltips** for Verified, Pending, Failed, Not verifiable and Eligible.

### 6.5 Returning user journey
- **"Continue where you left off"** card on the landing page (last route, selection and replay time, stored locally with try/catch).
- **"Since your last visit"** strip: items that changed status, using the Activity log.
- **Command palette** (Ctrl/⌘ K) to jump to any screen, moment, claim or draft. Shortcuts are discoverable with `?`.
- **Persisted preferences:** theme, reduced motion, text size, "show technical IDs", dismissed hints and tour completion.
- **Skip intro**: a returning user goes straight to Overview, with the tour available from the help menu.
- **Recents** in the command palette and on Overview.

### 6.6 Reduce overload
- **One primary action per screen.** Everything else goes in a secondary row or a "More" menu (the Composer currently shows 8 buttons).
- **Technical IDs off by default** for viewers, behind a "Show IDs" toggle (on by default in producer views). Shown in monospace as chips when on.
- **Progressive disclosure:** proof chains collapsed to the verdict plus a one-line reason, expanding on click.
- **Content budget:** 90 words or fewer above the fold per screen (currently 274–399 words per screen).

### 6.7 Interactivity that will make the presentation stand out
1. **Replay scrubber** in the sticky bar. Dragging the clock updates score, stats, timeline and claim verdicts. Scrubbing to 40:00 turns CL-0213 into "Not verifiable yet". Keyboard and button alternatives are required.
2. **Live re-verification in the Composer:** claim chips highlight inline in the text, verdicts recompute on edit, and the eligibility badge animates from Not eligible to Eligible. This is the hero moment.
3. **Evidence trace animation:** opening a claim lights up its source events on the pitch and in the timeline, then the calculation counts up (412 events → 58%).
4. **Forged-value demo:** a "Try to cheat" toggle changes 58% to 59%; the verifier rejects it with "Needs revision" (the golden path already supports this).
5. **Audience switcher:** EN / ES / FR × Analyst / Fan / Caption, all bound to the same evidence digest, shown in the phone frame.
6. **Resilience panel** (demo mode): toggles for offline, timeout, stale and permission errors render the matching defensive state in place.
7. **Presenter mode** (`?presenter=1`): larger type for 1920×1080 projectors, plus a "Reset demo" button.

---

## 7. Visual design overhaul spec (to match the mock-ups)

- **Atmosphere:** a fixed app-shell background layer with a subtle stadium-light bokeh (blurred, under 8% opacity) and a warm radial glow behind the active content area. Never behind text-dense panels.
- **Three surface levels:** base canvas, glass panel (`backdrop-filter: blur(12px)` over a semi-opaque panel colour), and a raised/hero card with an orange inner glow and a gradient border on active or selected items.
- **Hierarchy:** one hero element per screen (score card, proof chain, phone story). KPI tiles get coloured icon tiles and a 2px accent top border in the status colour, as in mock-up 02.
- **Iconography:** Lucide icons throughout. Each nav item gets its own icon. Event-type icons: football (goal), card (booking), flag (corner), arrows (substitution), whistle (half-time).
- **Typography:** self-host Inter (400/600/800) and IBM Plex Mono (500) via `next/font`. Display 56/60 for the hero, H1 32, H2 20, body 14/20, numbers in tabular figures.
- **Crests:** one shared SVG shield component for both teams (fix the blue "R" on Audience).
- **Data viz:** possession donut gauges, rolling momentum area chart, shot map with on/off-target markers, team comparison diverging bars, event pitch with team-coloured markers and pass arrows. Every chart has a "View as table" toggle.
- **Motion** (all disabled under reduced motion): 200ms route cross-fade, 40ms staggered card entrance, number tweens, check-mark draw on verification, pulsing "replaying" dot, drawer slide.
- **Phone frame component** for the audience story on desktop, as in mock-ups 11 and 03.
- **Density by breakpoint:** 3-zone layouts (list · detail · context) at 1440px and above, 2 columns at 1024px, 1 column on mobile with sheets.
- **Light theme parity:** the same hierarchy using warm off-white and the AA-corrected accent tokens already in `tokens.css`.
- **CSS architecture:** un-minify into component-scoped files (CSS Modules or Tailwind with the existing tokens). No single-line stylesheets.

---

## 8. Prioritised roadmap

| Priority | Item | Root cause fixed | Effort |
|---|---|---|---|
| **P0** | Real routes, per-route titles, root = Welcome, workbench moved to `/dev` | R3 | M |
| **P0** | Cut caveats to ≤1 per screen; trust pill; hide planned features; remove internal labels | R1, R5 | S |
| **P0** | Grouped 4-stage nav, pipeline stepper, compact sticky score bar, mobile 4-tab bar | R5, R6, R8 | M |
| **P0** | Visual system: fonts, Lucide icons, surfaces, glow, KPI tiles, crests | R4 | M |
| **P1** | Canonical scenario in backend simulator, plus build-time JSON export | R2 | M |
| **P1** | Real verifier output in Evidence; shot map, event pitch, momentum | R2 | M |
| **P1** | Guided tour, persona entry, continue-where-you-left-off | Onboarding | M |
| **P1** | Composer live re-verification (hero moment) | R7 | M |
| **P2** | Replay scrubber driving all screens | R7 | L |
| **P2** | Audience phone frame plus 9-variant switcher | R7 | S |
| **P2** | Command palette, shortcuts, recents, "since last visit" | Returning users | M |
| **P2** | Motion layer, presenter mode, resilience panel, OG images and SEO | Polish | M |

If time is short, **P0 plus the Evidence and Composer items from P1** are the minimum for a standout demo.

---

## 9. Implementation brief for the overhaul

The brief that followed from this assessment:

```text
ROLE
Principal product designer-engineer brief. Overhaul the MatchDesk /sunset-v3 frontend so it
matches the Sunset Studio mock-ups in quality and feels intuitive and interactive for first-time and
returning users. Keep every existing accessibility and regression test passing, or replace it with an
equal-or-stronger test. Never fake capability: everything shown as "Verified" must be computed.

READ FIRST
docs/design/briefs/sunset-studio-design-brief.md (canonical script + tokens), docs/design/briefs/ui-overhaul-assessment-20261016.md (this
report), apps/web/src/app/sunset-v3/*, backend/src/matchdesk/domain/{simulator,metrics,moments,
verification,judge_golden_path,audience_variants}.py, e2e/specs/*.

NON-NEGOTIABLES
- WCAG 2.2 AA: 0 axe violations on every route x dark/light x 390/1024/1440; keyboard-complete
  journeys; reduced-motion honoured; reflow at 320px; text-spacing safe.
- Canonical facts unchanged (2-1 at 67:12; Okafor 34:18 and 58:17; Lindqvist 41:03; D-031 v3 not
  eligible; D-029 v2 eligible, not approved, not published). No real brands, players or footage.
  No publishing. Approve remains locked as the human gate.
- Max ONE contextual caveat per screen. Persistent "Synthetic replay" pill in the top bar with an
  explanatory popover. No end-of-page disclaimer panels. No internal labels such as "Screen 08".
- Unbuilt features are hidden, not disabled, except the single locked Approve button.

PHASE 1 - STRUCTURE (stop and report with screenshots)
- Convert the single useState screen switcher into App Router routes:
  / (welcome), /match/nbr-riv, /match/nbr-riv/live, /match/nbr-riv/moments/[id], /match/nbr-riv/tactical,
  /match/nbr-riv/insights, /match/nbr-riv/evidence/[claimId], /producer/queue/[draftId],
  /producer/compose/[draftId], /producer/publish/[draftId], /story/[slug], /workspace/activity,
  /workspace/settings, /design-system/notifications, /design-system/states, /about, /dev/workbench.
- Per-route metadata (title, description, OG), sitemap, robots; noindex on producer and workspace.
- Shared layout: grouped sidebar (Match, Verify, Produce, Audience) with Lucide icons; utilities in a
  user menu; pipeline stepper in the top bar; compact 56px sticky score bar (full score card on
  Overview only); breadcrumbs; "Next step" card per screen; detail drawers / bottom sheets with
  deep-link params; mobile 4-tab bottom bar with no truncation.
- Back/Forward, refresh and shared links restore the exact view (screen, tab, selection, replay time).

PHASE 2 - REAL DATA (stop and report)
- Add a deterministic `northbridge_riverside` scenario to backend/src/matchdesk/domain/simulator.py
  that reproduces the canonical script: 1,284 events with x/y event coordinates, totals reconciling
  to possession 58/42, shots 14/9, on target 6/3, corners 6/3, fouls 8/11, yellows 1/1.
- scripts/export-demo-data.py: run simulator, detect_moments, metrics, verify_claim for
  CL-0213..CL-0216, draft eligibility and the 9 audience variants; write apps/web/src/data/*.json.
  Add pytest + CI determinism check (hash) and a frontend Zod schema test.
- Port the metric formulas and verify_claim to pure TypeScript (src/engine) with tests proving parity
  with the Python output on the exported data, so the UI can re-verify offline at any replay time.

PHASE 3 - VISUAL SYSTEM (stop and report)
- Self-host Inter and IBM Plex Mono via next/font. Lucide icons. Un-minify CSS into
  component-scoped modules using the existing tokens.
- Surfaces: base, glass panel, hero card with orange glow / gradient border for active items.
  App-shell stadium-light background at under 8% opacity. KPI tiles with icon tiles and status-colour top
  borders. Shared SVG crest component. Event-type icons.
- Data viz from real data: possession donuts, rolling possession momentum, shot map, event pitch with
  team markers and pass arrows, diverging comparison bars - each with "View as table".
- Motion (off under reduced motion): route cross-fade, staggered entrance, number tweens,
  verification check draw, drawer slide.
- Phone-frame component for the audience story on desktop.

PHASE 4 - INTERACTION AND JOURNEYS (stop and report)
- Welcome: animated Detect -> Verify -> Approve strip; "Start the 3-minute guided demo"; persona
  entry (Producer / Fan / Everything); "Continue where you left off" for returning users.
- Guided tour (6 stops, spotlight coach marks, progress, skip/back/Esc, focus to each stop heading):
  M-05 -> CL-0213 evidence -> D-031 blocked -> Composer fix -> Story on phone -> locked Approve.
- Replay scrubber in the sticky bar driving score, stats, timeline and verdicts (keyboard: arrows,
  PageUp/PageDown, Home/End, previous/next key moment; polite announcements at most every 2s).
- Composer: inline claim highlighting; verdicts recompute on edit; removing the "first brace" sentence
  and reclassifying CL-0215 flips D-031 to Eligible with an animated badge; real v3/v4 diff.
- Evidence: trace animation (claim -> source events highlighted on pitch and timeline -> calculation
  counts up); "Try a forged value" toggle that the verifier rejects.
- Audience: EN/ES/FR x Analyst/Fan/Caption switcher bound to one evidence digest.
- Command palette (Ctrl/Cmd+K), "?" shortcut help, recents, "Since your last visit", persisted
  theme, motion, text size, "Show IDs" and tour state (localStorage, try/catch).
- Resilience panel (demo mode) rendering the defensive states in place; presenter mode; reset demo.
- One primary action per screen; at most 90 words above the fold.

PHASE 5 - QUALITY GATES
- Keep all existing e2e specs green; update selectors for routes. Add: journey tests for first-time
  tour, returning-user resume, composer flip, scrubber, deep links, Back/Forward; Python<->TS parity
  tests; visual regression at 390/1024/1440 x dark/light in the Playwright Docker image; Lighthouse CI
  >= 95 (Accessibility 100) on indexable routes; size-limit <= 170KB gz JS per route; caveat-budget
  test (fails if a screen renders more than one caveat phrase outside the trust pill).
- Produce before/after screenshots per screen next to the matching mock-up board in
  docs/evidence/ui-overhaul/.

ACCEPTANCE
A first-time viewer understands the product in 10 seconds, completes the guided demo in under
3 minutes without help, and sees a real verification run and a real blocked-to-eligible flip. A
returning user lands back where they left off in one click. Back never leaves the app.
```

---

## 10. Evidence captured

Screenshots and the scan report were captured locally during the assessment and are not committed (12 desktop screens, defensive states, root page, 7 mobile screens, `report.json` with per-screen axe results, word counts, caveat counts and overflow checks).
