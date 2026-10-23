/** Locked Sunset Studio frontend: journeys, deep links, re-verification and responsive shell.
 *
 * These tests exercise the synthetic, client-only studio routes. They never call
 * an approval or publication API; "Approve" must remain a locked, planned control.
 */
import { test, expect } from '@playwright/test';

const STORY = '/story/okafor-header-restores-northbridge-lead';
const ROUTES = ['/', '/about', '/match/nbr-riv', '/match/nbr-riv/live', '/match/nbr-riv/moments', '/match/nbr-riv/tactical', '/match/nbr-riv/players', '/match/nbr-riv/player/riv-11', '/match/nbr-riv/insights', '/match/nbr-riv/evidence/CL-0214', '/producer/queue', '/producer/compose/D-031', '/producer/publish/D-031', '/workspace/activity', '/workspace/settings', STORY, '/design-system'];

/** Static pages are pre-rendered; wait for hydration before interacting. */
async function open(page, route) {
  await page.goto(route);
  await page.locator('html[data-md-ready="1"]').waitFor({ state: 'attached' });
}

/** Fail on any uncaught page error or console error during a test. */
function watchErrors(page) {
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  return errors;
}

test.beforeEach(async ({ page }) => {
  await open(page, '/design-system');
  await page.evaluate(() => window.localStorage.clear());
});

test('every studio route renders without overflow, errors or a missing main heading', async ({ page }) => {
  const errors = watchErrors(page);
  for (const route of ROUTES) {
    await open(page, route);
    await expect(page.getByRole('heading', { level: 1 }).first()).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), route).toBe(true);
    await expect(page).toHaveTitle(/MatchDesk/);
  }
  expect(errors).toEqual([]);
});

test('the site root is the product welcome, and the JSON workbench moved to /dev/workbench', async ({ page }) => {
  await open(page, '/');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Turn football moments into');
  await expect(page.getByRole('link', { name: /Start the 3-minute guided demo/ })).toBeVisible();
  await page.goto('/dev/workbench');
  await expect(page.getByLabel('Edit the JSON and validate its structure')).toBeVisible();
});

test('the guided tour walks all seven stops across real routes', async ({ page }) => {
  await open(page, '/');
  await page.getByRole('link', { name: /Start the 3-minute guided demo/ }).click();
  const expected = [
    ['1 of 7', /\/match\/nbr-riv\?tour=1/, 'Open the goal'],
    ['2 of 7', /moments\?moment=M-05&tour=2/, 'See the agents work'],
    ['3 of 7', /insights\?tour=3/, 'See the proof'],
    ['4 of 7', /evidence\/CL-0214\?tour=4/, 'See the review queue'],
    ['5 of 7', /producer\/queue\?tour=5/, 'Open the composer'],
    ['6 of 7', /compose\/D-031\?tour=6/, 'See what fans get'],
  ];
  for (const [step, url, next] of expected) {
    await expect(page).toHaveURL(url);
    const tour = page.getByRole('dialog', { name: /./ }).filter({ hasText: `Guided tour · ${step}` });
    await expect(tour).toBeVisible();
    await tour.getByRole('link', { name: next }).click();
  }
  await expect(page).toHaveURL(/story\/.*\?tour=7/);
  await expect(page.getByText('Guided tour · 7 of 7')).toBeVisible();
  await page.getByRole('link', { name: /Finish tour/ }).click();
  await expect(page).toHaveURL(/\/$/);
});

test('every tour card opens on screen and clear of the phone tab bar', async ({ page }) => {
  for (const [step, route] of [[1, '/match/nbr-riv?tour=1'], [2, '/match/nbr-riv/moments?moment=M-05&tour=2'], [3, '/match/nbr-riv/insights?tour=3'], [4, '/match/nbr-riv/evidence/CL-0214?tour=4'], [5, '/producer/queue?tour=5'], [6, '/producer/compose/D-031?tour=6']]) {
    await open(page, route);
    const card = page.getByRole('dialog').filter({ hasText: `Guided tour · ${step} of 7` });
    await expect(card).toBeInViewport({ ratio: 1 });
    // The tab bar only exists on phones; elsewhere it is display:none and has no box.
    await expect.poll(() => card.evaluate((el) => {
      const tabs = document.querySelector('nav[aria-label="Primary"]');
      const bar = tabs && tabs.getClientRects().length ? tabs.getBoundingClientRect().top : Infinity;
      return el.getBoundingClientRect().bottom <= bar;
    }), { message: `tour ${step} is not hidden by the tab bar` }).toBe(true);
  }
});

