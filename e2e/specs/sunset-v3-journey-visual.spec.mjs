/** Read-only visual acceptance captures for Sunset Studio v3 screens 05–08.
 *
 * Captures are review evidence, never automatic proof of mock-up equivalence
 * or WCAG compliance. Use one browser project and explicitly set all three
 * baseline viewport widths to avoid wasteful duplicate screenshot archives.
 */
import { test, expect } from '@playwright/test';

const screenCases = [
  {
    id: '05-moments',
    heading: 'Moments & Timeline',
    desktop: 'Moments & Timeline',
    mobile: 'Moments',
  },
  {
    id: '06-ai-workspace',
    heading: 'AI Intelligence Workspace',
    desktop: 'AI Intelligence Workspace',
    mobile: 'AI Desk',
  },
  {
    id: '07-evidence',
    heading: 'Evidence Verification Explorer',
    desktop: 'Evidence & Verification',
    mobile: 'Evidence',
  },
  {
    id: '08-producer',
    heading: 'Producer Review Queue',
    desktop: 'Producer Desk',
    mobile: 'Producer Review Queue',
  },
];

test('capture screens 05–08 in both themes at 390, 1024 and 1440 pixels', async ({ page }, testInfo) => {
  // Run once in each existing browser project; avoid screenshot duplication.
  const viewportByProject = {
    desktop: { width: 1440, height: 1000 },
    tablet: { width: 1024, height: 1000 },
    mobile: { width: 390, height: 844 },
  };
  const viewport = viewportByProject[testInfo.project.name];
  expect(viewport, 'An unknown browser project must not silently skip captures').toBeTruthy();
  const { width } = viewport;
  await page.setViewportSize(viewport);

  const outboundApiCalls = [];
  const browserErrors = [];
  page.on('request', request => {
    if (new URL(request.url()).pathname.startsWith('/api/')) outboundApiCalls.push(request.url());
  });
  page.on('pageerror', error => browserErrors.push(error.message));

  for (const theme of ['dark', 'light']) {
      await page.goto('/sunset-v3');
      await page.getByLabel('Display theme').selectOption(theme);
      await expect(page.locator('.mdv3')).toHaveAttribute('data-theme', theme);

      for (const screen of screenCases) {
        if (width === 390 && screen.id === '08-producer') {
          // Screen 08 is reached through the deliberately discoverable mobile More panel.
          await page.getByRole('navigation', { name: 'Mobile demo navigation' })
            .locator('.mdv3-mobile-more-trigger').click();
          await page.getByRole('region', { name: 'More demo destinations' })
            .getByRole('button', { name: /Producer Review Queue/ }).click();
        } else if (width === 390) {
          await page.getByRole('navigation', { name: 'Mobile demo navigation' })
            .getByRole('button', { name: screen.mobile }).click();
        } else {
          await page.getByRole('button', { name: screen.desktop, exact: true }).click();
        }
        await expect(page.getByRole('heading', { level: 1, name: screen.heading })).toBeVisible();
        if (screen.id === '08-producer') {
          await expect(page.getByRole('button', { name: 'Approve · Unavailable' })).toBeDisabled();
        }
        await expect(page.getByText(/Synthetic replay/i).first()).toBeVisible();
        expect(
          await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
          `Document must not horizontally overflow on ${screen.id} at ${width}px`
        ).toBe(true);
        await testInfo.attach(`sunset-v3-${screen.id}-${theme}-${width}px`, {
          body: await page.screenshot({ fullPage: true }),
          contentType: 'image/png',
        });
      }
  }

  expect(outboundApiCalls, 'Synthetic screens must not call privileged APIs').toEqual([]);
  expect(browserErrors, 'Synthetic screens must not throw browser errors').toEqual([]);
});
