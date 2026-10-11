/** Browser acceptance for the read-only Sunset Studio v3 screens 01 and 02.
 *
 * The original workbench remains separately tested by workbench.spec.mjs.
 * These tests prohibit pretending that demo fixture state is live verification,
 * authentication, publishing or a privileged producer action.
 */
import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.goto('/sunset-v3');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Turn football');
});

test('welcome identifies a synthetic replay and does not enable real sign-in', async ({ page }) => {
  await expect(page.getByText('Synthetic replay', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: /Sign in.*Planned/ })).toBeDisabled();
  await expect(page.getByRole('heading', { name: 'Detect' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Verify' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Approve' })).toBeVisible();
  await expect(page.getByText(/No tracking data/)).toBeVisible();
  // The nav must not route an unfinished Matches feature to the Welcome page.
  await expect(page.getByRole('button', { name: 'Matches', exact: true })).toHaveCount(0);
});

test('intelligence overview uses approved events and has no privileged API calls', async ({ page }, info) => {
  const apiRequests = [];
  const errors = [];
  page.on('request', request => {
    if (new URL(request.url()).pathname.startsWith('/api/')) apiRequests.push(request.url());
  });
  page.on('pageerror', error => errors.push(error.message));
  await page.getByRole('button', { name: /Explore synthetic demo/ }).click();
  await expect(page.getByRole('heading', { name: 'Intelligence Overview' })).toBeVisible();
  await expect(page.getByText('E-1421', { exact: true })).toBeVisible();
  await expect(page.getByText(/M-05 · E-1366/)).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Match statistics' })).toBeVisible();
  await expect(page.locator('.mdv3-stat')).toHaveCount(7);
  await expect(page.getByRole('button', { name: /Approve.*Planned/ })).toBeDisabled();
  await expect(page.getByText(/Eligible · not approved · not published/)).toBeVisible();
  expect(apiRequests).toEqual([]);
  expect(errors).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await info.attach('sunset-v3-overview', {
    body: await page.screenshot({ fullPage: true }), contentType: 'image/png',
  });
});

test('custom approval-blocked dialog traps and restores keyboard focus', async ({ page }) => {
  await page.getByRole('button', { name: /Explore synthetic demo/ }).click();
  const opener = page.getByRole('button', { name: 'Why is approval blocked?' });
  await opener.click();
  const dialog = page.getByRole('dialog', { name: 'Approval blocked' });
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText('CL-0215');
  await expect(dialog).toContainText('CL-0216');
  const first = dialog.getByRole('button', { name: 'Understood' });
  const last = dialog.getByRole('button', { name: 'Close' });
  await expect(first).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(last).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(first).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
});

test('responsive screens remain usable at mobile, tablet and desktop breakpoints', async ({ page }) => {
  for (const width of [390, 768, 1280, 1440]) {
    await page.setViewportSize({ width, height: width < 800 ? 844 : 1000 });
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  }
  await page.getByLabel('Display theme').selectOption('light');
  await expect(page.locator('.mdv3')).toHaveAttribute('data-theme', 'light');
  await page.getByRole('button', { name: /Explore synthetic demo/ }).click();
  await expect(page.getByRole('heading', { name: 'Intelligence Overview' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});
