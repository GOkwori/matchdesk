# Frontend hardening (17 October 2026)

This note records the production hardening of the Sunset Studio frontend and the deliberate deviations from the [frontend implementation brief](../design/briefs/locked-design-implementation-brief.md).

## What was removed

| Route | Why |
|---|---|
| `/sunset-v3` | The original 14-screen single-route preview. It is fully superseded by the routed studio (`/`, `/match/nbr-riv/...`, `/producer/...`, `/story/...`). Its 15 browser specs were removed with it; the studio specs cover the same journeys. |
| `/producer` (legacy) | An unlinked, untested developer read-out of `/api/producer/preview`. It clashed with the real `/producer/queue` and was not part of any journey. The API endpoint is unchanged. |

`/dev/workbench` stays: it is the one page the integration suite uses to prove the browser reaches the real API. It is `noindex, nofollow`, blocked in `robots.txt` and not linked from the product.

## What was added

- **Offline demo.** `/sw.js` is generated at build time from the [route registry](../../apps/web/src/studio/site.ts). On first visit it caches every studio page plus the scripts, styles and fonts they reference. Pages are network-first (fresh online, cached offline); hashed assets are cache-first; `/api` is never cached. A polite notice appears when the connection drops.
- **Search and sharing.** `sitemap.xml` (indexable pages only), `robots.txt`, `manifest.webmanifest`, canonical URLs, Open Graph and Twitter tags, 1200×630 social cards in the brand font, and `WebSite` + `SoftwareApplication` JSON-LD. The synthetic match is deliberately not marked up as a real `SportsEvent`. Workspace, producer, design-system and developer pages are `noindex`.
- **Security headers** (production builds): Content-Security-Policy without `unsafe-eval`, HSTS, `nosniff`, `strict-origin-when-cross-origin`, a restrictive Permissions-Policy, `frame-ancestors 'none'` / `X-Frame-Options: DENY`, and COOP.
- **Resilience.** A route-level error boundary with a reference ID and Retry (inside the shell, so navigation survives), a styled 404 for any unknown address, and skeleton loading for app screens.
- **Accessibility.** Skip links on the About page, the fan story and the 404 page.

## Quality gates

| Gate | Where | Threshold |
|---|---|---|
| Per-page JS / CSS budget | CI `web` job: [check_web_budget.mjs](../../scripts/check_web_budget.mjs) | ≤ 170 KB JS and ≤ 40 KB CSS gzip per page (legacy `nomodule` polyfills excluded) |
| axe WCAG 2.2 AA | Integration browser suite: `studio-hardening.spec.mjs` | 0 violations on every page, the tour, the forged-value state and the 404, at 1440 / 820 / 390 px |
| Reflow, skip links | Same spec | No horizontal scroll at 320 px; first Tab reaches a working skip link |
| SEO and sharing | Same spec | Unique titles, descriptions, canonicals, social cards; noindex where required; sitemap equals the indexable set |
| Security headers | Same spec | Headers present, no `unsafe-eval`, no CSP violations in the console |
| Offline | Same spec | Evidence, composer tour and fan story load and work with the network off |
| Web vitals | Same spec | CLS < 0.05 and LCP < 2.5 s in the CI browser |
| Visual regression | `studio-visual.spec.mjs` (`@visual-capture`) | Overview, evidence, composer, fan story and design system within 6% of their baselines at three sizes (see below) |

Visual baselines were rendered on Linux with an older Chromium build than CI's; CI measured 2–4% of pixels differing, all text antialiasing. The comparison therefore allows 6%, which still fails on a moved panel, a missing section or a colour change. **One-time tightening:** download the integration artifact from a CI run, copy the `*-actual.png` files from `browser-visual-results/` over the baselines, and lower `MAX_DIFF` to 1%. Refresh them the same way after an intended design change.

## Deviations, stated plainly

1. **`script-src 'unsafe-inline'`.** Next.js streams its route payload in inline scripts on statically prerendered pages. A nonce would force every page to render dynamically and defeat the offline cache. `unsafe-eval` is not allowed.
2. **Lighthouse is measured, not gated.** Adding Lighthouse to CI means a large new dependency tree. CI instead enforces the bundle budget, axe, SEO checks and real-browser web vitals. A local Lighthouse 13.5 mobile run (simulated slow 4G, 4× CPU) on the production build scored **Accessibility 100, Best Practices 100 and SEO 100** on all four public pages. **Performance** ranged from **93–99** (welcome) and **84–96** (about) to **81–92** (overview and fan story); the gap to 95 is main-thread time hydrating React on a throttled phone. Closing it means moving more of each screen to server components.
3. **The TypeScript verifier port** shipped after this note was written; see the resolved decision below.

## Resolved: what "58% possession" means

The backend verifier compared with exact `eq`, so "58% possession" failed against the log's 57.96%, while the frontend passed it with a ±0.5-point tolerance. Both sides now use one rule: **a claim is checked at the precision it is stated at**. The verifier rounds the recomputed value half up to that precision, so 57.96% verifies "58%" and a forged 59% is rejected. The frontend shows the backend's own verdicts and re-checks the claim in the browser with a TypeScript port that CI holds to exact parity. See [verification design](../solution-design/07-verification.md).

## Deployment setting

Set `MATCHDESK_SITE_URL` (for example `https://matchdesk.example`) at **build** time, as an environment variable or the Docker build argument, so canonical URLs, the sitemap and social cards point at the public address. It defaults to `http://localhost:3000`.
