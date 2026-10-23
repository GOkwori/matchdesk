/** Demo producer approval: accessible confirmation, exact-version binding and no network command.
 *
 * The demo approval runs only in the browser: no Entra session, CSRF token, producer grant or
 * API mutation. A production host must still revalidate exact CAS and actor authority.
 */
import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

const PAGE = "/producer/publish/D-031";
const BUTTON = "Approve this version";
const MODAL = "Approve D-031, this exact version";
const ELIGIBLE = JSON.stringify({ states: { "CL-0215": "opinion", "CL-0216": "removed" }, texts: {}, failedEdits: [], headline: "Okafor double restores Northbridge lead", submitted: true });

async function openPreview(page) {
  await page.goto(PAGE);
  await page.evaluate((doc) => { window.localStorage.setItem("md.d031", doc); window.localStorage.removeItem("md.d031.approval"); }, ELIGIBLE);
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

test("the approval binds this exact version, sends nothing, and an edit withdraws it", async ({ page }) => {
  const apiRequests = [];
  page.on("request", (request) => {
    if (new URL(request.url()).pathname.startsWith("/api/")) apiRequests.push(request.url());
  });
  const { dialog } = await openPreview(page);
  await expect(dialog.getByText("D-031", { exact: true }).first()).toBeVisible();
  await expect(dialog.getByText("replay-nbr-riv-canonical")).toBeVisible();
  await expect(dialog.getByText(/^[a-f0-9]{64}$/)).toHaveCount(2);
  await expect(dialog.getByRole("button", { name: "Confirm reviewed version" })).toBeDisabled();
  await dialog.getByRole("textbox", { name: /Reason for decision/ }).fill("Both figures verified; interpretation marked as opinion");
  await dialog.getByRole("button", { name: "Confirm reviewed version" }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.getByText("✓ Approved")).toBeVisible();
  await expect(page.getByRole("list").filter({ hasText: "Approved D-031 v4" })).toBeVisible();

  await page.getByRole("button", { name: "Publish to the chosen destinations" }).click();
  await expect(page.getByRole("status").filter({ hasText: "One destination timed out" })).toBeVisible();
  await expect(page.locator(".md-dest .md-chip-verified")).toHaveCount(3);
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.locator(".md-dest .md-chip-verified")).toHaveCount(4);
  await expect(page.getByRole("heading", { name: "In the demo channel" })).toBeVisible();
  await expect(page.getByText(/Social channel: sent PUB-[0-9a-f]{10} \(attempt 2\)/)).toBeVisible();

  // Edit the approved draft: the digests change and the approval no longer applies.
  await page.evaluate(() => {
    const doc = JSON.parse(window.localStorage.getItem("md.d031"));
    doc.headline = "A different headline";
    window.localStorage.setItem("md.d031", JSON.stringify(doc));
  });
  await page.reload();
  await expect(page.getByRole("alert").filter({ hasText: "Approval withdrawn" })).toBeVisible();
  await expect(page.getByRole("button", { name: BUTTON })).toBeVisible();
  expect(apiRequests).toEqual([]);
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
    // Native <dialog> itself may receive focus when Shift+Tab wraps.
    return !!modal && !!active && (modal === active || modal.contains(active));
  });
  expect(trapped).toBe(true);
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(results.violations.map((v) => v.id)).toEqual([]);
  await page.keyboard.press("Escape");
  await expect(dialog).not.toBeVisible();
});
