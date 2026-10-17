/** Production hardening for the studio: accessibility, SEO, security headers, resilience, offline and performance.
 *
 * Runs against the built application (never a dev server), at the three viewport
 * profiles. Automated checks complement, and never replace, manual screen-reader passes.
 */
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const STORY = '/story/okafor-header-restores-northbridge-lead';
const INDEXABLE = ['/', '/about', STORY, '/match/nbr-riv'];
const WORKSPACE = [
  '/match/nbr-riv/live', '/match/nbr-riv/moments?moment=M-05', '/match/nbr-riv/tactical', '/match/nbr-riv/insights',
  '/match/nbr-riv/evidence/CL-0213', '/match/nbr-riv/evidence/CL-0214', '/match/nbr-riv/evidence/CL-0215', '/match/nbr-riv/evidence/CL-0216',
  '/producer/queue', '/producer/compose/D-031', '/producer/publish/D-031', '/workspace/activity', '/workspace/settings', '/design-system',
];
const ALL = [...INDEXABLE, ...WORKSPACE];

/** Entrance animations fade panels in; audit the settled page, not a mid-fade frame. */
async function settle(page) {
  await page.locator('html[data-md-ready="1"]').waitFor({ state: 'attached' });
  await page.evaluate(async () => {
    // Saved preferences apply just after hydration; let that frame start any transition first.
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    await Promise.all(document.getAnimations().map((a) => a.finished.catch(() => undefined)));
  });
}

async function open(page, route) {
  const response = await page.goto(route);
  await page.locator('html[data-md-ready="1"]').waitFor({ state: 'attached' });
  return response;
}

