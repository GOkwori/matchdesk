# Sunset Studio design brief (v3)

The owner's design brief for the Sunset Studio look, written for a senior product designer for broadcast and sports-data tools (think Premier League match-centre, newsroom CMS and Microsoft Fluent-quality enterprise UI). It asks to refine the existing MatchDesk design mock-ups into a polished, internally consistent, judge-ready design set for the Microsoft x Premier League "Inside the Game" Developer Hackathon.

Keep the existing Sunset Studio look and the 14-screen structure. Your job is to make it sharper, calmer, more credible and 100% consistent, not to restyle it.

---

## 1. Product in one line

MatchDesk turns football match events into verifiable stories: AI-assisted analysis drafts the insight, deterministic checks verify every claim against the event log, and a human producer approves before anything is published.

Tagline (use verbatim): **AI-assisted. Verified. Human-led.**
Header strapline (use verbatim): **FOOTBALL INTELLIGENCE. EXPLAINED. VERIFIED. READY FOR BROADCAST.**

---

## 2. Canonical match script (single source of truth)

Every number, name, ID, time and claim on every screen MUST come from this script. Do not invent extra goals, players, scores or stats.

**Fixture:** Northbridge FC (Home, NBR) vs Riverside United (Away, RIV)
**Status:** Synthetic replay, NOT live. Replay clock **67:12**, Second half, replay speed 1×. Score **2–1**.
**Event log:** 1,421 synthetic events (E-0001 to E-1421), generated deterministically by `backend/src/matchdesk/domain/canonical_match.py`. Latest event **E-1421 at 67:08**. (Earlier drafts said 1,284, which contradicted the E-1421 identity.)
**Date of replay session:** 11 Oct 2026 (all timestamps in 2026, UK time).

