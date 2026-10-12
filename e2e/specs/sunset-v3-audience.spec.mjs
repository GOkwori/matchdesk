/** Screen 11: source-bound synthetic audience story, never a public feed.
 *
 * Validate named fixture evidence, missing positions, responsive layouts and
 * the complete absence of producer mutations or publication actions.
 */
import { test, expect } from "@playwright/test";

async function openAudience(page) {
  if (page.viewportSize()?.width < 701) {
    const nav = page.getByRole("navigation", { name: "Mobile demo navigation" });
    await nav.locator(".mdv3-mobile-more-trigger").click();
    await page.getByRole("region", { name: "More demo destinations" })
      .getByRole("button", { name: /Audience Experience/ }).click();
  } else {
    await page.getByRole("button", { name: "Audience Outputs", exact: true }).click();
  }
}

test.beforeEach(async ({ page }) => { await page.goto("/sunset-v3"); });

test("audience story uses named synthetic events, not tracking or publication", async ({ page }) => {
  const calls = [], errors = [];
  page.on("request", request => {
    if (new URL(request.url()).pathname.startsWith("/api/")) calls.push(request.url());
  });
  page.on("pageerror", error => errors.push(error.message));
  await openAudience(page);
  await expect(page.getByRole("heading", { level: 1, name: "Audience Experience" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Okafor's second goal puts Northbridge ahead/ })).toBeVisible();
  await expect(page.getByText("Recorded fixture facts")).toBeVisible();
  await expect(page.getByText("Audience view · Future state")).toBeVisible();
  await expect(page.getByText("14 seconds", { exact: false }).first()).toBeVisible();
  await expect(page.getByRole("group", {
    name: "Decorative football pitch schematic: no positional, tracking or shot-location data",
  })).toBeVisible();
  await expect(page.getByRole("heading", { name: "How we checked this" })).toBeVisible();
  const checklist = page.locator(".mdv3-audience-checklist");
  await expect(checklist).toContainText("Goal scorer in fixture");
  await expect(checklist).toContainText("Timing of recorded events");
  await expect(checklist).toContainText("Defender positions");
  await expect(checklist).toContainText("Not verifiable");
  await expect(page.getByRole("note").filter({ hasText: "Why some claims are excluded" }))
    .toContainText("do not include defender positions");
  await expect(page.getByRole("region", { name: "Audience preview security boundary" }))
    .toContainText("No public delivery");
  await expect(page.getByRole("button", { name: /Approve|Publish|Share/ })).toHaveCount(0);
  expect(calls).toEqual([]);
  expect(errors).toEqual([]);
});

test("source disclosure exposes only recorded IDs, times and missing tracking", async ({ page }) => {
  const calls = [];
  page.on("request", request => {
    if (new URL(request.url()).pathname.startsWith("/api/")) calls.push(request.url());
  });
  await openAudience(page);
  const expand = page.getByRole("button", { name: "View source details" });
  await expect(expand).toHaveAttribute("aria-expanded", "false");
  await expand.click();
  const source = page.getByRole("region", { name: "Synthetic source event details" });
  await expect(source).toBeVisible();
  await expect(source).toContainText("E-0688 · 34:18");
  await expect(source).toContainText("E-1359 · 58:03");
  await expect(source).toContainText("E-1366 · 58:17");
  await expect(source).toContainText("14 seconds");
  await expect(source).toContainText("Not provided");
  await expect(page.getByRole("button", { name: "Hide source details" }))
    .toHaveAttribute("aria-expanded", "true");
  await page.getByRole("button", { name: "Hide source details" }).click();
  await expect(source).toHaveCount(0);
  await page.getByRole("button", { name: "View source details" }).click();
  await source.getByRole("button", { name: "Open Evidence Explorer" }).click();
  await expect(page.getByRole("heading", { name: "Evidence Verification Explorer" })).toBeVisible();
  expect(calls).toEqual([]);
});

test("audience view is a future-state concept, not a published article", async ({ page }) => {
  await openAudience(page);
  await expect(page.getByText("Concept · Not live")).toBeVisible();
  await expect(page.getByText("unpublished preview", { exact: false })).toBeVisible();
  await expect(page.getByText("No tracking or event-position data")).toBeVisible();
  await expect(page.locator(".mdv3-audience-pitch svg")).toHaveAttribute("aria-hidden", "true");
  await expect(page.getByRole("link", { name: /Publish|Share this story/ })).toHaveCount(0);
});

for (const width of [390, 768, 1280, 1440]) {
  test("audience story reflows within " + width + "px in both themes", async ({ page }) => {
    await page.setViewportSize({ width, height: 880 });
    await openAudience(page);
    for (const theme of ["dark", "light"]) {
      await page.getByLabel("Display theme").selectOption(theme);
      await expect(page.locator(".mdv3")).toHaveAttribute("data-theme", theme);
      await expect(page.getByRole("heading", { level: 1, name: "Audience Experience" })).toBeVisible();
      await expect(page.getByRole("button", { name: "View source details" })).toBeVisible();
      const count = await page.locator(".mdv3-audience-layout").evaluate(
        element => getComputedStyle(element).gridTemplateColumns.split(" ").length);
      expect(count, "Responsive columns at " + width + "px").toBe(width <= 1050 ? 1 : 2);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),
        "No overflow at " + width + "px / " + theme).toBe(true);
    }
  });
}

/** Prevent tiny secondary text returning to the mobile score strip. */
test("secondary audience labels stay at least 12px in both themes", async ({ page }) => {
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/sunset-v3");
    await openAudience(page);
    for (const theme of ["dark", "light"]) {
      await page.getByLabel("Display theme").selectOption(theme);
      for (const selector of [
        ".mdv3-audience .mdv3-kicker",
        ".mdv3-audience-team strong",
        ".mdv3-audience-team small",
        ".mdv3-audience-score-middle small",
        ".mdv3-audience-pitch-caption span",
      ]) {
        const fontSize = await page.locator(selector).first().evaluate(
          element => Number.parseFloat(getComputedStyle(element).fontSize)
        );
        expect(fontSize, selector + " 12px floor at " + width + "px / " + theme).toBeGreaterThanOrEqual(12);
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    }
  }
});
