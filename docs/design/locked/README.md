# MatchDesk · Sunset Studio · Locked Design (16 Oct 2026)

This folder is the **visual source of truth** for the MatchDesk frontend. It was approved by George Okwori on 16 Oct 2026. It combines his Sunset Studio boards (09–14) with a guided tour (from Option C) and a three-panel Evidence layout (from Option B).

| Path | What it is |
|---|---|
| `screenshots/*.png` | **Visual targets.** Match these at 1440px (desktop) and 390px (phone). |
| `reference-html/*.html` | Static markup behind each screenshot. Use it for exact spacing, sizes and copy. **Not production code**: rebuild as real components. |
| `tokens.css` | Locked design tokens. **Tokens win** where a reference file differs: three colours were corrected for contrast. |
| `brand/` | Panther logo and favicon set |
| `fonts/` | Plus Jakarta Sans (400–800) and IBM Plex Mono (500–600) `.woff2`, for reference renders. Production loads them with `next/font`. |

## 1. Locked screens

| # | Screenshot | Route (target) | Key elements |
|---|---|---|---|
| 01 | `01-overview.png` | `/match/nbr-riv` | Hero score card with replay slider and goal markers · 4 KPI tiles (icon tile, status-colour top border) · Latest significant moments · **Guided tour pop-up (1 of 6)** · "Your next step" card · Match statistics with "View as table" |
| 02 | `02-evidence.png` | `/match/nbr-riv/evidence/[claimId]` | Compact score strip with breadcrumb · **three panels**: claims list · proof chain (Claim → Metric → Source events → Result), rolling-possession chart, calculation, "Try a forged value" · where the claim is used, verification record, next step |
| 03 | `03-composer.png` | `/producer/compose/[draftId]` | Re-verification banner · breadcrumb plus save status · score header · headline · rich-text narrative with **inline claim highlights** · claim chips · linked evidence with pitch thumbnails · version compare · eligibility card · Match Centre preview · Save draft / Submit for review |
| 04 | `04-fan-story-phone.png` | `/story/[slug]` (public) | Logo plus EN/ES/FR switch · Verified moment banner · headline · score row · corner → goal pitch diagram · "How we checked this" |
| 05 | `05-component-sheet.png` | `/design-system` | Tokens, type, buttons, status chips, workflow stepper, banners, required-reason dialog, defensive states |
| 06 | `06-mobile-pattern-overview.png` | all app routes below 768px | **Mobile pattern**: compact header (logo, replay pill, search), compact score card with slider, next-step card, 2-up KPIs, **4-tab bottom bar (Match · Verify · Produce · Story)**. Apply locked tokens and the panther logo; this pattern file still shows the old placeholder mark and serif crest letter. |

Screens not drawn here (Live Intelligence, Moments, Tactical, AI insights, Review queue, Publication, Activity, Settings) use the same shell, tokens and components, and follow the content specs in `docs/design-brief.md` §5.

## 2. Shell

- **Sidebar (≥1024px):** 240px wide with a vertical gradient (`--md-sidebar-top` → `--md-sidebar-bottom`) and a 1px right border.
  - Logo: panther mark (36px) plus the wordmark "Match**Desk**" (Desk in accent), 21px/800.
  - Nav items: 18px Lucide-style stroke icons with labels, 10×12 padding, 9px radius. Order: Overview · Match Intelligence · Moments & Timeline · Tactical Analysis · Evidence & Verification · Producer Tools (count badge) · Audience Story · Activity & Audit · Settings & Help.
  - Active item: orange gradient wash, 1px accent border at 55%, accent icon, weight 700.
  - Footer card: waveform icon plus "AI-assisted. Verified. Human-led."
- **768–1023px:** the sidebar collapses to a 72px icon rail with labels under the icons.
- **Below 768px:** no sidebar. Use the 4-tab bottom bar (pattern 06), 70–78px tall, respecting the safe area.
- **Top of content:** page H1 (28/800) with a one-line subtitle on the left. On the right: **Synthetic replay pill** (amber dot, opens an explanation popover), search button (Ctrl K), avatar "DP".
- **Background:** canvas colour plus one warm radial glow at the top right. Never put glow behind dense text.

## 3. Components (see `05-component-sheet.png`)

- **Buttons:**
  - Primary: vertical gradient (`--md-accent-grad-top` → `-bottom`), **dark text `--md-on-accent`**, 800 weight, 44px minimum height, orange drop glow.
  - Secondary: raised fill with a `--md-control-line` border.
  - Destructive: `--md-danger-solid` with white text.
  - Locked: dashed border, lock icon, "Approve · Planned". This is the only disabled-but-visible control allowed.
- **Status chips:** icon plus label plus colour, always: ✓ Verified, ! Pending, ✕ Failed, ○ Not verifiable, ✓ Eligible, ✕ Not eligible, ◷ Interpretation. 7px radius for claim status; pill shape for eligibility.
- **Claim highlight (composer text):** verified = success tint plus solid underline; pending = warning tint plus dashed underline; failed or removed = error tint plus strikethrough.
- **Banners:** info, warning, error (with Retry and `ref:` code), success. Icon in a filled circle, coloured label, message, optional action.
- **Workflow stepper:** filled success circles with ✓ for done, accent circle with a glow ring for current, outlined for future.
- **Score header:** shield crests. Northbridge is a solid `--md-home` shield with a dark triangle; Riverside is dark with three `--md-away` stripes. Both have a 1.6px light outline. Mono clock pill, score at 40–56px/800.
- **Guided tour pop-up:** light card (`#F5F7FA`) with dark text, an arrow pointer, label "GUIDED TOUR · n OF 6", progress dashes, "Skip tour", and a dark primary action button.
- **Next-step card:** orange-washed gradient panel with eyebrow "YOUR NEXT STEP", a 19px title, one sentence, and one primary action.
- **Pitch diagrams:** `--md-pitch` fill, `--md-pitch-line` markings, `--md-home` event markers with a light outline, dashed `--md-accent-soft` paths for delivery and pass.
- **Charts:** every chart has an `aria-label` summary and a "View as table" toggle. Home and away series must also differ by lightness or line style, not hue alone.

## 4. Copy and facts (must match exactly)

- **Fixture:** Northbridge FC 2–1 Riverside United, replay clock 67:12, synthetic, 1,284 events.
- **Goals:** Okafor 34:18 (E-0688), Lindqvist 41:03 (E-0790), Okafor header 58:17 (E-1366) after the corner at 58:03 (E-1359).
- **D-031:** CL-0213 ✓, CL-0214 ✓ (58.0% = 2,142 s / 3,693 s in-play; replace these figures with the engine export when available), CL-0215 pending interpretation, CL-0216 failed.
- **D-029:** eligible, not approved, not published.
- **Cast:** Dana Price (DP), Sam Reed, Priya Shah. Dates are 11 Oct 2026.
- **Not allowed:** real brands, player photos, "Published" states, or white text on orange.

## 5. Brand assets → Next.js

| File | Destination |
|---|---|
| `brand/favicon.ico` | `apps/web/src/app/favicon.ico` |
| `brand/favicon-512.png` | `apps/web/src/app/icon.png` |
| `brand/apple-touch-icon.png` | `apps/web/src/app/apple-icon.png` |
| `brand/favicon-192.png`, `favicon-512.png` | `manifest.webmanifest` icons (`theme_color: #0e1319`, `background_color: #0e1319`) |
| `brand/matchdesk-mark-256.png` | `apps/web/public/brand/` |

Use `matchdesk-mark-256.png` for the sidebar and mobile logo via `next/image`, with `alt=""` because the "MatchDesk" text sits beside it.
