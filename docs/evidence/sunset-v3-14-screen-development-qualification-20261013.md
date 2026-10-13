# Sunset Studio v3 — 14-screen development qualification

**Evidence date:** 13 October 2026 (UTC).
**Qualified source:** `4039ccb214ff999290a826df4e4a185718e65be4` on `development`.
**Scope:** synthetic-only, read-only Next.js frontend at `/sunset-v3`.
**Result:** CI-QUALIFIED FOR THIS DEMO SCOPE; NOT production-ready or independently WCAG-certified.

## Integration and review history

- Owner approved Screen 13 on 13 October 2026. PR #46 squash-merged at `4348ddd59811b7ddaf8f732ae55ba58bd7f32230`.
- First Screen 13 development integration run [38381919328](https://github.com/GOkwori/matchdesk/actions/runs/38381919328) FAILED due to Chromium Page.captureScreenshot error in Workbench before backend assertions; 206/207 browser tests passed.
- PR #47 isolated functional from visual Playwright processes, retaining zero retries and both evidence streams. Squash-merged at `a96faa15e47380200915f0551d373751efcf3b51`; all four post-merge gates passed.
- Owner approved Screen 14 on 13 October 2026. PR #48 included 16 labelled defensive-state examples, disabled privileged recovery, mobile viewport checks, compact local note and filter-selection consistency. Squash-merged at `4039ccb214ff999290a826df4e4a185718e65be4`.

## Exact post-merge qualification on development

| Workflow | Run ID | Conclusion |
| --- | --- | --- |
| [Foundation CI](https://github.com/GOkwori/matchdesk/actions/runs/38429583258) | 38429583258 | PASS |
| [Foundation integration](https://github.com/GOkwori/matchdesk/actions/runs/38429583212) | 38429583212 | PASS |
| [Source security](https://github.com/GOkwori/matchdesk/actions/runs/38429583220) | 38429583220 | PASS |
| [Dependency audit](https://github.com/GOkwori/matchdesk/actions/runs/38429583268) | 38429583268 | PASS |

Integration passed both runtime-browser and native-images jobs, with 213 functional and 3 visual-capture Playwright tests passing (216/216; no retries).

Evidence retained under run 38429583212, attempt 1:
- `integration-38429583212-1` (artifact 11830551292)
- `image-security-38429583212-1` (artifact 11829299860)
- `image-security-verdict-38429583212-1` (artifact 11829439507)

Three viewport profiles, both themes, and a separate mobile viewport screenshot for Screen 14 form review evidence, not independent pixel-parity certification.

## Outstanding gates — no waivers

1. Seven exact original Batch 1 PNGs, `image-gen-1(1).png` to `image-gen-7(1).png`, still require byte-for-byte import and a verified 21-image asset manifest. The 14 original Batch 2 PNGs are archived. Never substitute crops or regenerated images.
2. Independent/manual WCAG 2.2 AA validation, assistive-technology/focus checks, contrast and responsive auditing remain outstanding. CI does not establish WCAG certification.
3. Real actor/tenant authentication, granular action authorization, production session policies, producer writes, approvals, publication and audience delivery require separate secure backend and human governance gates.
4. UAT, live target provenance, operator review, recovery, monitoring, cost controls, production deployment approval and promotion to `main` remain separate and unapproved.

This evidence is tied to the specified development SHA. A later code or documentation commit must earn its own qualifying checks. No live permissions, billable resources or deployment are authorized.
