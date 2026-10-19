/** Custom producer confirmation: accessibility and browser-only no-authority QA.
 *
 * Exercises a deliberately synthetic Sunset Studio sample. Neither this test
 * nor the sample carries an Entra session, CSRF token, producer grant or API
 * mutation. The backend must still revalidate exact CAS and actor authority.
 */
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const PAGE = "/producer/publish/D-031";
const BUTTON = "Preview producer confirmation (demo)";
const MODAL = "Review sample producer decision";

async function openPreview(page) {
  await page.goto(PAGE);
  const trigger = page.getByRole("button", { name: BUTTON });
  await expect(trigger).toBeVisible();
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: MODAL });
  await expect(dialog).toBeVisible();
  return { dialog, trigger };
}

test("Escape, initial safe focus and focus restoration never use native confirm()", async ({ page }) => {
  const { dialog, trigger } = await openPreview(page);
  await expect(dialog.getByRole("button", { name: "Cancel" })).toBeFocused();
  await expect(dialog.getByRole("button", { name: "Confirm reviewed version" })).toBeDisabled();
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
  await expect(trigger).toBeFocused();
  // No modal survives a cancelled review, even after reopening.
  await trigger.click();
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(dialog).not.toBeVisible();
  await expect(trigger).toBeFocused();
});

test("reviewed version and reason are visible; preview never issues a producer command", async ({ page }) => {
  const mutationRequests = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/workforce/producer/")) {
      mutationRequests.push(request.url());
    }
  });
  const { dialog } = await openPreview(page);
  await expect(dialog.getByText("D-031", { exact: true }).first()).toBeVisible();
  await expect(dialog.getByText("DEMO_REPLAY")).toBeVisible();
  await expect(dialog.getByText("1".repeat(64))).toBeVisible();
  await expect(dialog.getByText("2".repeat(64))).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Confirm reviewed version" })).toBeDisabled();
  await dialog.getByRole("textbox", { name: /Reason for decision/ }).fill("  Reviewed sample only  ");
  await expect(dialog.getByRole("button", { name: "Confirm reviewed version" })).toBeEnabled();
  await dialog.getByRole("button", { name: "Confirm reviewed version" }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "Preview acknowledged" })).toBeVisible();
  await expect(page.getByText("No producer command was sent and nothing was approved.")).toBeVisible();
  expect(mutationRequests).toEqual([]);
});

test("modal is accessible and keyboard navigation stays inside it", async ({ page }) => {
  const { dialog } = await openPreview(page);
  await expect(dialog).toHaveAttribute("aria-modal", "true");
  await expect(dialog.getByRole("textbox", { name: /Reason for decision/ })).toBeVisible();
  await page.keyboard.press("Shift+Tab");
  // The dialog's top layer contains focus: an outside navigation link cannot
  // be activated while human confirmation is displayed.
  const trapped = await page.evaluate(() => {
    const active = document.activeElement;
    const modal = document.querySelector("dialog.md-decision-dialog");
    return !!modal && !!active && modal.contains(active);
  });
  expect(trapped).toBe(true);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(results.violations.map((v) => v.id)).toEqual([]);
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
});
