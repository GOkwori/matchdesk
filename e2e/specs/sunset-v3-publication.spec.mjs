/** Screen 10 future-state publication preview — NEVER a production approval test.
 *
 * A design-reference version can be visually eligible without a verified actor,
 * trustworthy evidence digest, human approval, destination, or publication.
 */
import { test, expect } from "@playwright/test";

async function openPublication(page) {
  if (page.viewportSize()?.width < 640) {
    const nav = page.getByRole("navigation", { name: "Mobile demo navigation" });
    await nav.locator(".mdv3-mobile-more-trigger").click();
    await page.getByRole("region", { name: "More demo destinations" })
      .getByRole("button", { name: /Review & Publication Journey/ }).click();
  } else {
    await page.getByRole("button", { name: "Editorial Review", exact: true }).click();
    await page.getByRole("button", { name: "View future publication journey" }).click();
  }
}

test.beforeEach(async ({ page }) => { await page.goto("/sunset-v3"); });

test("five-stage journey is future state only; no approval or publication is possible", async ({ page }) => {
  const calls = [];
  page.on("request", request => {
    if (new URL(request.url()).pathname.startsWith("/api/")) calls.push(request.url());
  });
  await openPublication(page);
  await expect(page.getByRole("heading", { name: "Review & Publication Journey" })).toBeVisible();
  const stages = page.getByRole("list", { name: "Future-state publication steps — not operational" });
  await expect(stages.getByRole("listitem")).toHaveCount(5);
  await expect(page.getByText("All five stages are illustrative.")).toBeVisible();
  await expect(page.getByText("D-029 v2", { exact: false }).first()).toBeVisible();
  await expect(page.getByText("4 / 4", { exact: true })).toBeVisible();
  await expect(page.getByText("Not computed", { exact: true })).toBeVisible();
  await expect(page.getByText("E-0790", { exact: false })).toBeVisible();
  await expect(page.getByText("41:03", { exact: false })).toBeVisible();
  await expect(page.getByRole("button", { name: /Confirm approval unavailable/ })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Confirm · Future state" })).toBeDisabled();
  await expect(page.getByRole("button", { name: /^Publish/ })).toHaveCount(0);
  expect(calls).toEqual([]);
});

test("approval confirmation example exposes missing prerequisites without granting authority", async ({ page }) => {
  await openPublication(page);
  const review = page.getByRole("button", { name: "Review evidence requirements" });
  await expect(review).toHaveAttribute("aria-expanded", "false");
  await review.click();
  const limitations = page.getByRole("note").filter({ hasText: "Missing execution prerequisites" });
  await expect(limitations).toBeVisible();
  await expect(limitations).toContainText("No D-029 v2 claim-level verification record");
  await expect(page.getByRole("button", { name: "Hide evidence requirements" })).toHaveAttribute("aria-expanded", "true");
  await page.getByRole("button", { name: "Hide evidence requirements" }).click();
  await expect(limitations).toHaveCount(0);
  await page.getByRole("button", { name: "Back to commentary composer" }).click();
  await expect(page.getByRole("heading", { name: "Story & Commentary Composer" })).toBeVisible();
});

test("a new composer-to-publication transition confirms discarding unsaved edits", async ({ page }) => {
  const calls = [];
  page.on("request", req => {
    if (new URL(req.url()).pathname.startsWith("/api/")) calls.push(req.url());
  });
  await page.getByRole("button", { name: "Editorial Review", exact: true }).click();
  const headline = page.getByRole("textbox", { name: "Headline" });
  await headline.fill("Unsaved local draft for review");
  await page.getByRole("button", { name: "View future publication journey" }).click();
  const dialog = page.getByRole("dialog", { name: "Discard your changes?" });
  await expect(dialog).toBeVisible();
  await dialog.getByRole("button", { name: "Continue editing" }).click();
  await expect(headline).toHaveValue("Unsaved local draft for review");
  await page.getByRole("button", { name: "View future publication journey" }).click();
  await dialog.getByRole("button", { name: "Discard local edits" }).click();
  await expect(page.getByRole("heading", { name: "Review & Publication Journey" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Confirm · Future state" })).toBeDisabled();
  expect(calls).toEqual([]);
});

for (const width of [390, 768, 1280, 1440]) {
  test(`future-state layout fits ${width}px and stays disabled in both themes`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await openPublication(page);
    for (const theme of ["dark", "light"]) {
      await page.getByLabel("Display theme").selectOption(theme);
      await expect(page.locator(".mdv3")).toHaveAttribute("data-theme", theme);
      await expect(page.getByRole("heading", { name: "Review & Publication Journey" })).toBeVisible();
      await expect(page.getByRole("button", { name: /Confirm approval unavailable/ })).toBeDisabled();
      await expect(page.getByRole("button", { name: "Confirm · Future state" })).toBeDisabled();
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
        `Screen 10 must not horizontally overflow at ${width}px / ${theme}`
      ).toBe(true);
    }
  });
}
