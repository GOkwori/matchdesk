/** Focus transfer on synthetic client-only screen changes.
 * A view change must expose its new main landmark without privileged API calls,
 * while initial page loads and skip-link navigation remain unchanged.
 * This is a browser regression, not screen-reader conformance evidence.
 */
import { test, expect } from '@playwright/test';

test.describe('Client-only screen focus handoff', () => {
  test('desktop navigation focuses the updated, named main landmark', async ({ page }) => {
    const calls = [];
    page.on('request', request => {
      if (new URL(request.url()).pathname.startsWith('/api/')) calls.push(request.url());
    });
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto('/sunset-v3');
    const main = page.getByRole('main');
    await expect(main).toHaveAttribute('aria-label', 'Welcome & Access');
    await expect(main).not.toBeFocused();

    await page.getByRole('button', { name: 'Overview', exact: true }).click();
    await expect(main).toHaveAttribute('aria-label', 'Intelligence Overview');
    await expect(main).toBeFocused();
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Intelligence Overview');

    await page.getByRole('button', { name: 'Tactical Analysis', exact: true }).click();
    await expect(main).toHaveAttribute('aria-label', 'Tactical Analysis');
    await expect(main).toBeFocused();
    expect(calls, 'Preview navigation must not invoke privileged APIs').toEqual([]);
  });

  test('mobile More selection focuses the new landmark and Escape keeps its opener', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/sunset-v3');
    const main = page.getByRole('main');
    const skip = page.getByRole('link', { name: 'Skip to main content' });
    await page.keyboard.press('Tab');
    await expect(skip).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(main).toBeFocused();

    const more = page.getByRole('navigation', { name: 'Mobile demo navigation' })
      .locator('.mdv3-mobile-more-trigger');
    await more.click();
    await expect(more).toHaveAttribute('aria-expanded', 'true');
    await page.getByRole('region', { name: 'More demo destinations' })
      .locator('.mdv3-mobile-more-options button')
      .filter({ hasText: 'Evidence Verification' }).click();
    await expect(more).toHaveAttribute('aria-expanded', 'false');
    await expect(main).toHaveAttribute('aria-label', 'Evidence Verification');
    await expect(main).toBeFocused();

    await more.click();
    await expect(page.getByRole('region', { name: 'More demo destinations' })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('region', { name: 'More demo destinations' })).toHaveCount(0);
    await expect(more).toBeFocused();
    await expect(main).toHaveAttribute('aria-label', 'Evidence Verification');
  });
  test('navigating from a scrolled mobile screen reveals the new heading', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 540 });
    await page.goto('/sunset-v3');
    const more = page.getByRole('navigation', { name: 'Mobile demo navigation' })
      .locator('.mdv3-mobile-more-trigger');

    await more.click();
    await page.getByRole('region', { name: 'More demo destinations' })
      .locator('.mdv3-mobile-more-options button')
      .filter({ hasText: 'Evidence Verification' }).click();

    // A long evidence screen has content below the visible mobile viewport.
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(150);

    await page.getByRole('navigation', { name: 'Mobile demo navigation' })
      .getByRole('button', { name: /Overview/ }).click();

    const main = page.getByRole('main');
    await expect(main).toHaveAttribute('aria-label', 'Intelligence Overview');
    await expect(main).toBeFocused();
    await expect(page.getByRole('heading', { level: 1, name: 'Intelligence Overview' })).toBeInViewport();
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBeLessThanOrEqual(1);
  });

});
