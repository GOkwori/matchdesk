/** Screen 14: browser acceptance for local-only, fail-closed defensive states. */
import { test, expect } from '@playwright/test';

async function openDefensive(page) {
  if (page.viewportSize().width <= 700) {
    await page.getByRole('navigation', { name: 'Mobile demo navigation' })
      .locator('.mdv3-mobile-more-trigger').click();
    await page.getByRole('region', { name: 'More demo destinations' })
      .getByRole('button', { name: 'Defensive States' }).click();
  } else {
    await page.getByRole('button', { name: 'Settings & Help', exact: true }).click();
    await page.getByRole('button', { name: 'Defensive States' }).click();
  }
}

test.beforeEach(async ({ page }) => { await page.goto('/sunset-v3'); });

test('all sixteen safe states are inspectable and privileged recovery stays disabled', async ({ page }) => {
  const api = [];
  const native = [];
  page.on('request', req => { if (new URL(req.url()).pathname.startsWith('/api/')) api.push(req.url()); });
  page.on('dialog', dialog => { native.push(dialog.type()); void dialog.dismiss(); });
  await openDefensive(page);
  await expect(page.getByRole('heading', { name: 'Defensive States' })).toBeVisible();
  const states = page.getByRole('region', { name: 'Defensive interface scenarios' }).locator('.mdv3-defensive-card');
  await expect(states).toHaveCount(16);
  await page.getByRole('button', { name: /Publication ineligible/ }).click();
  await expect(page.getByText('D-031 v3 has a pending claim and a failed claim.').last()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Execute privileged recovery · Unavailable' })).toBeDisabled();
  await expect(page.getByRole('button', { name: /Publication ineligible/ })).toHaveAttribute('aria-pressed', 'true');
  expect(api).toEqual([]);
  expect(native).toEqual([]);
});

test('filter, keyboard focus, and local notes behave without persistence claims', async ({ page }) => {
  await openDefensive(page);
  await page.getByRole('combobox', { name: 'Filter defensive states' }).selectOption('blocked');
  const cards = page.getByRole('region', { name: 'Defensive interface scenarios' }).locator('.mdv3-defensive-card');
  await expect(cards).toHaveCount(6);
  // A newly filtered list must never leave stale detail from a hidden state.
  await expect(cards.first()).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('.mdv3-defensive-inspection')).toContainText('Offline');
  await cards.first().focus();
  await page.keyboard.press('Enter');
  await expect(cards.first()).toHaveAttribute('aria-pressed', 'true');
  const note = page.getByRole('textbox', { name: 'Unsaved local example note' });
  await note.fill('Local-only edit');
  await expect(note).toHaveValue('Local-only edit');
  await page.getByRole('button', { name: 'View notification library' }).click();
  await expect(page.getByRole('heading', { name: 'Notification & Dialogue Library' })).toBeVisible();
  await openDefensive(page);
  await expect(page.getByRole('textbox', { name: 'Unsaved local example note' }))
    .toHaveValue('Local note only — not saved to an account');
});

test('dark and light layouts remain inside viewport', async ({ page }) => {
  await openDefensive(page);
  for (const theme of ['dark', 'light']) {
    await page.getByRole('combobox', { name: 'Display theme' }).selectOption(theme);
    await expect(page.locator('.mdv3')).toHaveAttribute('data-theme', theme);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    // The unsaved two-row example must not create a large empty editor panel.
    const noteHeight = await page.getByRole('textbox', { name: 'Unsaved local example note' })
      .evaluate(element => element.getBoundingClientRect().height);
    expect(noteHeight).toBeGreaterThanOrEqual(72);
    expect(noteHeight).toBeLessThanOrEqual(100);
  }
});
