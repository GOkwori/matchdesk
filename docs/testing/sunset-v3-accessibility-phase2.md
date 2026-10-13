# Sunset Studio v3 — accessibility Phase 2 qualification protocol

**Baseline:** `development` squash commit `0d003ca72a1fa0b8c07533f8740e946d6510dc63` (PR #50).
**Scope:** Fourteen implemented synthetic-only demo screens, dark and light themes.
**Status as authored:** Automated Phase 2 checks proposed; manual checks **NOT RUN**. No WCAG 2.2 AA conformance statement or independent accessibility certification is authorised.
**Promotion boundary:** Work through a reviewed PR into `development` only. `main`, production, identity, producer mutation, publishing and deployment gates do not change.

## What the automated subset can establish

- The pre-existing `sunset-v3-accessibility-baseline.spec.mjs` asserts one main and H1, skip-link focus/activation, no document overflow at 390/768/1280/1440 CSS px, and no browser exceptions on every screen in both themes.
- The pre-existing `sunset-v3-contrast.spec.mjs` validates semantic colour tokens against the three designated surfaces, an essential control-outline token, primary button computed contrast and selected minimum label sizes. It **does not measure every rendered pixel, graphic, icon or transparency blend**.
- The Phase 2 `sunset-v3-keyboard-reflow.spec.mjs` adds keyboard-only sequential Tab/Enter navigation, Escape and custom-dialog focus restoration, measured mobile-menu targets, and document-width reflow at **320 CSS px** for all fourteen screens and both themes.
- A 320 CSS px viewport approximates the **width** requirement of WCAG 2.2 SC 1.4.10 for a desktop viewport starting at 1280 CSS px and magnified 400%. It **does not certify actual browser zoom**, text-spacing overrides, viewport-height reflow, every interactive state, or screen-reader experience.
- All automated checks must pass at the exact PR head under existing Foundation CI, Foundation integration, Source security and Dependency audit. Retries must not suppress failed evidence. Retain CI artifacts, screenshots and traces as applicable.

## Manual execution prerequisites (do not pre-mark as PASS)

Record the tested git SHA, PR number, reviewer name, date/time, browser version, OS, display/viewport dimensions, zoom, locale and assistive-technology version. Test the actual running `/sunset-v3` demo on an isolated trusted environment. Do not enable login, approvals, publishing, system notifications or other unsupported features to perform accessibility tests.

| Test environment | State | Required evidence |
|---|---|---|
| Windows desktop, Chrome + keyboard-only (no pointer) | NOT RUN | Ordered Tab/Shift+Tab path, focus screenshots and defect IDs |
| Windows desktop, Chrome + NVDA screen reader | NOT RUN | Landmark/heading and control announcements, modal/notice observations |
| macOS Safari + VoiceOver | NOT RUN | Rotor navigation, role/state announcements and focus restoration |
| iOS Safari + VoiceOver **or** Android Chrome + TalkBack | NOT RUN | Touch/screen-reader navigation, 24 px target inspection and modal interaction |
| Desktop browser at 200% and 400% actual zoom | NOT RUN | Measured CSS viewport, responsive screenshots and obstruction findings |
| Contrast/manual visual inspection, light and dark | NOT RUN | Sampled foreground/background pairs, ratio, pixel context, exception reasoning |

If a listed platform is unavailable, record **BLOCKED** with reason; never relabel browser automation as a manual screen-reader observation. Additional platforms can be added without changing these required controls.

## Manual keyboard and focus checks

1. Reload each of the fourteen screens from its actual mobile More destination where applicable. Starting from the browser's normal focus position, use only **Tab**, **Shift+Tab**, **Enter**, **Space**, arrow keys when applicable and **Escape**; do not programmatically focus controls or click.
2. Confirm the first reachable skip link is visible when focused; Enter places visible keyboard focus on the main landmark. Inspect the sequence through the theme selector, navigation, links, action controls, filters, claim inspection and any safe local-note field. No unexpectedly skipped, invisible or disconnected focus stops.
3. Open the persistent mobile More menu by keyboard. Confirm `aria-expanded` is reflected in screen-reader state, all fourteen options are reachable and named, and selecting a destination lands in the expected view. Escape dismisses the menu and restores focus to its opener. Focus must never be lost to the document body.
4. Open the Notification & Dialogue Library's safe local discard dialog using keyboard only. Confirm initial focus, Tab/Shift+Tab containment, Escape/cancel, focus restoration, name/description announcement and that the background cannot be activated. Repeat with the **disabled** producer approval/rejection/publication examples; none may execute backend actions.
5. Inspect focus indicators against both themes, high contrast/forced-colour settings and when content is scrolled. A focused control should not be wholly obscured by the fixed mobile navigation or dialogs (WCAG 2.2 SC 2.4.11).
6. Record every unique failure with screen, exact keystrokes, expected versus observed focus target, computed CSS selector/label, severity and trace/screenshot location. Do not silently reorder controls or remove keyboard access to make tests pass.

## Manual screen-reader and status checks

1. For each screen, navigate by landmarks and headings. Expect exactly one meaningful main landmark and H1, one readable current-screen title and no synthetic fixture portrayed as live data.
2. Navigate by buttons, form controls, tables and links. Confirm descriptive accessible names, selected/pressed/expanded/disabled states, useful table headers, and names for the claim register and inspection actions.
3. In the notification library, verify that success/information/warning/error semantics are announced at a sensible time without stealing focus, spamming announcements or implying a real backend operation succeeded. Important errors must remain perceivable if examples are dismissed.
4. Inspect custom dialogue labels and descriptions, focus containment, Escape behaviour and focus return with NVDA and VoiceOver. Ensure screen-reader virtual cursor cannot interact with background content when a true modal is open.
5. Check the local-only defensive scenarios for clear safe recovery instructions and that planned/blocked actions are not announced as executable. Audit evidence labels for truthfulness (illustrative verdicts are not independently verified).
6. Attach an actual assistive-technology session record and note the precise phrase/role observed. Automated DOM role queries, aria attributes and screenshot capture are **not** substitutes.

## Manual zoom, reflow, text spacing, targets and contrast

- From a desktop width of **1280 CSS px**, test **200% and 400% real browser zoom**. At 400%, target approximately 320 CSS px of horizontal content width; also inspect vertical content at an effective height of 256 CSS px where appropriate. Look for loss of controls, clipped labels, two-dimensional page scrolling, fixed-navigation obstruction and inaccessible dialogues. A data table may require internal horizontal scrolling only when its two-dimensional layout is essential; the overall document must not.
- Check 390, 768, 1280 and 1440 CSS px for both themes, and rotate mobile orientation. Apply WCAG text-spacing adjustments (line height 1.5x, paragraph spacing 2x, letter spacing 0.12x and word spacing 0.16x font size) and verify labels/actions remain usable.
- Manually assess interactive targets against **24 x 24 CSS px minimum** or correctly documented WCAG 2.2 SC 2.5.8 exceptions. The automated More-menu check covers only those standalone options, not every target or spacing exception.
- Sample actual rendered text/background combinations (including status chips, secondary labels, hover/focus states, disabled states where relevant and overlaid surfaces). Require **4.5:1 for normal text**, **3:1 for qualifying large text**, and **3:1 for essential non-text UI component boundaries/state indicators**, subject to the applicable WCAG exceptions. Check both light and dark, without assuming token-level success guarantees actual rendered contrast.
- Test forced-colour/high-contrast and reduced-motion modes. Inspect visible focus indicators, icon meaning without colour, and readable ordering/labels. Preserve approved Sunset Studio design tokens except for justified, reviewed accessibility repairs.

References: [SC 1.4.10 Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html), [SC 1.4.3 Contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html), [SC 2.5.8 Target Size (Minimum)](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html).

## Per-screen execution register — no implied verification

Use one row per test/device/theme/zoom combination; these fourteen rows are the **initial backlog**, not passed tests.

| Destination | Manual keyboard | NVDA/VoiceOver | Real zoom and contrast | Findings |
|---|---|---|---|---|
| 01 Welcome & Access | NOT RUN | NOT RUN | NOT RUN | — |
| 02 Intelligence Overview | NOT RUN | NOT RUN | NOT RUN | — |
| 03 Match Intelligence | NOT RUN | NOT RUN | NOT RUN | — |
| 04 Moments & Timeline | NOT RUN | NOT RUN | NOT RUN | — |
| 05 Tactical Analysis | NOT RUN | NOT RUN | NOT RUN | — |
| 06 AI Intelligence Workspace | NOT RUN | NOT RUN | NOT RUN | — |
| 07 Evidence Verification | NOT RUN | NOT RUN | NOT RUN | — |
| 08 Producer Review Queue | NOT RUN | NOT RUN | NOT RUN | — |
| 09 Story & Commentary Composer | NOT RUN | NOT RUN | NOT RUN | — |
| 10 Review & Publication Journey | NOT RUN | NOT RUN | NOT RUN | — |
| 11 Audience Experience | NOT RUN | NOT RUN | NOT RUN | — |
| 12 Activity, Audit & Settings | NOT RUN | NOT RUN | NOT RUN | — |
| 13 Notification & Dialogue Library | NOT RUN | NOT RUN | NOT RUN | — |
| 14 Defensive States | NOT RUN | NOT RUN | NOT RUN | — |

## Evidence record template and release disposition

For each run capture:

- `run_id`, `git_sha`, `screen`, `theme`, `browser`, `os`, `assistive_technology`, `zoom`, `effective_css_viewport`, `method` (automated/manual), `reviewer`, `timestamp`.
- `expected`, `actual`, `status` (PASS/FAIL/BLOCKED/NOT RUN), `wcag_sc`, `severity`, `evidence_paths`, `issue_url`, `remediation_sha`, `retest_run_id`.
- A reviewer-approved final summary, explicit exceptions, known failures and business impact. Keep any user screenshots, speech recordings and logs free of credentials, personal data and unapproved production information.

**Automatic-gate outcome:** only `AUTOMATED BASELINE PASS` after all exact-head workflows are green.  
**Manual outcome:** retain `MANUAL VALIDATION OUTSTANDING` until genuinely performed and signed off.  
**Conformance outcome:** do not claim `WCAG 2.2 AA compliant/certified` from these probes or a self-authored checklist. Independent qualified assessment and evidence-backed remediation remain separate gates.

A failed or unavailable manual test never silently becomes a passed requirement, and no automated check grants authorisation to deploy, publish or alter a production environment.
