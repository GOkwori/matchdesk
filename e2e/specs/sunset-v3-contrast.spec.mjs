/** AA token regression for the actual Sunset Studio v3 rendered theme values.
 *
 * The brief's original subtle swatch did not meet 4.5:1 against raised panels.
 * Tests intentionally cover every semantic text/status foreground on the three
 * application surfaces, and an independent 3:1 essential-control outline.
 * Decorative --md-line is not an actionable control-boundary token.
 */
import { test, expect } from '@playwright/test';

/** WCAG luminance for valid CSS #RGB or #RRGGBB tokens, with no weaker threshold. */
function luminance(hex) {
  expect(hex, 'Only explicit hex palette tokens are accepted').toMatch(/^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/);
  const normalized = hex.length === 4
    ? '#' + [...hex.slice(1)].map(channel => channel + channel).join('')
    : hex;
  const channels = [1, 3, 5].map(index => Number.parseInt(normalized.slice(index, index + 2), 16) / 255);
  const linear = channels.map(value =>
    value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  );
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

/** The contrast ratio does not depend on foreground/background order. */
function contrast(first, second) {
  const a = luminance(first), b = luminance(second);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}

test('CSS hex shorthand expands without altering WCAG ratios', () => {
  expect(contrast('#fff', '#000')).toBeCloseTo(21, 8);
  expect(contrast('#fff', '#23303c')).toBeCloseTo(contrast('#ffffff', '#23303c'), 8);
});

test.beforeEach(async ({ page }) => {
  await page.goto('/sunset-v3');
});

test('both themes meet semantic text and control contrast thresholds', async ({ page }) => {
  const textTokens = ['text', 'muted', 'subtle', 'accent', 'accent-soft',
    'success', 'info', 'warn', 'error'];
  const surfaces = ['bg', 'panel', 'raised'];
  const values = [...textTokens, ...surfaces, 'ui-stroke', 'on-accent'];
  for (const theme of ['dark', 'light']) {
    await page.getByLabel('Display theme').selectOption(theme);
    const palette = await page.locator('.mdv3').evaluate((element, names) => {
      const style = window.getComputedStyle(element);
      return Object.fromEntries(names.map(name => [
        name, style.getPropertyValue('--md-' + name).trim(),
      ]));
    }, values);
    for (const surface of surfaces) {
      for (const token of textTokens) {
        expect(
          contrast(palette[token], palette[surface]),
          `${theme}: --md-${token} on --md-${surface} must be at least 4.5:1`
        ).toBeGreaterThanOrEqual(4.5);
      }
      expect(
        contrast(palette['ui-stroke'], palette[surface]),
        `${theme}: control outline against --md-${surface} must be at least 3:1`
      ).toBeGreaterThanOrEqual(3);
    }
    expect(
      contrast(palette['on-accent'], palette.accent),
      `${theme}: text on primary button must reach 4.5:1`
    ).toBeGreaterThanOrEqual(4.5);
  }
});

test('meta labels, state chips and mobile captions remain at least 12px', async ({ page }) => {
  // Keep this selector list tied to the labels actually rendered by the demo.
  const labels = [
    '.mdv3-side-label', '.mdv3-kicker', '.mdv3-nav-tag',
    '.mdv3-top-left > span', '.mdv3-score-mid small', '.mdv3-team small',
    '.mdv3-status', '.mdv3-mobile-nav small', '.mdv3-footer',
  ];
  for (const width of [390, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const selector of labels) {
      const entry = page.locator(selector).first();
      await expect(entry, `Missing label ${selector}`).toHaveCount(1);
      const fontSize = await entry.evaluate(element => Number.parseFloat(getComputedStyle(element).fontSize));
      expect(fontSize, `${selector} at ${width}px must be at least 12px`).toBeGreaterThanOrEqual(12);
    }
  }
  await page.emulateMedia({ forcedColors: 'active' });
  const forcedOutline = await page.locator('.mdv3').evaluate(element =>
    getComputedStyle(element).getPropertyValue('--md-ui-stroke').trim());
  expect(forcedOutline).toBe('CanvasText');
});
