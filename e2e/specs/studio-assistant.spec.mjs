/** Ask MatchDesk in the built studio: verified answers, guidance, model plans and accessibility. */
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

async function openAsk(page, route = '/match/nbr-riv') {
  await page.goto(route);
  await page.locator('html[data-md-ready="1"]').waitFor({ state: 'attached' });
  const button = page.getByRole('button', { name: 'Ask MatchDesk a question' }).filter({ visible: true }).first();
  await button.click();
  const dialog = page.getByRole('dialog', { name: 'Ask MatchDesk' });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText('Loading the event log…')).toHaveCount(0);
  return { dialog, button };
}

async function ask(dialog, question) {
  await dialog.getByLabel('Your question').fill(question);
  await dialog.getByRole('button', { name: 'Ask', exact: true }).click();
  const turn = dialog.getByRole('article', { name: `Answer to: ${question}` });
  await expect(turn).toBeVisible();
  return turn;
}

test('answers the score with two verified figures and a derived conclusion', async ({ page }) => {
  const { dialog } = await openAsk(page);
  const turn = await ask(dialog, "What's the score?");
  await expect(turn.getByText('Northbridge scored 2 goals up to 67:12.')).toBeVisible();
  await expect(turn.getByText('Riverside scored 1 goal up to 67:12.')).toBeVisible();
  await expect(turn.locator('.md-chip-verified')).toHaveCount(2);
  await expect(turn.getByText(/Northbridge lead 2–1\./)).toBeVisible();
  await turn.getByText('How this was checked').first().click();
  await expect(turn.getByText('goals.v1', { exact: false }).first()).toBeVisible();
  await expect(turn.getByText('E-0688, E-1366')).toBeVisible();
});

test('suggested questions answer in place, and the scorers are event checks', async ({ page }) => {
  const { dialog } = await openAsk(page, '/producer/queue');
  await dialog.getByRole('button', { name: 'Who scored?' }).click();
  const turn = dialog.getByRole('article', { name: 'Answer to: Who scored?' });
  await expect(turn.locator('.md-ask-line')).toHaveCount(3);
  await expect(turn.locator('.md-chip-verified')).toHaveCount(3);
  await expect(turn.getByText('Lindqvist scored for Riverside at 41:03.')).toBeVisible();
});

test('guidance links go to the right screen and close the panel', async ({ page }) => {
  const { dialog } = await openAsk(page);
  const turn = await ask(dialog, 'How do I approve a draft?');
  await turn.getByRole('link', { name: 'Open publication' }).click();
  await expect(page).toHaveURL(/\/producer\/publish\/D-031$/);
  await expect(dialog).toBeHidden();
});

test('without a planner service, an unreadable question gets an honest reply', async ({ page }) => {
  await page.route('**/api/assistant/plan', (route) => route.fulfill({ status: 404, body: 'not found' }));
  const { dialog } = await openAsk(page);
  const turn = await ask(dialog, 'Was it a good game for neutrals?');
  await expect(turn.getByText(/I couldn't read that question/)).toBeVisible();
  await expect(turn.locator('.md-chip')).toHaveCount(0);
});

test('a plan from the model is answered by the engine, and a malformed plan is ignored', async ({ page }) => {
  let calls = 0;
  await page.route('**/api/assistant/plan', async (route) => {
    calls += 1;
    const { question } = route.request().postDataJSON();
    const plan = question.includes('fizzle')
      ? { intent: 'metric', metric: 'shots.v1', subjects: ['riv'], window: { period: 2 } }
      : { intent: 'metric', metric: 'shots.v1', subjects: ['riv'], window: {}, text: 'Riverside had 99 shots' };
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ plan }) });
  });
  const { dialog } = await openAsk(page);
  const good = await ask(dialog, 'Did the side in stripes fizzle out late on?');
  await expect(good.getByText('Question read by Azure AI Foundry as: shots · Riverside · second half')).toBeVisible();
  await expect(good.getByText(/^Riverside had \d+ shots? in the second half so far\.$/)).toBeVisible();
  await expect(good.locator('.md-chip-verified')).toHaveCount(1);
  const bad = await ask(dialog, 'Make something up for me');
  await expect(bad.getByText(/I couldn't read that question/)).toBeVisible();
  await expect(bad.getByText('99')).toHaveCount(0);
  expect(calls).toBe(2);
});

test('declines predictions and other clubs', async ({ page }) => {
  const { dialog } = await openAsk(page);
  await expect((await ask(dialog, 'Who will win?')).getByText(/I don't predict results/)).toBeVisible();
  await expect((await ask(dialog, 'How are Arsenal doing?')).getByText(/only know this synthetic match/)).toBeVisible();
});

test('the open panel and its answers have no WCAG 2.2 AA violations', async ({ page }) => {
  const { dialog } = await openAsk(page);
  let result = await new AxeBuilder({ page }).include('.md-ask').withTags(TAGS).analyze();
  expect(result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(', ')}`)).toEqual([]);
  await ask(dialog, 'Who had more shots in the second half?');
  await ask(dialog, 'What does Eligible mean?');
  await dialog.getByText('How this was checked').first().click();
  result = await new AxeBuilder({ page }).include('.md-ask').withTags(TAGS).analyze();
  expect(result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target).join(', ')}`)).toEqual([]);
});

test('keyboard: focus starts in the field, Escape closes, focus returns to the Ask button', async ({ page }) => {
  const { dialog, button } = await openAsk(page);
  await expect(dialog.getByLabel('Your question')).toBeFocused();
  await page.keyboard.type('Northbridge possession');
  await page.keyboard.press('Enter');
  await expect(dialog.getByText('Northbridge had 58% possession up to 67:12.')).toBeVisible();
  await expect(dialog.getByRole('log', { name: 'Answers' })).toHaveAttribute('aria-live', 'polite');
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  await expect(button).toBeFocused();
});

test('the landing page offers the assistant too', async ({ page }) => {
  const { dialog } = await openAsk(page, '/');
  const turn = await ask(dialog, 'start the tour');
  await turn.getByRole('link', { name: 'Start the tour' }).click();
  await expect(page).toHaveURL(/\/match\/nbr-riv\?tour=1$/);
});

test('a windowed score is stated honestly, and unknown players are declined', async ({ page }) => {
  const { dialog } = await openAsk(page);
  await expect((await ask(dialog, 'What was the score after 40 minutes?')).getByText(/Northbridge led 1–0\./)).toBeVisible();
  await expect((await ask(dialog, "What's the score in the second half?")).getByText(/This is not the score\./)).toBeVisible();
  const stranger = await ask(dialog, 'How many shots did Fernandes take?');
  await expect(stranger.getByText(/no player called Fernandes/)).toBeVisible();
  await expect(stranger.locator('.md-chip')).toHaveCount(0);
});

test('jumping elsewhere with the search palette closes the assistant', async ({ page }) => {
  const { dialog } = await openAsk(page);
  await page.keyboard.press('Control+k');
  const palette = page.getByRole('dialog', { name: 'Search MatchDesk' });
  await expect(palette).toBeVisible();
  await page.keyboard.type('Review queue');
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/\/producer\/queue$/);
  await expect(dialog).toBeHidden();
});
