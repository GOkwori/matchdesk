/**
 * Sunset Studio v3 accessibility Phase 2: observable keyboard behaviour and
 * narrow-viewport reflow. These checks are not assistive-technology testing
 * and do not constitute WCAG 2.2 AA certification.
 *
 * A 320 CSS-pixel viewport probes the reference reflow width for SC 1.4.10.
 * It is not a substitute for verifying real 200%/400% browser zoom.
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
 * Traverse the browser's actual sequential Tab order rather than invoking a
 * click on a simulated keyboard target. The finite bound fails closed when a
 * control cannot be reached by Tab.
 */
async function tabTo(page, target, maximumTabs = 120) {
  for (let index = 0; index <= maximumTabs; index += 1) {
    if (await target.evaluate(element => document.activeElement === element)) {
      return;
    }
    if (index < maximumTabs) await page.keyboard.press('Tab');
  }
  throw new Error('Control was not reachable through Tab within ' + maximumTabs + ' steps');
}

/**
 * Select an implemented synthetic screen using only Tab and Enter. The More
 * panel deliberately exposes all fourteen screens at narrow widths.
 */
async function selectDestinationByKeyboard(page, label) {
  const more = page.getByRole('navigation', { name: 'Mobile demo navigation' })
    .locator('.mdv3-mobile-more-trigger');
  await tabTo(page, more);
  await page.keyboard.press('Enter');
  await expect(more).toHaveAttribute('aria-expanded', 'true');

  const menu = page.getByRole('region', { name: 'More demo destinations' });
  await expect(menu).toBeVisible();
  const option = menu.locator('.mdv3-mobile-more-options button').filter({ hasText: label });
  await expect(option).toHaveCount(1);
  await tabTo(page, option, 20);
  await page.keyboard.press('Enter');

  await expect(menu).toHaveCount(0);
  await expect(more).toHaveAttribute('aria-expanded', 'false');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
}

/** Click only for reflow setup; keyboard activation is audited separately. */
async function selectDestinationForReflow(page, label) {
  await page.getByRole('navigation', { name: 'Mobile demo navigation' })
    .locator('.mdv3-mobile-more-trigger').click();
  const menu = page.getByRole('region', { name: 'More demo destinations' });
  await menu.locator('.mdv3-mobile-more-options button').filter({ hasText: label }).click();
  await expect(menu).toHaveCount(0);
}

/** Report overflowing nodes in failure messages without hiding actual overflow. */
async function inspectDocumentWidth(page) {
  return page.evaluate(() => {
    const viewport = window.innerWidth;
    const offenders = [...document.querySelectorAll('.mdv3 *')]
      .filter(element => {
        const box = element.getBoundingClientRect();
        const style = window.getComputedStyle(element);
        return box.width > 0 && box.right > viewport + 1 &&
          !['fixed', 'absolute'].includes(style.position);
      })
      .slice(0, 6)
      .map(element => ({
        tag: element.tagName.toLowerCase(),
        className: typeof element.className === 'string' ? element.className.slice(0, 100) : '',
        right: Math.round(element.getBoundingClientRect().right),
      }));
    return {
      viewport,
      documentWidth: document.documentElement.scrollWidth,
      offenders,
    };
  });
}

test.describe('Keyboard and reflow qualification (automated subset)', () => {
  test('skip navigation, mobile destination selection and Escape use real keys', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'desktop', 'One Chromium project owns the extra accessibility checks.');
    await page.setViewportSize({ width: 390, height: 844 });
    const apiCalls = [];
    page.on('request', request => {
      if (new URL(request.url()).pathname.startsWith('/api/')) apiCalls.push(request.url());
    });
    await page.goto('/sunset-v3');

    const skip = page.getByRole('link', { name: 'Skip to main content' });
    await page.keyboard.press('Tab');
    await expect(skip).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.getByRole('main')).toBeFocused();

    await selectDestinationByKeyboard(page, 'Evidence Verification');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Evidence Verification Explorer');

    const more = page.getByRole('navigation', { name: 'Mobile demo navigation' })
      .locator('.mdv3-mobile-more-trigger');
    await tabTo(page, more);
    await page.keyboard.press('Enter');
    await expect(page.getByRole('region', { name: 'More demo destinations' })).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.getByRole('region', { name: 'More demo destinations' })).toHaveCount(0);
    await expect(more).toBeFocused();
    expect(apiCalls, 'Synthetic navigation must never call a privileged API').toEqual([]);
  });

  test('keyboard-only discard dialogue restores focus without privileged side effects', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'desktop', 'One Chromium project owns the extra accessibility checks.');
    await page.setViewportSize({ width: 390, height: 844 });
    const nativeDialogs = [], apiCalls = [];
    page.on('dialog', dialogue => { nativeDialogs.push(dialogue.type()); void dialogue.dismiss(); });
    page.on('request', request => {
      if (new URL(request.url()).pathname.startsWith('/api/')) apiCalls.push(request.url());
    });
    await page.goto('/sunset-v3');
    await selectDestinationByKeyboard(page, 'Notification & Dialogue Library');

    const opener = page.getByRole('button', { name: 'Try local discard' });
    await tabTo(page, opener);
    await page.keyboard.press('Enter');
    const modal = page.getByRole('dialog', { name: 'Discard changes?' });
    await expect(modal).toBeVisible();
    await expect(modal.getByRole('textbox', { name: 'Local example edit' })).toBeFocused();
    await page.keyboard.press('Shift+Tab');
    await expect(modal.getByRole('button', { name: 'Discard local example' })).toBeFocused();
    await page.keyboard.press('Escape');
    await expect(modal).toHaveCount(0);
    await expect(opener).toBeFocused();
    expect(nativeDialogs, 'System/browser dialogs must not be used').toEqual([]);
    expect(apiCalls, 'Only local in-memory changes are allowed').toEqual([]);
  });

  test('mobile More options expose measurable pointer targets', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'desktop', 'One Chromium project owns the extra accessibility checks.');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/sunset-v3');
    const more = page.getByRole('navigation', { name: 'Mobile demo navigation' })
      .locator('.mdv3-mobile-more-trigger');
    await more.click();
    const options = page.getByRole('region', { name: 'More demo destinations' })
      .locator('.mdv3-mobile-more-options button');
    await expect(options).toHaveCount(14);

    // These particular large, standalone controls have no spacing exception:
    // require >=24x24 CSS pixels as a useful subset of WCAG 2.2 SC 2.5.8.
    const targets = await options.evaluateAll(elements => elements.map(element => {
      const rect = element.getBoundingClientRect();
      return { label: element.textContent.trim(), width: rect.width, height: rect.height };
    }));
    for (const target of targets) {
      expect(target.width, target.label + ': interactive width').toBeGreaterThanOrEqual(24);
      expect(target.height, target.label + ': interactive height').toBeGreaterThanOrEqual(24);
    }
  });

  for (const label of destinations) {
    test('320px reflow in both themes: ' + label, async ({ page }, testInfo) => {
      test.skip(testInfo.project.name !== 'desktop', 'One browser project audits the full screen/theme matrix.');
      await page.setViewportSize({ width: 320, height: 820 });
      await page.goto('/sunset-v3');
      await selectDestinationForReflow(page, label);

      for (const theme of ['dark', 'light']) {
        await page.getByRole('combobox', { name: 'Display theme' }).selectOption(theme);
        await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
        const measure = await inspectDocumentWidth(page);
        expect(
          measure.documentWidth,
          label + ' / ' + theme + ': document must reflow at 320px; ' +
          JSON.stringify(measure.offenders)
        ).toBeLessThanOrEqual(measure.viewport);
      }
    });
  }
});