test('browser Back stays inside the app and restores the previous screen', async ({ page }) => {
  await open(page, '/match/nbr-riv');
  await page.getByRole('link', { name: /Fix in composer/ }).click();
  await expect(page).toHaveURL(/\/producer\/compose\/D-031$/);
  await page.goBack();
  await expect(page).toHaveURL(/\/match\/nbr-riv$/);
  await expect(page.getByRole('heading', { name: 'Intelligence Overview' })).toBeVisible();
});

test('the replay slider recomputes the score from recorded goals', async ({ page }) => {
  await open(page, '/match/nbr-riv');
  const score = page.locator('.md-score');
  await expect(score).toHaveAttribute('aria-label', 'Northbridge 2, Riverside 1');
  await page.getByRole('slider', { name: 'Replay time' }).fill(String(42 * 60));
  await expect(score).toHaveAttribute('aria-label', 'Northbridge 1, Riverside 1');
  await page.getByRole('slider', { name: 'Replay time' }).fill('600');
  await expect(score).toHaveAttribute('aria-label', 'Northbridge 0, Riverside 0');
  await expect(page.getByText(/No goals yet at 10:00/)).toBeVisible();
});

test('composer re-verifies live: D-031 becomes eligible only after both blocking claims are resolved', async ({ page }) => {
  await open(page, '/producer/compose/D-031');
  const eligibility = page.getByRole('region', { name: 'Eligibility' });
  await expect(eligibility.getByText('Not eligible')).toBeVisible();
  const submit = page.getByRole('button', { name: /Submit for review/ });
  await expect(submit).toBeDisabled();

  const cards = page.getByRole('list', { name: 'Claims in this draft' });
  await cards.getByRole('listitem').filter({ hasText: 'CL-0216' }).getByRole('button', { name: 'Remove sentence' }).click();
  await expect(eligibility.getByText('Not eligible')).toBeVisible();
  await cards.getByRole('listitem').filter({ hasText: 'CL-0215' }).getByRole('button', { name: 'Mark as opinion' }).click();
  await expect(eligibility.getByText('Not eligible')).toHaveCount(0);
  await expect(eligibility.getByText(/Eligible/)).toBeVisible();
  await expect(page.getByText('In our view, Riverside’s best spell').first()).toBeVisible();
  await expect(submit).toBeEnabled();
  await submit.click();
  await expect(page.getByText('D-031 v4 is with the producer for review.')).toBeVisible();
  await expect(page.getByText('Approve · Planned')).toBeVisible();

  await open(page, '/producer/queue');
  await expect(page.getByRole('link', { name: 'Review' })).toBeVisible();
});

test('every factual sentence in the draft verifies as written, not only its claim', async ({ page }) => {
  await open(page, '/producer/compose/D-031');
  const cards = page.getByRole('list', { name: 'Claims in this draft' });
  for (const id of ['CL-0213', 'CL-0214']) {
    // Re-entering the same words makes the browser re-verify the sentence itself.
    const box = page.getByRole('textbox', { name: `Sentence for ${id}` });
    await box.fill(await box.inputValue());
    await expect(cards.getByRole('listitem').filter({ hasText: id }).getByText('Verified')).toBeVisible();
  }
});

test('editing a sentence re-verifies its words in the browser', async ({ page }) => {
  await open(page, '/producer/compose/D-031');
  const eligibility = page.getByRole('region', { name: 'Eligibility' });
  const cards = page.getByRole('list', { name: 'Claims in this draft' });
  await cards.getByRole('listitem').filter({ hasText: 'CL-0216' }).getByRole('button', { name: 'Remove sentence' }).click();
  await cards.getByRole('listitem').filter({ hasText: 'CL-0215' }).getByRole('button', { name: 'Mark as opinion' }).click();
  await expect(eligibility.getByText(/Eligible/)).toBeVisible();

  const possession = page.getByRole('textbox', { name: 'Sentence for CL-0214' });
  await possession.fill('Northbridge have had 60% of possession at the replay point.');
  const card = cards.getByRole('listitem').filter({ hasText: 'CL-0214' });
  await expect(card.getByText("Sentence doesn't match the claim")).toBeVisible();
  await expect(card.getByText('Claim text states a quantity that differs from its assertion')).toBeVisible();
  await expect(eligibility.getByText('Not eligible')).toBeVisible();

  await possession.fill('Riverside have had 58% of possession at the replay point.');
  await expect(card.getByText('Claim text does not name the asserted subject')).toBeVisible();

  await possession.fill('Northbridge kept 58% of the ball.');
  await expect(card.getByText('Verified')).toBeVisible();
  await expect(eligibility.getByText('Not eligible')).toHaveCount(0);
});

