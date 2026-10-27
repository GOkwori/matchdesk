# Sunset Studio - engineering and content guardrails

The 14 mock-ups are approved for visual direction only. They were assessed on 11 October 2026 in a source-grounded implementation readiness review; they have **not** been independently certified as a functioning, secure or WCAG-compliant application.

## Non-negotiable truth and authority boundaries

- Label the match as a **synthetic replay**, never live. The Northbridge FC v Riverside United fixture is invented demonstration data, not a real Premier League match.
- Do not copy unsupported claims from raster illustrations into the product. In particular, avoid presenting fabricated metrics, tracking, video, player locations, season history or evidence.
- Distinguish structurally valid input from factually verified claims; distinguish AI interpretation from proven analytics.
- Claim `CL-0216` has no season evidence, `CL-0217` is not verifiable without defender-position data, and `CL-0215` is pending in the illustrative source story. Do not convert them into verified facts.
- Sample `D-031 v3` is ineligible for approval (2 verified, 1 pending, 1 failed). `D-029 v2` is eligible in the illustrative story but **not approved or published**.
- No front-end control, agent output, role badge, or prompt can authorise a backend action. Every mutation must be independently authenticated, authorised, scoped, version-bound and audited at execution.
- Keep sign-in, privileged review, approval and publication unavailable in the current demo until their corresponding backend/API, actor and policy controls are implemented and tested. Label future-state experiences accurately; approval is never equivalent to publication.

## Known review findings to correct at implementation

- Batch 1 raster screens contain inconsistencies and unsupported tracking-like visual representations. Preserve the approved look, but use vetted source events and truthful SVGs.
- The seven Batch 2 HTML prototypes contain fonts smaller than the 12px secondary minimum. Production should target 14-16px body text, secondary minimum 12px and measured WCAG 2.2 AA contrast in both themes.
- Batch 2 prototypes contain `href="#"` placeholders. Replace with actual allowed routes or remove/disable; do not deploy dead links.
- The seven HTML files are static design sources and MUST NOT be pasted into production unreviewed. Build typed, reusable Next.js/React components, semantic CSS tokens and tested responsive layouts.
- The current default API does not expose producer mutation/publication workflows or public dashboard/fixture projections for all screens. Do not invent success from unsupported routes.
- Custom in-app status banners and dialogs need keyboard, focus trap/restoration, screen-reader announcement, error-recovery and concurrency tests; do not use browser or OS notification APIs.
- Validate 390, 768, 1280 and 1440px layouts, touch targets, reduced motion and no horizontal page scroll; run typecheck, build, browser and security CI on the implementation SHA.

## Scope of this design archive

A design-only documentation commit may add approved prototypes and describe planned interactions. It must not change application routes, enable permissions, add infrastructure, mark tests passed, deploy to Azure or promote `main`.

The historical readiness review was recorded in `IMPLEMENTATION_READINESS.md` in the Microsoft Competition Library on 11 October 2026. Treat its baseline SHA and status as a time-specific observation, not a statement about the current Git branch.
