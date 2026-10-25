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
  await expect(replay.getByText(/21 timed overlays · 37 of 37 claims re-verified here/)).toBeVisible();
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

test('cards are verified by their registered event fact', async ({ page }) => {
  await open(page, '/match/nbr-riv/live');
  const replay = page.locator('.md-lr');
  await expect(replay.getByText(/37 of 37 claims/)).toBeVisible();
  const slider = replay.getByRole('slider', { name: 'Match clock' });
  await slider.fill(String((27 * 60 + 41) * 1000));
  await expect(replay.locator('.md-lt')).toContainText('Yellow card');
  await expect(replay.locator('.md-lt')).toContainText('Verified in this browser');
  await expect(replay.locator('.md-lt')).not.toContainText('Logged event');
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
  await expect(page.getByText('15 of 15 sentences verified')).toBeVisible();
  await expect(page.getByText('Okafor reached a top speed of 32.3 km/h up to 67:12.')).toBeVisible();
  await expect(page.getByText("Okafor's shot speed was 58.5 km/h up to 67:12.")).toBeVisible();
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

test('every goal has a verified fan story that follows My match', async ({ page }) => {
  const errors = watchErrors(page);
  await open(page, '/story');
  await expect(page.getByRole('link', { name: /Lindqvist equalises for Riverside/ })).toBeVisible();
  await page.evaluate(() => window.localStorage.setItem('md.viewer', JSON.stringify({ club: 'riv', player: 'riv-11', persona: 'fan', language: 'es', focus: 'tackles.v1' })));
  await open(page, '/story/lindqvist-equalises-for-riverside');
  await expect(page.locator('main')).toHaveAttribute('lang', 'es');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('42′ · Lindqvist empata para el Riverside');
  await expect(page.getByText('Tu jugador, Lindqvist, marcó.')).toBeVisible();
  await expect(page.getByText('Comprobado de nuevo en tu navegador')).toBeVisible();
  await expect(page.locator('.md-checks .md-bad')).toHaveCount(0);
  await page.getByRole('button', { name: 'Texto para pantalla' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('42′ GOL · Lindqvist · NBR 1–1 RIV');
  await page.getByRole('link', { name: /Okafor devuelve la ventaja/ }).click();
  await expect(page).toHaveURL(/okafor-header-restores-northbridge-lead$/);
  await expect(page.getByText('Northbridge marcó contra tu club, Riverside.')).toBeVisible();
  await page.goto('/story/okafor-opens-the-scoring?lang=fr');
  await expect(page.locator('main')).toHaveAttribute('lang', 'fr');
  await expect(page.locator('.md-checks').getByText('Interception, puis but 28\u00a0s plus tard')).toBeVisible();
  expect(errors).toEqual([]);
});

test('the match recaps state only verified figures, re-checked here, and follow My match', async ({ page }) => {
  const errors = watchErrors(page);
  await open(page, '/story');
  await page.getByRole('link', { name: /Half-time · Northbridge 1–1 Riverside/ }).click();
  await expect(page).toHaveURL(/\/story\/recap\?at=half-time$/);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Half-time · Northbridge 1–1 Riverside');
  await expect(page.getByText('Checked again in your browser')).toBeVisible();
  await expect(page.locator('.md-checks .md-bad, .md-recap-milestones .md-bad')).toHaveCount(0);
  await expect(page.getByRole('link', { name: /Equaliser · Lindqvist/ })).toHaveAttribute('href', '/story/lindqvist-equalises-for-riverside');
  await page.getByRole('link', { name: 'Recap at 67:12' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('At 67:12 · Northbridge 2–1 Riverside');
  await expect(page.getByText("Okafor's brace")).toBeVisible();
  await page.evaluate(() => window.localStorage.setItem('md.viewer', JSON.stringify({ club: 'riv', player: null, persona: 'analyst', language: 'fr', focus: 'shots.v1' })));
  await open(page, '/story/recap');
  await expect(page.locator('main')).toHaveAttribute('lang', 'fr');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('67:12 · NBR 2–1 RIV');
  await expect(page.getByText('Votre club, Riverside, est mené.')).toBeVisible();
  await expect(page.getByText('Vérifié à nouveau dans votre navigateur')).toBeVisible();
  const feed = await (await page.request.get('/recaps/nbr-riv.json')).json();
  expect(feed.schema).toBe('matchdesk-recap-feed/1');
  expect(feed.claims.every((c) => c.status === 'verified')).toBe(true);
  expect(errors).toEqual([]);
});

test('the replay offers the half-time recap once the first half has been played', async ({ page }) => {
  await open(page, '/match/nbr-riv/live');
  const replay = page.locator('.md-lr');
  await expect(replay.getByText(/claims re-verified here/)).toBeVisible();
  await expect(replay.locator('.md-lr-recap')).toHaveCount(0);
  await replay.getByRole('button', { name: 'Half-time' }).click();
  await expect(replay.locator('.md-lr-recap')).toContainText('Half-time recap · ready');
  await expect(replay.getByRole('link', { name: 'Open the recap' })).toHaveAttribute('href', '/story/recap?at=half-time');
});

test('pressure changes come with the verified counts on both sides', async ({ page }) => {
  await open(page, '/match/nbr-riv/tactical');
  const panel = page.locator('.md-pressure');
  await expect(panel.getByRole('heading', { name: 'Pressure changes' })).toBeVisible();
  await expect(panel.getByText('Pressure rose from 12 to 26 passes under pressure.')).toBeVisible();
  await expect(panel.locator('.md-chip-failed')).toHaveCount(0);
  await expect(panel.getByText('Northbridge played 15 passes under pressure between 45′ and 50′.').first()).toBeVisible();
});

test('tracking thresholds tag the player on the replay, verified', async ({ page }) => {
  await open(page, '/match/nbr-riv/live');
  const replay = page.locator('.md-lr');
  await expect(replay.getByText(/21 timed overlays · 37 of 37 claims re-verified here/)).toBeVisible();
  await replay.getByRole('slider', { name: 'Match clock' }).fill(String(48 * 60_000 + 44_000));
  await expect(replay.locator('.md-lt')).toContainText('Mensah flies at 35.4 km/h');
  await expect(replay.locator('.md-lt .md-chip-verified')).toBeVisible();
  await replay.getByRole('button', { name: 'Goal 58:17' }).click();
  await replay.getByRole('slider', { name: 'Match clock' }).fill(String(58 * 60_000 + 26_000));
  await expect(replay.locator('.md-lt')).toContainText("Okafor's header left at 49.4 km/h");
});

test('the auto-eventing lab shows events read from video, scored against the log', async ({ page }) => {
  await open(page, '/match/nbr-riv/live');
  await page.getByRole('link', { name: /Open the video detection experiment/ }).click();
  await expect(page.getByRole('heading', { level: 1, name: 'Video detection experiment' })).toBeVisible();
  const sources = page.locator('video source');
  await expect(sources).toHaveCount(2);
  expect(await sources.first().getAttribute('src')).toMatch(/auto-eventing.*\.webm$/);
  const webm = await page.request.get(await sources.first().getAttribute('src'));
  expect(webm.ok()).toBe(true);
  await expect(page.getByRole('heading', { name: 'Scored against the log' })).toBeVisible();
  await expect(page.locator('.md-ae-cards li')).toHaveCount(7);
  await expect(page.getByRole('list').filter({ hasText: 'E-1365' }).first()).toBeVisible();
});