test('the overview lets a first-time visitor try to fool the verifier', async ({ page }) => {
  await open(page, '/match/nbr-riv');
  const panel = page.getByRole('region', { name: /possession/ });
  await expect(panel.getByText(/matches the log/)).toBeVisible();
  await panel.getByRole('button', { name: 'Claim 59% instead' }).click();
  await expect(panel.getByText('Rejected')).toBeVisible();
  await expect(panel.getByText(/57\.96%/)).toBeVisible();
});

test('a forged statistic is recalculated and rejected', async ({ page }) => {
  await open(page, '/match/nbr-riv/evidence/CL-0214');
  await expect(page.getByText('PASS', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Claim 59% instead' }).click();
  await expect(page.getByText('Failed · needs revision')).toBeVisible();
  await expect(page.getByText('FAIL', { exact: true })).toBeVisible();
  await expect(page.getByText(/The log gives 57.96%, which rounds to 58%, not 59%/)).toBeVisible();
});

test('moment deep links select the moment and link to its evidence', async ({ page }) => {
  await open(page, '/match/nbr-riv/moments?moment=M-02');
  await expect(page.getByRole('heading', { name: 'Okafor opens the scoring' })).toBeVisible();
  await page.getByRole('link', { name: /Check the evidence/ }).click();
  await expect(page).toHaveURL(/evidence\/CL-0213$/);
  await expect(page.getByText('2 of 2 goals match')).toBeVisible();
});

test('the fan story switches language without changing the verified facts', async ({ page }) => {
  await open(page, STORY);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('59′ · Okafor restores the Northbridge lead');
  await expect(page.getByText('Checked again in your browser')).toBeVisible();
  await page.getByRole('button', { name: 'Español' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('devuelve la ventaja');
  await expect(page.locator('main')).toHaveAttribute('lang', 'es');
  await expect(page.getByText('58:17').first()).toBeVisible();
  await expect(page.getByText('Momento verificado')).toBeVisible();
  await expect(page.getByRole('img', { name: /^Diagrama de la jugada: ① Córner 58:03/ })).toBeVisible();
  await expect(page.getByText(/Traducción asistida por IA/)).toBeVisible();
  await page.getByRole('button', { name: 'Français' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('redonne');
  await expect(page.getByText('Moment vérifié')).toBeVisible();
  await expect(page.getByText(/Traduction assistée par IA/)).toBeVisible();
  await page.getByRole('button', { name: 'English' }).click();
  await expect(page.getByText(/assisted|Traduc/)).toHaveCount(0);
});

test('Ctrl+K search jumps to a claim by keyboard', async ({ page }) => {
  await open(page, '/match/nbr-riv');
  await page.keyboard.press('Control+k');
  const palette = page.getByRole('dialog', { name: 'Search MatchDesk' });
  await expect(palette).toBeVisible();
  await page.keyboard.type('CL-0216');
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/evidence\/CL-0216$/);
  await expect(palette).toBeHidden();
});

test('returning users can resume where they left off', async ({ page }) => {
  await open(page, '/producer/queue');
  await open(page, '/');
  const resume = page.getByRole('link', { name: /Continue where you left off/ });
  await expect(resume).toContainText('Review queue');
  await resume.click();
  await expect(page).toHaveURL(/\/producer\/queue$/);
});

test('the shell adapts: sidebar on desktop, icon rail on tablet, tab bar on phones', async ({ page }, info) => {
  await open(page, '/match/nbr-riv');
  const tabs = page.getByRole('navigation', { name: 'Primary' });
  const workspace = page.getByRole('navigation', { name: 'Workspace' });
  if (info.project.name === 'mobile') {
    await expect(tabs).toBeVisible();
    await expect(workspace).toBeHidden();
    await expect(tabs.getByRole('link', { name: 'Match' })).toHaveAttribute('aria-current', 'page');
  } else {
    await expect(tabs).toBeHidden();
    await expect(workspace).toBeVisible();
    await expect(workspace.getByRole('link', { name: 'Overview' })).toHaveAttribute('aria-current', 'page');
  }
});

test('evidence figures come from the generated event-log export', async ({ page }) => {
  await open(page, '/match/nbr-riv/evidence/CL-0214');
  await expect(page.getByText('1,421 events read from the log')).toBeVisible();
  await expect(page.getByLabel('Calculation')).toContainText('2,334.5 s / 4,028.0 s');
  await expect(page.getByLabel('Calculation')).toContainText('57.96%  →  58%');
  await expect(page.getByText(/Checked twice: by the server, and again in your browser from 1,421 events/)).toBeVisible();
});

test('tactical filters recount shots from real event locations', async ({ page }) => {
  await open(page, '/match/nbr-riv/tactical');
  await expect(page.getByText('23 shots')).toBeVisible();
  await page.getByRole('group', { name: 'Team' }).getByRole('button', { name: 'Northbridge' }).click();
  await expect(page.getByText('14 shots')).toBeVisible();
  await page.getByRole('group', { name: 'Half' }).getByRole('button', { name: '1st' }).click();
  await expect(page.getByRole('heading', { name: /Shot map · first half/ })).toBeVisible();
});

test('tactical analysis shows passing quality and defending from registered metrics, and asks who led', async ({ page }) => {
  await open(page, '/match/nbr-riv/tactical');
  const panel = page.getByRole('region', { name: 'Passing quality and defending' });
  await expect(panel.getByText('Tackles: Northbridge 33, Riverside 33')).toBeAttached();
  await expect(panel.getByText('Progressive passes: Northbridge 101, Riverside 60')).toBeAttached();
  await expect(panel.getByText(/not from tracking/)).toBeVisible();
  await panel.getByRole('button', { name: 'Ask who led the tackles' }).click();
  const turn = page.getByRole('article', { name: 'Answer to: Who made the most tackles?' });
  await expect(turn.locator('.md-chip-verified')).toHaveCount(3);
  await expect(turn.getByText(/Sorensen made 8 tackles/)).toBeVisible();
});

test('the live run shows first, the rehearsal sends a draft back, and verified claims wait for a human', async ({ page }) => {
  await open(page, '/match/nbr-riv/insights');
  const runs = page.getByRole('group', { name: 'Which run' });
  await expect(runs.getByRole('button', { name: 'Recorded live run' })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByRole('note').filter({ hasText: 'Microsoft Foundry via Agent Framework' })).toBeVisible();
  await expect(page.getByText(/rejected by the claim contract, so the host retried/)).toBeVisible();
  await expect(page.getByText('9 versions of the 58′ story')).toBeVisible();
  await expect(page.getByText(/Words around it, such as praise or emphasis, are tone and are not checked/)).toBeVisible();
  await runs.getByRole('button', { name: 'Rehearsal' }).click();
  await expect(page.getByRole('note').filter({ hasText: 'Rehearsal run' })).toBeVisible();
  await expect(page.getByText('Sent back')).toBeVisible();
  await expect(page.locator('.md-chip').filter({ hasText: 'Passed' })).toBeVisible();
  await expect(page.getByText(/Observed 57\.96%, claimed 60\.00%/)).toBeVisible();
  await expect(page.getByText('3 left to review')).toBeVisible();
  await page.getByRole('button', { name: 'Dismiss' }).first().click();
  await expect(page.getByText('2 left to review')).toBeVisible();
  await page.getByRole('button', { name: 'Undo' }).click();
  await expect(page.getByText('3 left to review')).toBeVisible();
  await page.getByRole('button', { name: 'Replay step by step' }).click();
  await expect(page.getByText(/^Step 1 of \d+$/)).toBeVisible();
  await page.getByRole('button', { name: 'Next step' }).click();
  await expect(page.getByText(/^Step 2 of \d+$/)).toBeVisible();
});

test('publication journey reflects the composer fix and keeps approval locked', async ({ page }) => {
  await open(page, '/producer/publish/D-031');
  await expect(page.getByRole('link', { name: /Make D-031 eligible/ })).toBeVisible();
  await open(page, '/producer/compose/D-031');
  const cards = page.getByRole('list', { name: 'Claims in this draft' });
  await cards.getByRole('listitem').filter({ hasText: 'CL-0216' }).getByRole('button', { name: 'Remove sentence' }).click();
  await cards.getByRole('listitem').filter({ hasText: 'CL-0215' }).getByRole('button', { name: 'Mark as opinion' }).click();
  await open(page, '/producer/publish/D-031');
  await expect(page.getByText(/Approve · Planned: a signed-in producer approves/)).toBeVisible();
  await open(page, '/workspace/activity');
  await expect(page.getByText('Re-verified D-031 v4')).toBeVisible();
});

test('display preferences persist and apply to the whole document', async ({ page }) => {
  await open(page, '/workspace/settings');
  await page.getByRole('switch', { name: /Reduce motion/ }).check();
  await expect(page.locator('html')).toHaveAttribute('data-md-motion', 'reduce');
  await open(page, '/match/nbr-riv');
  await expect(page.locator('html')).toHaveAttribute('data-md-motion', 'reduce');
  await open(page, '/workspace/settings');
  await page.getByRole('button', { name: 'Reset demo data' }).click();
  await expect(page.getByText(/D-031 is back to v3/)).toBeVisible();
});
