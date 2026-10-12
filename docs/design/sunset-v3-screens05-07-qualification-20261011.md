# Sunset Studio v3 — Screens 05–07 qualification and visual review

**Recorded:** 11 October 2026 (Europe/London). **Source:** [development `40c8719f2f40f1414c3e36202f702b47dd4b6e73`](https://github.com/GOkwori/matchdesk/commit/40c8719f2f40f1414c3e36202f702b47dd4b6e73).

**Result: QUALIFIED for the bounded, read-only synthetic preview.** This is not a production, accessibility, publishing or visual-fidelity sign-off.

## Required exact-source gates

| Gate | Run | Result |
| --- | --- | --- |
| Foundation CI | [38175668508](https://github.com/GOkwori/matchdesk/actions/runs/38175668508) | PASS |
| Foundation integration | [38175668510](https://github.com/GOkwori/matchdesk/actions/runs/38175668510) | PASS |
| Source security | [38175668512](https://github.com/GOkwori/matchdesk/actions/runs/38175668512) | PASS |
| Dependency audit | [38175668515](https://github.com/GOkwori/matchdesk/actions/runs/38175668515) | PASS |

Integration ran **69 Playwright tests; all passed (37.5 seconds)** across desktop, tablet and mobile Chromium. The runtime-browser and native-images jobs both succeeded. It tested screens 05–07 and the previous foundation workbench, synthetic constraints, disabled privileged actions, text/contrast checks and navigation.

Prior candidate `475485cb4510350bbc84a06f9a50a007351ba375` ran 63 passing and three failing browser cases due to an escaped literal backslash-d regex in the computed RGB parser. The correction at `40c8719` fixed only that parser and added the screenshots; **no WCAG threshold was reduced**.

## Actual screenshot evidence

The new integration browser test captured **18 PNGs**: 05 Moments & Timeline, 06 AI Intelligence Workspace and 07 Evidence Verification Explorer, each in dark and light modes at **390, 1024 and 1440 CSS px**. It checked no document-width overflow, proper implemented view heading, synthetic replay notice, no unexpected `/api/` requests and no uncaught page errors.

**GitHub archived artifact:** `integration-38175668510-1`, ID **11716161202**, provider-reported ZIP SHA-256 `852e55e82612f63cdea3085a083932edad559eb56ecc20a3494658f8d52f455b`. Related image security artifact ID **11716041660** and security verdict ID **11715548161** were retained. The browser JSON report, logs and captured images are inside the integration artifact. Review copies of all 18 PNGs were individually SHA-256 indexed and delivered separately; they are *not* original historical design mock-ups or committed GitHub PNG blobs.

## Approved design comparison — still open

- **05:** Accurate chronological event facts and the corner `E-1359` → goal `E-1366` (14 seconds) are shown. The implemented event cards do not yet replicate the approved vertical event timeline treatment, and no x/y coordinates may be invented.
- **06:** Five illustrative stages, separate source facts, pending `CL-0215` and unsupported `CL-0216` are visible. The current composition is cleaner but less visually differentiated than the approved agent-card design. No model or tool actually ran.
- **07:** Claim register, reference verdicts, proof chain and disabled approval are present. For `CL-0214`, source-event operands are absent; the UI correctly states that a design reference verdict is **not** independent runtime verification.
- **Mobile:** Layouts render without page-width overflow. The seven-tab bottom navigation horizontally scrolls; discoverability of further tabs needs a clearer affordance.
- Dark and light tokens follow the approved direction. Owner visual sign-off, device/screen-reader review, non-Chromium browsers, zoom/accessibility and actual performance budgets have **not** been completed.

**Visual disposition:** PARTIALLY MATCHED / owner sign-off pending. Do not imply pixel-level parity from passing browser tests.

## Truth, archive and execution boundaries

Only seven canonical event descriptions are supplied in the fixture; the declared 1,284-event total is not evidence that the rest are generated or verified. CL-0215 remains pending, CL-0216 unsupported, `D-031 v3` ineligible; no customer authentication, editorial approval, publishing, model execution, live match, or database mutation is permitted by this frontend.

The **seven original Batch 1 PNGs remain absent from GitHub**. They were verified externally but the historical 21-image asset archive is not complete. The Sunset Studio v3 design approval does not waive this provenance requirement.

**Next:** controlled timeline and mobile navigation visual refinements, capture/requalify the changed source, independent accessibility/manual design acceptance, then screens 08–14. Production deployment, cost-incurring cloud resources and protected `main` changes remain prohibited without separate approval.
