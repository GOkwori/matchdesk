/** Screens 05–07: data truthfulness, navigation and non-execution acceptance. */
import { test, expect } from '@playwright/test';

async function openScreen(page, desktop, mobile) {
  if (page.viewportSize()?.width < 640) {
    await page.getByRole('navigation', { name: 'Mobile demo navigation' })
      .getByRole('button', { name: mobile }).click();
  } else {
    await page.getByRole('button', { name: desktop, exact: true }).click();
  }
}

test.beforeEach(async ({ page }) => { await page.goto('/sunset-v3'); });

test('moment timeline uses exactly seven named events and deterministic corner explanation', async ({ page }) => {
  await openScreen(page, 'Moments & Timeline', 'Moments');
  await expect(page.getByRole('heading', { name: 'Moments & Timeline' })).toBeVisible();
  const timeline = page.getByRole('list', { name: 'Seven canonical moments' });
  await expect(timeline.getByRole('button')).toHaveCount(7);
  await expect(page.getByText('14 seconds between the named events')).toBeVisible();
  await page.getByRole('combobox', { name: 'Timeline event type' }).selectOption('goals');
  await expect(timeline.getByRole('button')).toHaveCount(3);
  await timeline.getByRole('button', { name: /M-02/ }).click();
  await expect(page.getByRole('region', { name: 'Selected synthetic moment details' })).toContainText('E-0688');
  await page.getByRole('button', { name: /Inspect claim evidence/ }).click();
  await expect(page.getByRole('heading', { name: 'Evidence Verification Explorer' })).toBeVisible();
});

test('AI workspace never sends an action and retry is explicitly local', async ({ page }) => {
  const requests = [];
  page.on('request', req => {
    if (new URL(req.url()).pathname.startsWith('/api/')) requests.push(req.url());
  });
  await openScreen(page, 'AI Intelligence Workspace', 'AI Desk');
  await expect(page.getByRole('heading', { name: 'AI Intelligence Workspace' })).toBeVisible();
  await expect(page.getByRole('list', { name: 'Illustrative AI workflow' }).locator('li')).toHaveCount(5);
  await expect(page.getByRole('button', { name: /Run agent.*Approve/ })).toBeDisabled();
  await page.getByRole('button', { name: 'Try again (demo)' }).click();
  await expect(page.getByText('Retry request not sent.')).toBeVisible();
  expect(requests).toEqual([]);
});

test('evidence explorer distinguishes fixture verdicts from runtime verification', async ({ page }) => {
  await openScreen(page, 'Evidence & Verification', 'Evidence');
  await expect(page.getByRole('heading', { name: 'Evidence Verification Explorer' })).toBeVisible();
  await expect(page.locator('.mdv3-claims-table tbody tr')).toHaveCount(4);
  const detail = page.getByRole('region', { name: 'Selected claim evidence details' });
  await expect(detail).toContainText('Source events are unavailable');
  await expect(detail).toContainText('Not independently evaluated in this preview');
  await page.getByRole('button', { name: 'Inspect CL-0216' }).click();
  await expect(detail).toContainText('season history');
  await expect(page.getByRole('button', { name: /Approve or publish/ })).toBeDisabled();
});

test('new screens retain responsive page width and accessible mobile navigation', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const label of ['Moments', 'AI Desk', 'Evidence']) {
    await openScreen(page, '', label);
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  }
});
