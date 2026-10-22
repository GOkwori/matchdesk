# MatchDesk studio — manual accessibility runbook (WCAG 2.2 AA)

**Tracker:** [Issue #52](https://github.com/GOkwori/matchdesk/issues/52).
**Test surface:** the hosted studio at https://matchdesk-seven.vercel.app (synthetic data only), or a
local production build (`cd apps/web && npm run build && npx next start`).
**Automated evidence:** [studio WCAG 2.2 audit, 22 October 2026](../evidence/studio-wcag22-audit-20261022.md).
Automated checks do not certify assistive-technology use, real browser zoom or conformance; this runbook
is the human part. Every row stays **NOT RUN** until a named tester records it.

The studio has one theme (dark). It replaces the Sunset v3 surface covered by the
[earlier runbook](sunset-v3-accessibility-manual-runbook.md), which stays as history.

## 1. Device and assistive-technology matrix

| Environment | Objective | Status |
| --- | --- | --- |
| Windows + Chrome, keyboard only | Tab/Shift+Tab, Enter/Space, arrows, Escape; focus order and visibility | NOT RUN |
| Windows + Chrome + NVDA | Landmarks, headings, names/roles/states, live announcements | NOT RUN |
| macOS + Safari + VoiceOver | Rotor navigation, dialogs, focus return | NOT RUN |
| iOS Safari + VoiceOver **or** Android Chrome + TalkBack | Touch navigation, bottom tab bar, composer editing | NOT RUN |
| Desktop Chrome at real 200% and 400% zoom | Reflow, clipping, fixed bars, reading order | NOT RUN |
| Windows high contrast / forced colours; reduced motion | Focus, status cues without colour, no motion | NOT RUN |

Record browser, OS and AT versions, the tester, and the date and time.

## 2. Screens

| ID | Screen | Route | Status |
| --- | --- | --- | --- |
| 01 | Welcome | `/` | NOT RUN |
| 02 | Overview (incl. "Try to fool the verifier") | `/match/nbr-riv` | NOT RUN |
| 03 | Live intelligence | `/match/nbr-riv/live` | NOT RUN |
| 04 | Moments and timeline | `/match/nbr-riv/moments?moment=M-05` | NOT RUN |
| 05 | Tactical analysis | `/match/nbr-riv/tactical` | NOT RUN |
| 06 | AI insights (live run and rehearsal) | `/match/nbr-riv/insights` | NOT RUN |
| 07 | Evidence and verification | `/match/nbr-riv/evidence/CL-0214` | NOT RUN |
| 08 | Review queue | `/producer/queue` | NOT RUN |
| 09 | Composer | `/producer/compose/D-031` | NOT RUN |
| 10 | Publication journey | `/producer/publish/D-031` | NOT RUN |
| 11 | Fan story (EN/ES/FR) | `/story/okafor-header-restores-northbridge-lead` | NOT RUN |
| 12 | Activity and settings | `/workspace/activity`, `/workspace/settings` | NOT RUN |
| 13 | About | `/about` | NOT RUN |
| 14 | Guided tour (7 stops) | start from `/` → "Start the 3-minute guided demo" | NOT RUN |
| 15 | Not found | any unknown address | NOT RUN |

## 3. Scripts

### A. Keyboard
1. Reload; the first Tab reaches "Skip to main content"; Enter moves focus to the main content.
2. Operate every control in order with the keyboard only. Record skips, traps, invisible focus or unreachable controls.
3. **Search palette:** Ctrl+K (or the Search button) opens it; focus is in the field; Tab stays inside; Escape closes and returns focus to the opener.
4. **Guided tour:** each stop moves focus to the card's heading; Tab reaches "Skip tour" and the next-stop link; Escape closes the tour.
5. **Composer:** remove a sentence, mark one as opinion, then edit the CL-0214 sentence to say 60%. The result ("Sentence doesn't match the claim" and its reason) must be reachable and announced without moving focus.
6. **Phone width (390 px):** tab through long screens; a focused control must never be hidden under the bottom tab bar (2.4.11).

### B. Screen readers
1. Navigate by landmarks and headings on every screen; one `main`, one `h1`, labelled navigation.
2. Overview: "Claim 59% instead" — the rejection must be announced.
3. AI insights: switching "Which run" announces the new run's banner; "Replay step by step" and "Next step" announce the step count.
4. Composer: verdict changes are announced through status regions.
5. Fan story: switching to Español/Français changes the language of the content (`lang`), so the voice changes.

### C. Zoom, spacing, contrast, targets, motion
1. Real 200% and 400% browser zoom at about 1280 px: no two-dimensional page scrolling except data tables and the pitch graphics.
2. SC 1.4.12 text-spacing overrides (line height 1.5, paragraph 2, letter 0.12, word 0.16): no clipped or overlapping text.
3. Measure rendered contrast: text 4.5:1 (large 3:1), focus indicators and controls 3:1.
4. Targets at least 24×24 CSS px, or a documented exception.
5. With reduced motion set in the OS (or Settings → Reduce motion in the studio), nothing animates.

## 4. Recording

Use [the session record template](sunset-v3-accessibility-session-template.md), one record per
screen × environment, with the actual readouts or keystrokes, the WCAG criterion and the outcome.
Raise each failure as an issue and link it here. A PASS needs a named tester; CI does not count.
