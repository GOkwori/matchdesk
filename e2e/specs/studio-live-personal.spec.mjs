/** Live replay with timed overlays, personalisation, player focus and control vs chaos.
 *
 * Synthetic, client-side studio routes only. The overlay feed's claims are re-verified in the
 * browser; these tests check that what reaches the screen is what the verifier passed.
 */
import { test, expect } from '@playwright/test';

async function open(page, route) {
  await page.goto(route);
  await page.locator('html[data-md-ready="1"]').waitFor({ state: 'attached' });
}

function watchErrors(page) {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  return errors;
}

test.beforeEach(async ({ page }) => {
  await open(page, '/design-system');
  await page.evaluate(() => { window.localStorage.clear(); window.localStorage.setItem('md.tourDone', '1'); });
});

test('the replay re-verifies every overlay claim and shows the goal cue at its moment', async ({ page }) => {
  const errors = watchErrors(page);
  await open(page, '/match/nbr-riv/live');
  const replay = page.locator('.md-lr');
  await expect(replay.getByText(/13 timed overlays · 26 of 26 claims re-verified here/)).toBeVisible();
  await replay.getByRole('button', { name: 'Goal 58:17' }).click();
  await replay.getByRole('button', { name: '1×' }).click();
  await replay.getByRole('button', { name: 'Play replay' }).click();
  const third = replay.locator('.md-lt');
  await expect(third).toContainText("GOAL! Okafor scores for Northbridge. It's 2–1.", { timeout: 30_000 });
  await expect(third).toContainText('Verified in this browser');
  await expect(replay.locator('.md-bcast-bug')).toContainText('2–1');
  await replay.getByRole('button', { name: 'Pause replay' }).click();
  await replay.getByRole('button', { name: 'Français' }).click();
  await replay.getByRole('button', { name: 'Broadcast caption' }).click();
  await expect(third).toContainText('59′ BUT · Okafor · NBR 2–1 RIV');
  await expect(third).toContainText('Vérifié dans ce navigateur');
  expect(errors).toEqual([]);
});

test('logged cards are marked as logged, not verified', async ({ page }) => {
  await open(page, '/match/nbr-riv/live');
  const replay = page.locator('.md-lr');
  await expect(replay.getByText(/26 of 26 claims/)).toBeVisible();
  const slider = replay.getByRole('slider', { name: 'Match clock' });
  await slider.fill(String((27 * 60 + 41) * 1000));
  await expect(replay.locator('.md-lt')).toContainText('Yellow card');
  await expect(replay.locator('.md-lt')).toContainText('Logged event');
});

test('the overlay feed downloads as machine-readable JSON', async ({ page, request }) => {
  await open(page, '/match/nbr-riv/live');
  await expect(page.getByRole('link', { name: 'Download the overlay feed (JSON)' })).toHaveAttribute('href', '/overlays/nbr-riv.json');
  const feed = await (await request.get('/overlays/nbr-riv.json')).json();
  expect(feed.schema).toBe('matchdesk-overlay-feed/1');
  expect(feed.cues.map((c) => c.t_ms)).toEqual([...feed.cues.map((c) => c.t_ms)].sort((a, b) => a - b));
  for (const cue of feed.cues) for (const persona of ['analyst', 'fan', 'caption']) for (const lang of ['en', 'es', 'fr']) expect(cue.text[persona][lang]).toBeTruthy();
});

test('My match follows the viewer to the overview, the replay and Ask MatchDesk', async ({ page }) => {
  const errors = watchErrors(page);
  await open(page, '/workspace/settings');
  const section = page.locator('#my-match');
  await section.getByLabel('Favourite club').selectOption('riv');
  await section.getByLabel('Favourite player').selectOption('riv-11');
  await section.getByLabel('Focus statistic').selectOption('tackles.v1');
  await section.getByLabel('Overlay language').selectOption('es');
  await open(page, '/match/nbr-riv');
  const card = page.locator('section', { has: page.getByRole('heading', { name: 'Riverside · Lindqvist' }) });
  await expect(card.getByText('Lindqvist scored 1 goal up to 67:12.')).toBeVisible();
  await expect(card.locator('.md-chip-verified')).toHaveCount(3);
  await open(page, '/match/nbr-riv/live');
  const replay = page.locator('.md-lr');
  await expect(replay.getByRole('button', { name: 'Español' })).toHaveAttribute('aria-pressed', 'true');
  await expect(replay.getByRole('row', { name: /Tackles/ })).toBeVisible();
  await replay.getByRole('button', { name: 'Goal 41:03' }).click();
  await expect(replay.locator('.md-lt')).toContainText('Your player');
  await page.getByRole('button', { name: /^Ask/ }).first().click();
  await expect(page.getByRole('button', { name: 'How did Lindqvist play?' })).toBeVisible();
  expect(errors).toEqual([]);
});

test('player focus states verified figures and can set the favourite', async ({ page }) => {
  await open(page, '/match/nbr-riv/players');
  await page.getByRole('link', { name: /Okafor/ }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Okafor' })).toBeVisible();
  await expect(page.getByText('Okafor scored 2 goals up to 67:12.')).toBeVisible();
  await expect(page.getByText('11 of 11 sentences verified')).toBeVisible();
  await page.getByRole('button', { name: '☆ Make Okafor my player' }).click();
  await expect(page.getByRole('button', { name: '★ Okafor is your player' })).toHaveAttribute('aria-pressed', 'true');
  expect(await page.evaluate(() => JSON.parse(window.localStorage.getItem('md.viewer')).player)).toBe('nbr-09');
});

test('control and chaos labels come with verified reasons', async ({ page }) => {
  await open(page, '/match/nbr-riv/tactical');
  const panel = page.locator('.md-control');
  await expect(panel.getByText('Rule, not AI')).toBeVisible();
  await expect(panel.getByText('Chaos: the ball kept changing hands')).toBeVisible();
  await expect(panel.getByText('Riverside in control')).toBeVisible();
  await expect(panel.locator('.md-chip-failed')).toHaveCount(0);
  await expect(panel.getByText('Northbridge made 31 ball recoveries between 45′ and 60′.')).toBeVisible();
});
