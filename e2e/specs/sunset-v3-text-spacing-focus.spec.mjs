/**
 * Sunset Studio v3: automated, deliberately partial WCAG 2.2 accessibility
 * probes for text-spacing overrides (SC 1.4.12) and focused controls hidden by
 * fixed mobile navigation (SC 2.4.11). The tests do not emulate a screen reader
 * or certify real browser zoom or complete WCAG conformance.
 *
 * Use actual DOM and browser Tab behaviour; do not mask scroll overflow, change
 * application routes, invoke privileged APIs or suppress failing results.
 */
import { test, expect } from '@playwright/test';

const destinations = [
  'Welcome & Access',
  'Intelligence Overview',
  'Match Intelligence',
  'Moments & Timeline',
  'Tactical Analysis',
  'AI Intelligence Workspace',
  'Evidence Verification',
  'Producer Review Queue',
  'Story & Commentary Composer',
  'Review & Publication Journey',
  'Audience Experience',
  'Activity, Audit & Settings',
  'Notification & Dialogue Library',
  'Defensive States',
];

/**
 * User stylesheet values from the W3C explanation of WCAG SC 1.4.12:
 * 1.5x line height, 2x paragraph spacing, 0.12em character spacing and
 * 0.16em word spacing. No other visual or layout property is overridden.
 */
const userTextSpacing = [
  '.mdv3, .mdv3 * {',
  '  line-height: 1.5 !important;',
  '  letter-spacing: 0.12em !important;',
  '  word-spacing: 0.16em !important;',
  '}',
  '.mdv3 p { margin-bottom: 2em !important; }',
].join('\n');

async function openDestination(page, label) {
  const more = page.getByRole('navigation', { name: 'Mobile demo navigation' })
    .locator('.mdv3-mobile-more-trigger');
  await more.click();
  const panel = page.getByRole('region', { name: 'More demo destinations' });
  await panel.locator('.mdv3-mobile-more-options button').filter({ hasText: label }).click();
  await expect(panel).toHaveCount(0);
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
}

/**
 * Detect document-level horizontal scrolling and obvious text clipped by
 * overflow:hidden/clip. Tables intentionally scrolling inside their own
 * container are not document-level overflow, and manual inspection still
 * decides whether every piece of text is readable and unobscured.
 */
async function inspectTextSpacing(page) {
  return page.evaluate(() => {
    const viewport = window.innerWidth;
    const clipped = [...document.querySelectorAll('.mdv3 *')]
      .filter(element => {
        const style = window.getComputedStyle(element);
        const hasOwnText = [...element.childNodes].some(node =>
          node.nodeType === Node.TEXT_NODE && Boolean(node.textContent?.trim())
        );
        if (!hasOwnText || element.clientWidth < 1 || element.clientHeight < 1) return false;
        const clipsHorizontally = ['hidden', 'clip'].includes(style.overflowX)
          && element.scrollWidth > element.clientWidth + 2;
        const clipsVertically = ['hidden', 'clip'].includes(style.overflowY)
          && element.scrollHeight > element.clientHeight + 2;
        return clipsHorizontally || clipsVertically;
      })
      .slice(0, 6)
      .map(element => ({
        tag: element.tagName.toLowerCase(),
        className: typeof element.className === 'string' ? element.className.slice(0, 70) : '',
        text: (element.textContent ?? '').trim().slice(0, 65),
        client: [element.clientWidth, element.clientHeight],
        scroll: [element.scrollWidth, element.scrollHeight],
      }));

    return {
      viewport,
      scrollWidth: Math.max(
        document.documentElement.scrollWidth,
        document.body?.scrollWidth ?? 0
      ),
      clipped,
    };
  });
}

/** Find a control by real sequential browser Tab events; never focus it from JS. */
async function tabUntilFocused(page, locator, limit = 140) {
  for (let step = 0; step <= limit; step += 1) {
    const focused = await locator.evaluate(element => document.activeElement === element);
    if (focused) return;
    if (step < limit) await page.keyboard.press('Tab');
  }
  throw new Error('Keyboard-only navigation could not reach the requested control');
}

/** A focused control is not wholly hidden if at least one sampled interior
 * point is visible and is not covered by the fixed mobile navigation.
 */
async function hasUnobscuredFocusedArea(locator) {
  return locator.evaluate(element => {
    if (document.activeElement !== element) return false;
    const rect = element.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const xs = [.2, .5, .8];
    const ys = [.2, .5, .8];
    return xs.some(px => ys.some(py => {
      const x = rect.left + px * rect.width;
      const y = rect.top + py * rect.height;
      if (x < 0 || y < 0 || x >= viewportWidth || y >= viewportHeight) return false;
      const hit = document.elementFromPoint(x, y);
      return hit === element || Boolean(hit && element.contains(hit));
    }));
  });
}

test.describe('Text spacing and unobscured focus (automated subset)', () => {
  for (const label of destinations) {
    test('user text-spacing override, both themes and mobile widths: ' + label, async ({ page }, testInfo) => {
      test.skip(testInfo.project.name !== 'desktop', 'One Chromium project owns the extra spacing matrix.');
      await page.setViewportSize({ width: 320, height: 820 });
      await page.goto('/sunset-v3');
      await openDestination(page, label);
      await page.addStyleTag({ content: userTextSpacing });

      for (const width of [320, 390]) {
        await page.setViewportSize({ width, height: 820 });
        for (const theme of ['dark', 'light']) {
          await page.getByRole('combobox', { name: 'Display theme' }).selectOption(theme);
          await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
          const result = await inspectTextSpacing(page);
          expect(result.scrollWidth,
            label + ' / ' + theme + ' / ' + width + 'px: document horizontal overflow: ' +
            JSON.stringify(result)
          ).toBeLessThanOrEqual(result.viewport);
          expect(result.clipped,
            label + ' / ' + theme + ' / ' + width + 'px: text clipping suspects'
          ).toEqual([]);
        }
      }
    });
  }

  for (const width of [320, 390]) {
    for (const theme of ['dark', 'light']) {
      test('keyboard focus not obscured by mobile bar: ' + width + 'px ' + theme, async ({ page }, testInfo) => {
        test.skip(testInfo.project.name !== 'desktop', 'One Chromium project owns the extra keyboard focus tests.');
        await page.setViewportSize({ width, height: 540 });
        await page.goto('/sunset-v3');
        await openDestination(page, 'Notification & Dialogue Library');
        await page.getByRole('combobox', { name: 'Display theme' }).selectOption(theme);

        const control = page.getByRole('button', { name: 'Try local discard' });
        await tabUntilFocused(page, control);
        await expect(control).toBeFocused();
        await expect.poll(
          () => hasUnobscuredFocusedArea(control),
          { message: 'Fixed bottom navigation must not completely cover the focused action' }
        ).toBe(true);
      });
    }
  }
});