| Moment | Clock | Event ID | What happened | Score after |
|---|---|---|---|---|
| M-01 | 27:40 | E-0561 | Yellow card — Haddad (RIV #6), late challenge | 0–0 |
| M-02 | 34:18 | E-0688 | GOAL — Okafor (NBR #9), right-footed finish, open play | 1–0 |
| M-03 | 41:03 | E-0790 | GOAL — Lindqvist (RIV #11), finish from cut-back | 1–1 |
| — | 45:00 | E-0841 | Half-time | 1–1 |
| M-04 | 58:03 | E-1359 | Corner — Northbridge, right side | 1–1 |
| M-05 | 58:17 | E-1366 | GOAL — Okafor (NBR #9), header from the corner (14 s after E-1359) | 2–1 |
| M-06 | 63:04 | E-1402 | Yellow card — Mensah (NBR #4), late challenge in midfield | 2–1 |
| M-07 | 67:08 | E-1421 | Substitution — Riverside United | 2–1 |

**Match stats at 67:12 (whole match so far):**
Possession NBR 58% / RIV 42% · Shots 14 / 9 · On target 6 / 3 · Corners 6 / 3 · Fouls 8 / 11 · Yellow cards 1 / 1 · Red cards 0 / 0.
Do NOT show xG, player-tracking, defender positions, heatmaps from tracking, or computer-vision confidence scores — the synthetic log has no tracking data. Where a visual would need it, show a "No tracking data" chip instead.

**Claims (CL) and drafts (D):**
- **D-031 v3 — "Okafor double restores Northbridge lead"** → **Not eligible**
  - CL-0213 "Okafor scored both Northbridge goals" — Verified (E-0688, E-1366)
  - CL-0214 "Northbridge have had 58% possession" — Verified (calculated from in-play events, ±1% tolerance)
  - CL-0215 "Riverside's best spell came from 30–45 minutes" — Pending (interpretation, awaiting producer review)
  - CL-0216 "Okafor's first brace of the season" — Failed (no season data in the event log)
  - Blocking message: "Approval blocked — CL-0215 is pending and CL-0216 has no supporting evidence. Resolve or remove before re-verification."
- **D-029 v2 — "Lindqvist levels for Riverside before the break"** → **Eligible · not approved · not published** (4 of 4 claims verified)

**Cast (use only these):**
- Dana Price (DP) — Producer, signed-in user, avatar "DP"
- Sam Reed (SR) — Verification analyst
- Priya Shah (PS) — Editor
- "MatchDesk" — system actor (automated detection and checks)

**Nothing has been published.** No version is ever marked "Published" or "Live". Version history uses v1, v2, v3 for drafts only.

---

## 3. Design system (locked tokens)

**Colour (dark, Sunset Studio):**
- Background `#10151C` · Panel `#19222D` · Raised `#23303C` · Border `#32404E`
- Text `#F5F7FA` · Muted `#A7B4C2` · Subtle `#768898`
- Accent (primary actions, active nav, key numbers) `#FF9159` · Accent soft `#FFC084` · Text on accent `#22140C`
- Success `#70D8A9` · Info `#7BC5FA` · Warning `#F6C46B` · Error `#FF858E`
- Pitch `#0B4039` with 1px white lines at 35% opacity
- Status colour is always paired with an icon AND a text label (never colour alone).

**Type:** Inter for UI (Display 40/44 bold, H1 28/34 bold, H2 20/26 semibold, Body 14/20, Caption 12/16). IBM Plex Mono for IDs, clocks and calculations (E-1366, CL-0213, 67:12, D-031 v3).

**Layout:** 8px spacing grid, 12px card radius, 1px borders, no heavy glows on UI cards. Desktop 1440px with a 240px left sidebar; mobile 390px with a bottom tab bar. The stadium-lights background belongs only on presentation board frames, never inside the app UI.

**Components to reuse identically everywhere:**
- Score header: crest + team name + Home/Away, mono clock pill "67:12", score "2–1", "Second half · Replay 1×".
- Synthetic replay banner (amber, dismissible): "Synthetic replay — Northbridge FC v Riverside United is invented test data replayed from a recorded event log. Not a live match."
- Status chips: Verified · Pending · Failed · Not verifiable · Eligible · Not eligible · Planned · Preview.
- Buttons: Primary (accent fill), Secondary (outline), Destructive (error fill), Disabled (raised fill, 50% text, lock icon + "Planned" where the feature is future state).
- Evidence row: claim text, linked event IDs in mono, status chip, "View evidence" link.

**Sidebar navigation (same order on every desktop screen):**
Overview · Matches · Live Intelligence · Moments & Timeline · Tactical Analysis · Evidence & Verification (Preview) · Producer Desk (Preview) · Editorial Review (Planned) · Audience Outputs (Planned) · Activity & Audit (Planned) · Settings & Help
Footer card: "AI-assisted. Verified. Human-led."

---

## 4. Hard guardrails

1. No real brands, logos or partners: no Premier League, Opta, X/Twitter, Instagram, TikTok, Sky or club logos. Use generic icons ("Social channel", "Data partner feed", "Broadcast graphics").
2. No photo-real players, faces, kits that resemble real clubs, or real stadium footage. Use abstract pitch diagrams, event markers and illustrated placeholders with a "Synthetic clip" label.
3. AI output is never shown as evidence. AI insights carry a "Needs human review" chip and cite only event IDs from the script.
4. Approve and Publish are separate steps. In the current demo, Approve and Publish buttons are disabled with a lock icon and "Planned". Screen 10 is labelled "Future state" in its title.
5. No dates before 2026. No "Published" or "Live" states anywhere.
6. Every error message gives a plain-English cause, what was preserved ("Your work hasn't been lost"), one next action, and a mono reference like "ref: req-7f3a".
7. WCAG 2.2 AA: 4.5:1 text contrast, visible 2px accent focus rings, 44px minimum touch targets on mobile, reduced-motion respected.

---

## 5. Screen-by-screen enhancements

**01 Welcome & Access** — Hero "Turn football moments into verifiable stories." Keep "Explore synthetic demo" primary and "Sign in (Planned)" disabled. Replace the four feature tiles with a three-step strip: Detect → Verify → Approve, each with one line and an icon.

**02 Intelligence Overview** — Score header, stats list from the script (no xG). Four attention cards: AI insights 3 (needs review), Verification queue 1 pending claim, Producer drafts 2 (1 not eligible), Audience outputs Planned. "Latest significant moments" lists M-02, M-03, M-05, M-06 with correct times.

**03 Match Intelligence Command Centre** — Momentum chart with markers at 34', 41', 58'. Shot map labelled "Shot locations from event log · No tracking data". Live feed rows match the script exactly; M-05 selected, showing the corner (E-1359) to goal (E-1366) link and claims CL-0213 Verified.

**04 Tactical Analysis** — Event-location view only (shots, passes into final third, set pieces) plotted from event coordinates. No player positions or formation shapes. Insights carry "Interpretation · Needs human review".

**05 Moments & Timeline** — Vertical timeline of M-01 to M-07. Selected moment M-05 (Okafor header 58:17). "Why this moment was detected" lists rule-based signals only: goal event E-1366, preceding corner E-1359 within 15 s, score change 1–1 → 2–1. No CV or audio confidence numbers.

**06 AI Intelligence Workspace** — Agent stepper: Analyse → Compose → Review → Adapt → Human decision. Insight cards cite event IDs and show "Needs human review". Keep one "Temporary issue" error card with Try again to show resilience.

**07 Evidence Verification Explorer** — Claims table CL-0213 to CL-0216 with the exact statuses above. Expanded CL-0214 shows Claim → Metric → Source events → Calculation (in mono) → Result, with "Structurally valid" and "Factually verified" as two separate verdicts.

**08 Producer Review Queue** — Two rows only: D-031 v3 (Not eligible) and D-029 v2 (Eligible · not published). Right panel inspects D-031 with the amber "Approval blocked" message. Approve button disabled · Planned. "Request changes" dialog pre-filled with a reason about CL-0215 and CL-0216.

**09 Story & Commentary Composer** — Editing D-031 v4 (unsaved). Headline and narrative match the script (Okafor 34' and 58', Lindqvist 41'). Claim chips inline in text. v3 vs v4 diff shows CL-0216 removed. Amber banner: "Re-verification required before approval." Last edited by Dana Price, 11 Oct 2026.

**10 Review & Publication Journey — Future state** — Stepper: Ready → Eligible → Approved → Destinations → Published, with the current demo stopped at Eligible for D-029 v2. Destinations use generic labels with "Planned" chips. Show success path and failure/recovery path as small illustrative diagrams, clearly labelled "Illustration".

**11 Audience Experience (mobile-first)** — Story card "Okafor's header puts Northbridge back in front", 58' · 2–1. Pitch diagram with corner (1) → goal (2) markers and "No tracking data". "How we checked this": Goal scorer in log — Verified; Timing of events — Verified; Defender positions — Not verifiable, with an info note explaining the exclusion. Share sheet buttons disabled · Planned.

**12 Activity, Audit & Settings** — Audit rows from the script with actors Sam Reed, Priya Shah, Dana Price, MatchDesk; times on 11 Oct 2026. Version history: D-031 v1, v2, v3 (drafts), no Published. Settings: Theme (Sunset Studio / Light / Dark), Reduced motion, Text size, Data refresh interval. Role restriction example with lock and "Planned".

**13 Notification & Dialogue Library** — Keep the current structure. Each dialog shows Default, Loading, Disabled, and Error-in-dialog. Add a light-theme counterpart row for the four banners. Use script content (D-031, D-029) in all copy.

**14 Defensive States** — Keep all 16 states. Make every "Edit conflict" or attribution use the cast above. Each card: icon, title, one-sentence cause, primary action, two small behaviour tags.

---

## 6. Presentation boards (if producing images)

- 16:9, 2 screens per board, numbered badges 01–14, title "MatchDesk — Design Review", subtitle "Sunset Studio theme".
- One mobile preview strip and one component callout per board.
- UI text must be crisp and legible at 100% zoom; no merged or garbled words; never repeat a badge number.
- Footer: "Synthetic demo · Football intelligence platform" left, "Analyse · Verify · Create · Inform" right.

---

## 7. Final quality check (run before returning output)

- [ ] Every score, clock, scorer, event ID, claim ID and percentage matches Section 2.
- [ ] Same sidebar, score header, banner and chips on every screen.
- [ ] No real brands, real-looking players, xG, tracking or CV confidence scores.
- [ ] No "Published"/"Live" states; Approve/Publish disabled · Planned.
- [ ] Only Dana Price, Sam Reed, Priya Shah and MatchDesk appear as actors.
- [ ] All dates are 2026.
- [ ] Contrast, focus rings, touch targets and icon + label on every status.

Return the screens in order 01–14 and list any place where you had to deviate from this brief, with the reason.