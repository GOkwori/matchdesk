/** Visual regression baselines for the locked screens at desktop, tablet and phone sizes. @visual-capture
 *
 * Baselines live in studio-visual.spec.mjs-snapshots/. They were rendered on Linux with an
 * older Chromium build than CI's, which antialiases text differently (2-4% of pixels, measured
 * in CI). MAX_DIFF therefore allows 6%: enough to absorb glyph edges, not a moved panel, a
 * missing section or a colour change. To tighten it to 1%, replace the baselines with the
 * `*-actual.png` files from a CI run's integration artifact (browser-visual-results/) and
 * lower MAX_DIFF. After an intended design change, refresh the baselines the same way.
 */
import { test, expect } from '@playwright/test';

const MAX_DIFF = 0.06;

const SCREENS = [
  ['overview', '/match/nbr-riv'],
  ['evidence', '/match/nbr-riv/evidence/CL-0214'],
  ['composer', '/producer/compose/D-031'],
  ['fan-story', '/story/okafor-header-restores-northbridge-lead'],
  ['design-system', '/design-system'],
];

for (const [name, route] of SCREENS) {
  test(`${name} matches its approved baseline @visual-capture`, async ({ page }) => {
    await page.goto(route);
    await page.locator('html[data-md-ready="1"]').waitFor({ state: 'attached' });
    await page.evaluate(() => document.fonts.ready);
    await expect(page).toHaveScreenshot(`${name}.png`, { animations: 'disabled', caret: 'hide', maxDiffPixelRatio: MAX_DIFF });
  });
}
