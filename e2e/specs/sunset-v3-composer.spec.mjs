/** Screen 09: local editorial simulation must not acquire publishing authority. */
import { test, expect } from "@playwright/test";

async function openComposer(page) {
  if (page.viewportSize()?.width < 640) {
    await page.locator(".mdv3-mobile-more-trigger").click();
    await page.getByRole("region", { name: "More demo destinations" })
      .getByRole("button", { name: /Story & Commentary Composer/ }).click();
  } else {
    await page.getByRole("button", { name: "Editorial Review" }).click();
  }
}
test.beforeEach(async ({ page }) => { await page.goto("/sunset-v3"); });
test("composer edits are local and cannot save or publish", async ({ page }) => {
  const requests = [];
  page.on("request", request => {
    if (new URL(request.url()).pathname.startsWith("/api/")) requests.push(request.url());
  });
  await openComposer(page);
  await expect(page.getByRole("heading", { name: "Story & Commentary Composer" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Save version (Planned)" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Approve (Planned)" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Publish (Planned)" })).toBeDisabled();
  await page.getByRole("textbox", { name: /Story text/ }).fill("Example local text");
  await page.getByRole("button", { name: "Check demo limitations" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Changes are local" })).toBeVisible();
  await page.reload();
  await openComposer(page);
  await expect(page.getByRole("textbox", { name: /Story text/ })).not.toHaveValue("Example local text");
  expect(requests).toEqual([]);
});
for (const width of [390, 768, 1280, 1440]) {
  test(`composer reflows at ${width}px`, async ({ page }) => {
    await page.setViewportSize({width, height: 880});
    await openComposer(page);
    await expect(page.getByRole("heading", { name: "Story & Commentary Composer" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
}
