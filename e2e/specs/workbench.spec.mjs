/** Browser regressions against the actual built API; controlled faults are named explicitly. */
import { test, expect } from '@playwright/test';

const endpoint = '**/api/contracts/event/validate';

/** Wait for the real validation response before reading the rendered state. */
async function submit(page, status = 200) {
  const response = page.waitForResponse((item) => item.url().endsWith('/api/contracts/event/validate') && item.request().method() === 'POST');
  await page.getByRole('button', { name: 'Validate event', exact: true }).click();
  expect((await response).status()).toBe(status);
}

/** Reuse the labelled control so keyboard and accessible names remain tested. */
function input(page) {
  return page.getByLabel('Edit the JSON and validate its structure');
}

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await expect(input(page)).toBeVisible();
});

test('real backend acceptance is not represented as evidence verification', async ({ page }, info) => {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await info.attach('initial-view', { body: await page.screenshot({ fullPage: true }), contentType: 'image/png' });
  await submit(page);
  await expect(page.getByRole('heading', { name: 'Structure accepted' })).toBeVisible();
  await expect(page.getByText('Not evidence verified.', { exact: false })).toBeVisible();
  await expect(page.locator('code')).toHaveText(/^[0-9a-f]{64}$/);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  expect(errors).toEqual([]);
  await info.attach('accepted-view', { body: await page.screenshot({ fullPage: true }), contentType: 'image/png' });
});

test('invalid synthetic flag is rejected by the real HTTP boundary', async ({ page }) => {
  const event = JSON.parse(await input(page).inputValue());
  await input(page).fill(JSON.stringify({ ...event, synthetic: 1 }));
  await submit(page, 422);
  await expect(page.getByRole('alert')).toContainText('HTTP 422');
  await expect(page.getByRole('heading', { name: 'Structure accepted' })).toHaveCount(0);
});

test('malformed JSON is rejected locally without an HTTP mutation', async ({ page }) => {
  let posts = 0;
  page.on('request', (request) => {
    if (request.url().endsWith('/api/contracts/event/validate') && request.method() === 'POST') posts += 1;
  });
  await input(page).fill('{malformed');
  await page.getByRole('button', { name: 'Validate event', exact: true }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  expect(posts).toBe(0);
});

test('oversized JSON is rejected through the standalone proxy', async ({ page }) => {
  const event = JSON.parse(await input(page).inputValue());
  await input(page).fill(JSON.stringify({ ...event, unexpected: 'x'.repeat(70000) }));
  await submit(page, 413);
  await expect(page.getByRole('alert')).toContainText('HTTP 413');
});

test('controlled network fault clears after retry against the real API', async ({ page }) => {
  // Deliberately abort this one transport request; this is not an observed backend outage.
  await page.route(endpoint, (route) => route.abort('failed'));
  await page.getByRole('button', { name: 'Validate event', exact: true }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await page.unroute(endpoint);
  await submit(page);
  await expect(page.getByRole('heading', { name: 'Structure accepted' })).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('controlled untrusted response cannot claim evidence verification', async ({ page }) => {
  // A synthetic transport fixture tests the runtime response guard, not the backend verifier.
  await page.route(endpoint, (route) => route.fulfill({ status: 200, contentType: 'application/json',
    body: JSON.stringify({ event_id: 'fixture', structurally_valid: true, evidence_verified: true, content_digest: 'a'.repeat(64) }) }));
  await submit(page);
  await expect(page.getByRole('alert')).toContainText('unexpected response contract');
  await expect(page.getByRole('heading', { name: 'Structure accepted' })).toHaveCount(0);
});

test('an edited input cannot inherit acceptance from an older in-flight request', async ({ page }) => {
  const newer = { ...JSON.parse(await input(page).inputValue()), event_id: 'm001-newer-input' };
  let release;
  let arrived;
  const delivery = new Promise((resolve) => { release = resolve; });
  const intercepted = new Promise((resolve) => { arrived = resolve; });
  // Fetch the actual API response, but delay delivery to reproduce the input race deterministically.
  await page.route(endpoint, async (route) => {
    const response = await route.fetch();
    arrived();
    await delivery;
    await route.fulfill({ response });
  });
  try {
    await page.getByRole('button', { name: 'Validate event', exact: true }).click();
    await intercepted;
    await input(page).fill(JSON.stringify(newer));
  } finally {
    release();
  }
  await expect(page.getByRole('button', { name: 'Validate event', exact: true })).toBeEnabled();
  await expect(page.getByRole('heading', { name: 'Structure accepted' })).toHaveCount(0);
  await page.unroute(endpoint);
  await submit(page);
  await expect(page.getByText('m001-newer-input', { exact: true })).toBeVisible();
});

test('keyboard submission reaches the same verified structural boundary', async ({ page }) => {
  await input(page).focus();
  await page.keyboard.press('Tab');
  const button = page.getByRole('button', { name: 'Validate event', exact: true });
  await expect(button).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', { name: 'Structure accepted' })).toBeVisible();
});
