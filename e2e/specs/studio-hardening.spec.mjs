/** Production hardening for the studio: accessibility, SEO, security headers, resilience, offline and performance.
 *
 * Runs against the built application (never a dev server), at the three viewport
 * profiles. Automated checks complement, and never replace, manual screen-reader passes.
 */
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const STORY = '/story/okafor-header-restores-northbridge-lead';
const INDEXABLE = ['/', '/about', '/story', '/story/recap', STORY, '/story/okafor-opens-the-scoring', '/story/lindqvist-equalises-for-riverside', '/match/nbr-riv'];
const WORKSPACE = [
  '/match/nbr-riv/live', '/match/nbr-riv/moments?moment=M-05', '/match/nbr-riv/tactical', '/match/nbr-riv/players', '/match/nbr-riv/player/nbr-09', '/match/nbr-riv/insights',
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
    test.setTimeout(120_000); // a full axe pass over 22 pages; slower runners exceed the 30 s default
    const pages = [...ALL, '/match/nbr-riv?tour=1', '/match/nbr-riv/insights?tour=3', '/producer/compose/D-031?tour=6', '/nope-not-a-page'];
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

  test('heading levels never skip and every page has one h1, one main and labelled navigation', async ({ page }) => {
    for (const route of ALL) {
      await open(page, route);
      // Some pages stream their heading in after hydration; a page with no h1 still fails here.
      await page.locator('h1').first().waitFor();
      const s = await page.evaluate(() => {
        const hs = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter((h) => h.getClientRects().length);
        const levels = hs.map((h) => Number(h.tagName[1]));
        const skips = levels.filter((l, i) => i > 0 && l > levels[i - 1] + 1).length;
        const unlabelled = [...document.querySelectorAll('nav')].filter((n) => !n.getAttribute('aria-label') && !n.getAttribute('aria-labelledby')).length;
        return { h1: levels.filter((l) => l === 1).length, skips, mains: document.querySelectorAll('main').length, unlabelled };
      });
      expect(s, route).toEqual({ h1: 1, skips: 0, mains: 1, unlabelled: 0 });
    }
  });

  test('interactive targets are at least 24 by 24 px, apart from links inside sentences (WCAG 2.5.8)', async ({ page }) => {
    for (const route of ALL) {
      await open(page, route);
      await settle(page); // measure settled boxes, not a panel mid-way through its entrance scale
      const small = await page.evaluate(() => [...document.querySelectorAll('a[href],button,input,select,textarea,summary,[tabindex]:not([tabindex="-1"])')]
        .filter((el) => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden'; })
        .filter((el) => { const r = el.getBoundingClientRect();
          if (r.width >= 24 && r.height >= 24) return false;
          if (el.tagName === 'A' && getComputedStyle(el).display === 'inline') return false; // inline in a sentence
          return el.type !== 'range'; // the slider's thumb, not its track, is the target
        })
        .map((el) => `${el.tagName} "${(el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 30)}"`));
      expect(small, route).toEqual([]);
    }
  });

  test('keyboard focus is always visible and never hidden under a fixed bar (WCAG 2.4.7, 2.4.11)', async ({ page }) => {
    for (const route of ['/match/nbr-riv', '/match/nbr-riv/moments?moment=M-05', '/match/nbr-riv/insights',
      '/match/nbr-riv/evidence/CL-0214', '/producer/compose/D-031', '/workspace/settings']) {
      await open(page, route);
      const seen = new Set();
      const problems = [];
      for (let i = 0; i < 120; i++) {
        await page.keyboard.press('Tab');
        const info = await page.evaluate(() => {
          const el = document.activeElement;
          if (!el || el === document.body) return null;
          const cs = getComputedStyle(el);
          // The range input draws its ring on the thumb, which computed style cannot see.
          const visible = el.type === 'range' || (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) > 0) || cs.boxShadow !== 'none';
          const r = el.getBoundingClientRect();
          const x = Math.min(Math.max(r.left + r.width / 2, 0), innerWidth - 1);
          const y = Math.min(Math.max(r.top + r.height / 2, 0), innerHeight - 1);
          const top = document.elementFromPoint(x, y);
          const covered = !!top && !el.contains(top) && !top.contains(el);
          const id = `${el.tagName}:${(el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 40)}:${Math.round(r.left)},${Math.round(r.top + scrollY)}`;
          return { id, visible, covered };
        });
        if (!info) continue;
        if (seen.has(info.id)) break;
        seen.add(info.id);
        if (!info.visible) problems.push(`no focus indicator: ${info.id}`);
        if (info.covered) problems.push(`hidden under another element: ${info.id}`);
      }
      expect(problems, route).toEqual([]);
    }
  });

  test('with reduced motion requested, nothing keeps animating (WCAG 2.3.3)', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    for (const route of ['/', '/match/nbr-riv', '/match/nbr-riv/insights', STORY]) {
      await open(page, route);
      const moving = await page.evaluate(() => document.getAnimations().filter((a) => {
        const t = a.effect?.getTiming?.();
        return a.playState === 'running' && ((typeof t?.duration === 'number' && t.duration > 200) || t?.iterations === Infinity);
      }).length);
      expect(moving, route).toBe(0);
    }
  });

  test('a guided-tour stop takes focus, and Escape closes it', async ({ page }) => {
    await open(page, '/match/nbr-riv?tour=1');
    const tour = page.getByRole('dialog').filter({ hasText: 'Guided tour · 1 of 7' });
    await expect(tour.getByRole('heading')).toBeFocused();
    await page.keyboard.press('Tab');
    await expect(tour.getByRole('button', { name: 'Skip tour' })).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(tour).toBeHidden();
    await expect(page).not.toHaveURL(/tour=/);
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
    const listed = [...sitemap.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => new URL(m[1]).pathname);
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
    // The event log for the in-browser re-check is warmed in idle time; wait until it is cached.
    await expect.poll(() => page.evaluate(async () => {
      const cache = await caches.open('md-assets');
      for (const request of await cache.keys()) {
        const response = await cache.match(request);
        if (request.url.endsWith('.js') && (await response.text()).includes('E-1420')) return true;
      }
      return false;
    }), { timeout: 15000 }).toBe(true);
    await context.setOffline(true);
    try {
      await page.goto('/match/nbr-riv/evidence/CL-0214');
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
      await expect(page.getByText('1,421 events read from the log')).toBeVisible();
      await expect(page.getByText(/Checked twice: by the server, and again in your browser/)).toBeVisible();
      await expect(page.getByText('You’re offline. The demo keeps working from this device.')).toBeVisible();
      await page.getByRole('button', { name: 'Claim 59% instead' }).click();
      await expect(page.getByText('Failed · needs revision')).toBeVisible();
      await page.goto('/producer/compose/D-031?tour=6');
      await expect(page.getByText('Guided tour · 6 of 7')).toBeVisible();
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
