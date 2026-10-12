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

/** Custom confirmation remains accessible and cannot accidentally discard edits. */
test("composer discard dialog traps focus, cancels, restores and confirms locally", async ({ page }) => {
  await openComposer(page);
  const headline = page.getByRole("textbox", { name: "Headline" });
  await headline.fill("Local editorial headline");
  const discardButton = page.getByRole("button", { name: "Discard local changes" });
  await discardButton.click();
  const dialog = page.getByRole("dialog", { name: "Discard your changes?" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("button", { name: "Continue editing" })).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(dialog.getByRole("button", { name: "Discard local edits" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(discardButton).toBeFocused();
  await expect(headline).toHaveValue("Local editorial headline");

  await discardButton.click();
  await dialog.getByRole("button", { name: "Discard local edits" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(headline).toHaveValue("Okafor double restores Northbridge lead");
  await expect(discardButton).toBeDisabled();
  await expect(page.getByRole("button", { name: "Save version (Planned)" })).toBeDisabled();
});

test("composer tabs expose real comparison and honest evidence limitations", async ({ page }) => {
  await openComposer(page);
  await page.getByRole("tab", { name: "Version history" }).click();
  await expect(page.getByRole("tabpanel", { name: "Version history" })).toContainText("prior design excerpt");
  await page.getByRole("tab", { name: "Version history" }).press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Claim evidence" })).toHaveAttribute("aria-selected", "true");
  const claims = page.getByRole("tabpanel", { name: "Claim evidence" });
  await expect(claims).toContainText("Season history unavailable");
  await claims.getByRole("checkbox", { name: /CL-0216/ }).uncheck();
  await page.getByRole("tab", { name: "Edit draft" }).click();
  await expect(page.getByRole("button", { name: "Discard local changes" })).toBeEnabled();
  await expect(page.getByRole("region", { name: "Composer security boundary" })).toContainText("cannot approve");
  await expect(page.getByRole("button", { name: "Publish (Planned)" })).toBeDisabled();
});

test("composer captures only a transient local preview and does not create an approved version", async ({ page }) => {
  const requests = [];
  page.on("request", request => {
    if (new URL(request.url()).pathname.startsWith("/api/")) requests.push(request.url());
  });
  await openComposer(page);
  await expect(page.getByRole("button", { name: "Capture session preview" })).toBeDisabled();
  await page.getByRole("textbox", { name: "Headline" }).fill("A new local headline");
  await page.getByRole("button", { name: "Capture session preview" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Local preview r1" }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Save version (Planned)" })).toBeDisabled();
  await page.getByRole("tab", { name: "Version history" }).click();
  await expect(page.getByRole("tabpanel", { name: "Version history" })).toContainText("Local preview r1");
  await page.reload();
  await openComposer(page);
  await expect(page.getByRole("textbox", { name: "Headline" })).toHaveValue("Okafor double restores Northbridge lead");
  await expect(page.getByRole("button", { name: "Capture session preview" })).toBeDisabled();
  expect(requests).toEqual([]);
});

/** The reference mock-up uses readable normal-weight prose, not bold textarea text. */
test("editor text keeps regular font weight in both themes and viewport sizes", async ({ page }) => {
  for (const width of [390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/sunset-v3");
    await openComposer(page);
    for (const theme of ["dark", "light"]) {
      await page.getByLabel("Display theme").selectOption(theme);
      for (const textbox of ["Headline", "Story text (local exploration only)"]) {
        const field = page.getByRole("textbox", { name: textbox });
        const weight = await field.evaluate(element => Number.parseInt(getComputedStyle(element).fontWeight, 10));
        expect(weight, `${theme} ${width}px ${textbox} should have legible regular text weight`).toBeLessThanOrEqual(500);
      }
    }
  }
});
