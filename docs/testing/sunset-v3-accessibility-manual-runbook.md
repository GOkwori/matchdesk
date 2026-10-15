# Sunset Studio v3 — manual accessibility acceptance runbook

**Authority:** This runbook prepares human testing; it is not a completed accessibility audit.  
**Pinned application source:** development squash commit `17571e45916af2d8e80e22f45faf51903b9d88b7` (PR #57), including the keyboard focus and scrolled-heading repairs in PRs #56–57. This pinned application SHA is distinct from later documentation commits.  
**Automated evidence:** PR #57 source `760a67a7516ba04f9700ccc3d7b3107cb1de943b` passed all four mandatory exact-head CI workflows: 277 Chromium browser tests passed, 98 deliberate cross-project skips, three visual evidence checks passed, and the native-image qualification passed. Check the independent post-merge runs on application SHA `17571e4` before declaring the merged source qualified. These automated results **do not certify** real AT use, real browser zoom, visual parity or WCAG 2.2 AA conformance.  
**Manual status:** **NOT RUN** for all modalities, screens and themes until attributable observed evidence is supplied.  
**Tracker:** [Issue #52](https://github.com/GOkwori/matchdesk/issues/52).  
**Test surface:** `http://127.0.0.1:3000/sunset-v3` on a private local build, using synthetic data only.

## 1. Set up an isolated, pinned local preview

Use Git, Docker/Compose, a POSIX shell (WSL2 is suitable on Windows), and access to the MatchDesk repository. Do not reuse production credentials or a shared database. Run from an existing local MatchDesk checkout:

```bash
git fetch origin development
git worktree add --detach ../matchdesk-a11y-review 17571e45916af2d8e80e22f45faf51903b9d88b7
cd ../matchdesk-a11y-review
git rev-parse HEAD
python -m scripts.create_local_env
docker compose -p matchdesk-a11y-review up --build
```

- Stop if the checked-out SHA differs, the new worktree already exists, local port 3000/8000 is occupied, the environment generator refuses to proceed, or a service reports an unexpected failure. Diagnose; **do not delete/recreate any existing database or override local secrets**.
- The Compose project name is deliberately distinct from the usual `matchdesk` project; its PostgreSQL volume must stay isolated. API and web bind to `127.0.0.1`. Do not publish a public URL or enable sign-in, real producer authorisation, approval or publication.
- Open `http://127.0.0.1:3000/sunset-v3` in the named test browser and confirm it is explicitly labelled as a **synthetic preview**. `/api/ready` is intentionally fail-closed and must not be treated as a reason to enable backend permissions.
- After the session, stop Compose with Ctrl+C and use `docker compose -p matchdesk-a11y-review down` only if this dedicated project belongs to the test. **Do not use `down -v`, prune, reset, or remove another project's data.** Retain evidence separately from the repo worktree.

If a different code SHA is tested, record and independently qualify it before attributing any result to that revision. Do not transfer PR #57's automated evidence to later commits, including documentation-only merges.

### Physical Android TalkBack access without changing loopback bindings

The computer's `127.0.0.1` is **not** the phone's `127.0.0.1`. For the Android Chrome + TalkBack option, a tester with a trusted, physically connected Android phone can use a temporary **USB-only ADB reverse tunnel**, keeping the host's Compose web port bound to localhost. Only enable USB debugging with the device owner's consent, confirm the device identity, and use a trusted cable/computer.

```bash
adb devices
adb reverse tcp:3000 tcp:3000
```

Open `http://127.0.0.1:3000/sunset-v3` in Chrome **on that phone**, then enable TalkBack and follow the mobile assistive-technology protocol. Confirm the phone displays the same pinned, clearly labelled synthetic preview. After the manual session, remove this exact tunnel and revoke temporary debugging trust as appropriate:

```bash
adb reverse --remove tcp:3000
```

Do not expose the web service on `0.0.0.0`, use `adb tcpip`, open a LAN/firewall port, create a public tunnel, or connect a privileged account to make phone testing work. An iOS Safari + VoiceOver device needs a separately reviewed private access method; this Android-only USB path is **not** an iOS workaround. Without a working trusted mobile connection and an actual human tester, mark mobile AT **BLOCKED / NOT RUN**, not PASS.


## 2. Minimum device and assistive-technology matrix

| Environment | Test objective | Status |
| --- | --- | --- |
| Windows + Chrome, keyboard only | Full Tab/Shift+Tab, Enter/Space, arrows, Escape, focus ordering/visibility | NOT RUN |
| Windows + Chrome + NVDA | Landmarks, heading list, buttons/labels, dynamic notices, modal background isolation | NOT RUN |
| macOS + Safari + VoiceOver | Rotor navigation, names/roles/states, focus return and dialogues | NOT RUN |
| Android Chrome + TalkBack **or** iOS Safari + VoiceOver | Touch/screen-reader navigation, menu, controls, safe local dialogues | NOT RUN |
| Desktop Chrome at actual 200% and 400% browser zoom | Reflow, clipping, fixed-nav overlap, modal use, target discoverability | NOT RUN |
| Both themes and appropriate high-contrast/forced-colour settings | Actual rendered contrast, focus affordances, non-colour status cues | NOT RUN |

Record exact browser/OS/AT versions, tester and timestamp. The 320px automated viewport and `style.zoom` do **not** substitute for real 400% browser zoom. If hardware or independent reviewer access is unavailable, mark the affected row **BLOCKED** and explain why.

## 3. Screen and theme coverage

Observe both **dark** and **light** modes for each of the fourteen implemented destinations. Screen 13 and the Overview blocked-approval dialogue require the additional modal tests below. Every destination is synthetic-only; do not mistake unavailable real capabilities for missing keyboard functionality.

| ID | Destination | Dark | Light |
| --- | --- | --- | --- |
| 01 | Welcome & Access | NOT RUN | NOT RUN |
| 02 | Intelligence Overview | NOT RUN | NOT RUN |
| 03 | Match Intelligence | NOT RUN | NOT RUN |
| 04 | Moments & Timeline | NOT RUN | NOT RUN |
| 05 | Tactical Analysis | NOT RUN | NOT RUN |
| 06 | AI Intelligence Workspace | NOT RUN | NOT RUN |
| 07 | Evidence Verification | NOT RUN | NOT RUN |
| 08 | Producer Review Queue | NOT RUN | NOT RUN |
| 09 | Story & Commentary Composer | NOT RUN | NOT RUN |
| 10 | Review & Publication Journey | NOT RUN | NOT RUN |
| 11 | Audience Experience | NOT RUN | NOT RUN |
| 12 | Activity, Audit & Settings | NOT RUN | NOT RUN |
| 13 | Notification & Dialogue Library | NOT RUN | NOT RUN |
| 14 | Defensive States | NOT RUN | NOT RUN |

## 4. Human execution scripts

### A. Keyboard and focus — all screens

1. Reload the preview, then use **Tab** to reach the visible skip link. Press **Enter** and confirm keyboard focus moves to the main content; continue using only Tab/Shift+Tab/Enter/Space and applicable arrows.
2. Follow each visible interactive control in reading/operating order. Record unexpected skips, duplicate focus, disappearing focus rings, unreachable buttons, invisible actionable elements or traps. No pointer use during this pass.
3. At 320px and 390px, use the **mobile More** destination menu. Check its expanded state, all 14 choices, Escape close and returned focus. At a normal desktop width, use the **sidebar navigation** instead; the mobile More menu is not displayed there. After selecting a destination using either layout, confirm keyboard focus reaches the new named main landmark and its heading becomes visible.
4. On **Intelligence Overview**, open "Why is approval blocked?". On **Notification & Dialogue Library**, open "Try local discard" and all disabled approval/rejection/publication variants. Verify focus enters the dialog, stays inside while tabbing, Escape/cancel restores the exact opener, and the rest of the interface cannot be reached until close. Do not attempt real publishing.
5. With the fixed bottom bar visible, tab through controls near the bottom of long screens; a focused control must not be **entirely obscured** by author-created UI (SC 2.4.11). Inspect the visible focus indicator separately (SC 2.4.7).
6. On mobile at 390 CSS px, open **Evidence Verification** and scroll near the bottom. Select **Overview** using actual keyboard or screen-reader controls. Verify that the new heading is visible near the top, the new main landmark receives focus, and no stale viewport position remains. Repeat in dark and light modes and separately with real 400% desktop browser zoom. Record any unexpected scroll jump or lost focus.

### B. Real assistive technology

1. With **NVDA/Chrome**, navigate by landmarks, headings and form controls using normal NVDA navigation. Record each actual spoken name, role and state. Inspect the evidence claim register's table semantics and navigation.
2. With **VoiceOver/Safari**, use the rotor to inspect headings, links, controls and landmarks. Verify current-screen heading, disabled/unavailable state, expanded More menu and returned focus.
3. Open both custom modal implementations. Check that the accessible name and description are announced and **background content is not reachable through assistive-technology navigation**. DOM `aria-modal` and `inert` presence alone do not establish this outcome.
4. Check in-app warning, error, information and success examples on Screen 13. Confirm meaningful announcements without steals of focus, repeated speech or a claim that a backend action was performed. Important warnings/errors must remain discoverable.
5. Run at least one genuine mobile assistive-technology session and record the physical device, OS, browser, assistive-technology mode, gesture sequence, announcement and result.

### C. Zoom, spacing, contrast and targets

1. At a normal desktop width initially around **1280 CSS pixels**, apply **real 200% and 400% browser zoom** through the browser UI. Record the effective CSS viewport (e.g. inspect `window.innerWidth`/`window.innerHeight` in DevTools, without altering application state). Test modal use, More navigation, reading order and long/table content. Essential data tables may scroll internally, but the whole document must not require two-dimensional scrolling without an allowed exception.
2. Apply W3C SC 1.4.12 text overrides without changing other styling: line height **1.5x** font size, paragraph spacing **2x**, letter spacing **0.12x**, word spacing **0.16x**. Inspect labels, links, focused controls, errors and dynamic content for loss of meaning or functionality. The automated test samples overflow and selected clipping; it does not establish complete readability.
3. Check actual foreground/background colours in both themes. Normal text must reach **4.5:1**, qualifying large text **3:1**, and necessary non-text controls/indicators **3:1**, allowing only documented WCAG exceptions. Measure real composited appearance, not just design-token variables.
4. Inspect control target areas against WCAG 2.2 SC 2.5.8's **24×24 CSS px** baseline or a correctly documented exception; check target spacing and zoom. Inspect forced-colour/high-contrast and reduced-motion settings.
5. Capture a screenshot/short video for each material failure, with location and UI state. Do not include secrets, account tokens, production customer information or identity-bearing screenshots in public evidence.

Reference criteria: [1.4.10 Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html), [1.4.12 Text Spacing](https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html), [2.4.11 Focus Not Obscured](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html), [2.5.8 Target Size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html).

## 5. Capture, triage and gate the evidence

Use [the session record template](sunset-v3-accessibility-session-template.md) and create **one completed record per screen/theme/device/method combination**. Provide screenshot/recording/transcript paths, observed readouts/keystrokes, expected versus actual behaviour, WCAG criterion and reviewer identity. A generated matrix with NOT RUN values is not executed evidence.

- **PASS**: a named tester observed the expected behaviour and has traceable dated evidence.
- **FAIL**: an observed violation with reproducible steps, severity and a linked remediation issue.
- **BLOCKED**: an external prerequisite such as unavailable device, environment or reviewer prevents observation; record the blocker.
- **NOT RUN**: no test execution took place, regardless of automated green CI.

A critical/high accessibility failure blocks acceptance until repaired and retested on the exact new source. Unavailable observations do not become PASS. An independent qualified reviewer must approve the completed evidence and documented exceptions before anyone describes the surface as WCAG 2.2 AA conformant. Even that accessibility decision does not authorise promotion to `main`, production deployment, paid infrastructure or live producer capabilities.