test.describe('accessibility', () => {
  test('every studio page has zero WCAG 2.2 AA violations, including the tour and the forged-value state', async ({ page }) => {
    const pages = [...ALL, '/match/nbr-riv?tour=1', '/producer/compose/D-031?tour=5', '/nope-not-a-page'];
    for (const route of pages) {
      await page.goto(route);
      await page.locator('h1').first().waitFor();
      await settle(page);
      const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa']).analyze();
      expect(result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(', ')}`), route).toEqual([]);
    }
    await open(page, '/match/nbr-riv/evidence/CL-0214');
    await page.getByRole('button', { name: 'Claim 59% instead' }).click();
    await settle(page);
    const forged = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze();
    expect(forged.violations.map((v) => v.id)).toEqual([]);
  });

  test('content reflows at 320 px with no horizontal scrolling', async ({ page }, info) => {
    test.skip(info.project.name !== 'mobile', 'Reflow is a narrow-viewport check');
    await page.setViewportSize({ width: 320, height: 640 });
    for (const route of ALL) {
      await open(page, route);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), route).toBe(true);
    }
  });

  test('the first Tab lands on a working skip link on every page', async ({ page }) => {
    for (const route of ['/', '/about', '/match/nbr-riv', '/producer/compose/D-031', STORY, '/no-such-page']) {
      await page.goto(route);
      await page.locator('h1').first().waitFor();
      await page.keyboard.press('Tab');
      const skip = page.getByRole('link', { name: 'Skip to main content' });
      await expect(skip).toBeFocused();
      await page.keyboard.press('Enter');
      await expect(page.locator('#main')).toBeFocused();
    }
  });
});

test.describe('search and sharing', () => {
  test('indexable pages carry a unique title, description, canonical URL, social card and en-GB language', async ({ page }) => {
    const titles = new Set();
    for (const route of INDEXABLE) {
      await open(page, route);
      const title = await page.title();
      expect(titles.has(title), `duplicate title ${title}`).toBe(false);
      titles.add(title);
      await expect(page.locator('html')).toHaveAttribute('lang', 'en-GB');
      expect((await page.locator('meta[name="description"]').getAttribute('content'))?.length ?? 0).toBeGreaterThan(50);
      await expect(page.locator('link[rel="canonical"]')).toHaveAttribute('href', new RegExp(`${route === '/' ? '' : route}/?$`));
      await expect(page.locator('meta[property="og:image"]')).toHaveAttribute('content', /opengraph-image/);
      expect(await page.locator('meta[name="robots"][content*="noindex"]').count(), route).toBe(0);
    }
  });

  test('workspace, producer and developer pages are noindex', async ({ page }) => {
    for (const route of [...WORKSPACE, '/dev/workbench']) {
      await page.goto(route);
      await expect(page.locator('meta[name="robots"]'), route).toHaveAttribute('content', /noindex/);
    }
  });

  test('robots.txt, the sitemap, the manifest and structured data are served', async ({ request, page }) => {
    const robots = await (await request.get('/robots.txt')).text();
    expect(robots).toContain('Disallow: /producer/');
    expect(robots).toContain('Disallow: /dev/');
    expect(robots).toMatch(/Sitemap: .*\/sitemap\.xml/);
    const sitemap = await (await request.get('/sitemap.xml')).text();
    const listed = [...sitemap.matchAll(/<loc>[^<]*?\/\/[^/]+(\/[^<]*)<\/loc>/g)].map((m) => m[1]);
    expect(listed.sort()).toEqual([...INDEXABLE].sort());
    const manifest = await (await request.get('/manifest.webmanifest')).json();
    expect(manifest).toMatchObject({ name: 'MatchDesk', display: 'standalone', start_url: '/' });
    for (const icon of manifest.icons) expect((await request.get(icon.src)).ok(), icon.src).toBe(true);
    await open(page, '/');
    const jsonLd = JSON.parse(await page.locator('script[type="application/ld+json"]').textContent());
    expect(jsonLd.map((d) => d['@type'])).toEqual(['WebSite', 'SoftwareApplication']);
    expect(JSON.stringify(jsonLd)).not.toContain('SportsEvent');
  });

  test('social cards render as 1200 x 630 PNGs', async ({ page, request }) => {
    for (const route of ['/', STORY]) {
      await open(page, route);
      const url = new URL(await page.locator('meta[property="og:image"]').getAttribute('content'));
      const image = await request.get(url.pathname + url.search);
      expect(image.headers()['content-type']).toBe('image/png');
      const body = await image.body();
      expect([body.readUInt32BE(16), body.readUInt32BE(20)]).toEqual([1200, 630]);
    }
  });
});

test.describe('security', () => {
  test('pages send strict security headers and a CSP without unsafe-eval', async ({ request }) => {
    for (const route of ['/', '/producer/compose/D-031', STORY]) {
      const headers = (await request.get(route)).headers();
      const csp = headers['content-security-policy'];
      expect(csp, route).toContain("default-src 'self'");
      expect(csp).toContain("frame-ancestors 'none'");
      expect(csp).toContain("object-src 'none'");
      expect(csp).not.toContain('unsafe-eval');
      expect(headers['x-content-type-options']).toBe('nosniff');
      expect(headers['referrer-policy']).toBe('strict-origin-when-cross-origin');
      expect(headers['strict-transport-security']).toContain('max-age=');
      expect(headers['permissions-policy']).toContain('camera=()');
      expect(headers['x-powered-by']).toBeUndefined();
    }
  });

  test('the page runs with the CSP enforced and no violations', async ({ page }) => {
    const violations = [];
    page.on('console', (m) => { if (/Content Security Policy/i.test(m.text())) violations.push(m.text()); });
    for (const route of ['/', '/match/nbr-riv', '/producer/compose/D-031', STORY]) await open(page, route);
    expect(violations).toEqual([]);
  });
});

test.describe('resilience', () => {
  test('an unknown address gets a styled 404 with ways back in', async ({ page }) => {
    const response = await page.goto('/this/page/does-not-exist');
    expect(response.status()).toBe(404);
    await expect(page.getByRole('heading', { level: 1, name: 'That page isn’t in the match log' })).toBeVisible();
    await expect(page).toHaveTitle(/Page not found/);
    await page.getByRole('link', { name: 'Match overview' }).click();
    await expect(page).toHaveURL(/\/match\/nbr-riv$/);
  });

  test('the demo keeps working with no connection after one online visit', async ({ page, context }) => {
    await open(page, '/');
    await page.evaluate(async () => {
      const registration = await navigator.serviceWorker.ready;
      if (!navigator.serviceWorker.controller) await new Promise((r) => navigator.serviceWorker.addEventListener('controllerchange', r, { once: true }));
      return registration.active?.state;
    });
    await context.setOffline(true);
    try {
      await page.goto('/match/nbr-riv/evidence/CL-0214');
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      await expect(page.getByText('1,421 events read from the log')).toBeVisible();
      await expect(page.getByText('You’re offline. The demo keeps working from this device.')).toBeVisible();
      await page.getByRole('button', { name: 'Claim 59% instead' }).click();
      await expect(page.getByText('Failed · needs revision')).toBeVisible();
      await page.goto('/producer/compose/D-031?tour=5');
      await expect(page.getByText('Guided tour · 5 of 6')).toBeVisible();
      await page.goto(STORY);
      await expect(page.getByRole('heading', { level: 1 })).toContainText('Northbridge');
    } finally {
      await context.setOffline(false);
    }
  });
});

test.describe('performance', () => {
  test('key pages render fast with no layout shift', async ({ page }, info) => {
    test.skip(info.project.name === 'tablet', 'Desktop and phone bracket the range');
    for (const route of ['/', '/match/nbr-riv', STORY]) {
      await open(page, route);
      const vitals = await page.evaluate(() => new Promise((resolve) => {
        let cls = 0;
        let lcp = 0;
        new PerformanceObserver((list) => { for (const e of list.getEntries()) if (!e.hadRecentInput) cls += e.value; }).observe({ type: 'layout-shift', buffered: true });
        new PerformanceObserver((list) => { const last = list.getEntries().at(-1); if (last) lcp = last.startTime; }).observe({ type: 'largest-contentful-paint', buffered: true });
        setTimeout(() => resolve({ cls, lcp }), 600);
      }));
      expect(vitals.cls, `${route} CLS`).toBeLessThan(0.05);
      expect(vitals.lcp, `${route} LCP`).toBeLessThan(2500);
    }
  });
});
