/** Sunset Studio v3 screens 03–04: read-only event evidence and absent coordinate regressions. */
import { test, expect } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.goto('/sunset-v3');
});

test('command centre selects only recorded events and binds the corner to the goal', async ({ page }) => {
  const calls = [];
  page.on('request', request => {
    if (new URL(request.url()).pathname.startsWith('/api/')) calls.push(request.url());
  });
  await page.getByRole('button', { name: 'Live Intelligence', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Match Intelligence Command Centre' })).toBeVisible();
  await expect(page.getByRole('group', { name: /Shot-location pitch schematic/ })).toContainText('Coordinates unavailable');
  await expect(page.getByText('14 seconds between events')).toBeVisible();
  await expect(page.getByText('CL-0213 Verified')).toBeVisible();
  await expect(page.getByText('No measured momentum series is supplied.')).toBeVisible();
  const feed = page.getByRole('group', { name: /Recorded synthetic event feed/ });
  await expect(feed.getByRole('button')).toHaveCount(8);
  await feed.getByRole('button', { name: /M-02/ }).click();
  await expect(page.getByRole('heading', { name: 'Okafor opens the scoring' })).toBeVisible();
  expect(calls).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('tactical filters are controlled and never invent event coordinates', async ({ page }) => {
  await page.getByRole('button', { name: 'Tactical Analysis', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Tactical Analysis' })).toBeVisible();
  const pitch = page.getByRole('group', { name: /Event-location pitch schematic/ });
  await expect(pitch).toContainText('Coordinates unavailable');
  await expect(pitch.locator('circle')).toHaveCount(0);
  await expect(page.getByRole('button', { name: /Northbridge corner, right side/ })).toBeVisible();
  await page.getByRole('combobox', { name: 'Team' }).selectOption('RIV');
  await expect(page.getByText('No matching recorded moments')).toBeVisible();
  await page.getByRole('combobox', { name: 'Event group' }).selectOption('goals');
  await expect(page.getByRole('button', { name: /Lindqvist levels for Riverside/ })).toBeVisible();
  await page.getByRole('combobox', { name: 'Event group' }).selectOption('final-third');
  await expect(page.getByText('No final-third pass records')).toBeVisible();
  await page.getByRole('combobox', { name: 'Event group' }).selectOption('shots');
  await expect(page.getByText('Individual shot records and coordinates')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('mobile navigation opens the read-only command and tactical views', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('navigation', { name: 'Mobile demo navigation' })
    .getByRole('button', { name: 'Command' }).click();
  await expect(page.getByRole('heading', { name: 'Match Intelligence Command Centre' })).toBeVisible();
  await page.getByRole('navigation', { name: 'Mobile demo navigation' })
    .getByRole('button', { name: 'Tactical' }).click();
  await expect(page.getByRole('heading', { name: 'Tactical Analysis' })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
