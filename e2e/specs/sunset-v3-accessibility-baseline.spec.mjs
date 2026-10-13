/** Preliminary WCAG 2.2 AA audit probes for all fourteen synthetic screens.
 *
 * These browser checks cover only measurable DOM/navigation properties.
 * They do NOT certify screen-reader behaviour, focus order, visual equivalence
 * or complete WCAG conformance. Manual and independent review stays required.
 */
import { test, expect } from '@playwright/test';

const destinations = [
  'Welcome & Access', 'Intelligence Overview', 'Match Intelligence',
  'Moments & Timeline', 'Tactical Analysis', 'AI Intelligence Workspace',
  'Evidence Verification', 'Producer Review Queue',
  'Story & Commentary Composer', 'Review & Publication Journey',
  'Audience Experience', 'Activity, Audit & Settings',
  'Notification & Dialogue Library', 'Defensive States',
];

/** Open the actual client-only destination from the labelled mobile menu. */
async function visitDestination(page, label) {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/sunset-v3');
  const navigation = page.getByRole('navigation', { name: 'Mobile demo navigation' });
  await navigation.locator('.mdv3-mobile-more-trigger').click();
  // Destination buttons also contain a visible “Open” / “Current” suffix.
  // Target the unique labelled option without relying on a truncated
  // accessible name or hiding the actual UI text from assistive technology.
  await page.getByRole('region', { name: 'More demo destinations' })
    .locator('.mdv3-mobile-more-options button').filter({ hasText: label }).click();
}

/** Only one Chromium project performs the multi-width cross-screen audit. */
test.describe('Cross-screen accessibility baseline', () => {
  test.skip(({ }, info) => info.project.name !== 'desktop', 'One browser project explicitly tests all target widths.');

  for (const label of destinations) {
    test(`${label}: landmark, heading, keyboard skip link, responsive reflow`, async ({ page }) => {
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      await visitDestination(page, label);
      await expect(page.getByRole('main')).toHaveCount(1);
      await expect(page.getByRole('heading', { level: 1 })).toHaveCount(1);
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible();

      // A focus-only skip link must become visible through keyboard access.
      const skip = page.getByRole('link', { name: 'Skip to main content' });
      await expect(skip).not.toBeInViewport();
      await skip.focus();
      await expect(skip).toBeFocused();
      await expect(skip).toBeInViewport();
      await page.keyboard.press('Enter');
      await expect(page.locator('#mdv3-main')).toBeFocused();

      for (const theme of ['dark', 'light']) {
        await page.getByRole('combobox', { name: 'Display theme' }).selectOption(theme);
        for (const width of [390, 768, 1280, 1440]) {
          await page.setViewportSize({ width, height: 900 });
          await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
          expect(await page.evaluate(() =>
            document.documentElement.scrollWidth <= window.innerWidth
          ), `${label}, ${theme}, ${width}px: horizontal scroll`).toBe(true);
        }
      }
      expect(errors).toEqual([]);
    });
  }
});
