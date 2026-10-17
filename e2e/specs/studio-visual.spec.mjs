/** Visual regression baselines for the locked screens at desktop, tablet and phone sizes. @visual-capture
 *
 * Baselines live in studio-visual.spec.mjs-snapshots/. They were rendered on Linux Chromium
 * with the self-hosted fonts, and compare with a 1% pixel tolerance to absorb sub-pixel
 * antialiasing differences between Chromium builds. After an intended design change,
 * run the suite with --update-snapshots on Linux and commit the images.
 */
import { test, expect } from '@playwright/test';

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
    await expect(page).toHaveScreenshot(`${name}.png`, { animations: 'disabled', caret: 'hide', maxDiffPixelRatio: 0.01 });
  });
}
