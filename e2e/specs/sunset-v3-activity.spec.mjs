/** Screen 12: source-only fixture activity and ephemeral settings; no audit API. */
import { test, expect } from "@playwright/test";

async function openActivity(page) {
  if (page.viewportSize().width <= 700) {
    await page.getByRole("navigation", { name: "Mobile demo navigation" }).locator(".mdv3-mobile-more-trigger").click();
    await page.getByRole("region", { name: "More demo destinations" }).getByRole("button", { name: /Activity, Audit & Settings/ }).click();
  } else {
    await page.getByRole("button", { name: "Activity & Audit", exact: true }).click();
  }
}
test.beforeEach(async ({ page }) => { await page.goto("/sunset-v3"); });
test("fixture rows contain only canonical event IDs and no authenticated audit trail", async ({ page }) => {
  const calls = [];
  page.on("request", req => { if (new URL(req.url()).pathname.startsWith("/api/")) calls.push(req.url()); });
  await openActivity(page);
  const table = page.getByRole("table", { name: "Named synthetic fixture events" });
  await expect(table.getByRole("rowheader")).toHaveCount(5);
  for (const id of ["E-1421", "E-1402", "E-1366", "E-0790", "E-0688"]) await expect(table).toContainText(id);
  await expect(table).not.toContainText("E-1188");
  await expect(table).not.toContainText("E-1042");
  await table.getByRole("button", { name: "Details for E-1366" }).click();
  const details = page.getByRole("region", { name: "Selected synthetic event details" });
  await expect(details).toContainText("58:17");
  await expect(details).toContainText("Not generated");
  await details.getByRole("button", { name: "Close details for E-1366" }).click();
  await expect(details).toHaveCount(0);
  expect(calls).toEqual([]);
});
test("history tabs cannot fabricate producer reviews or durable versions", async ({ page }) => {
  await openActivity(page);
  await page.getByRole("tab", { name: "Review history" }).click();
  await expect(page.getByRole("tabpanel", { name: "Review history" })).toContainText("No authenticated review history available");
  await page.getByRole("tab", { name: "Review history" }).press("ArrowRight");
  await expect(page.getByRole("tab", { name: "Version history" })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByRole("tabpanel", { name: "Version history" })).toContainText("No durable version history available");
});
test("preferences are local and cannot change publishing authority", async ({ page }) => {
  await openActivity(page);
  await page.getByRole("button", { name: "Light", exact: true }).click();
  await expect(page.locator(".mdv3")).toHaveAttribute("data-theme", "light");
  await page.getByLabel("Reduce motion").check();
  await page.getByLabel("Text size").selectOption("large");
  await expect(page.locator(".mdv3-activity")).toHaveAttribute("data-reduce-motion", "on");
  await expect(page.locator(".mdv3-activity")).toHaveAttribute("data-text-size", "large");
  await expect(page.getByText("Unavailable", { exact: true })).toBeVisible();
  await page.reload();
  await openActivity(page);
  await expect(page.locator(".mdv3-activity")).toHaveAttribute("data-text-size", "default");
});
for (const width of [390, 768, 1280, 1440]) {
  test("activity fits " + width + "px in dark and light themes", async ({ page }) => {
    await page.setViewportSize({ width, height: 880 });
    await openActivity(page);
    for (const theme of ["dark", "light"]) {
      await page.getByLabel("Display theme").selectOption(theme);
      await expect(page.getByRole("heading", { name: "Activity, Audit & Settings" })).toBeVisible();
      await expect(page.locator(".mdv3-activity-table tbody tr")).toHaveCount(5);
      if (width <= 700) await expect(page.locator(".mdv3-activity-table tbody tr").first()).toHaveCSS("display", "grid");
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    }
  });
}

/** Contrast is computed from the rendered panel and label colours, not a
 * hard-coded theme guess. Both approved themes must meet WCAG AA normal text.
 */
test("preference label colours meet WCAG AA in both themes", async ({ page }) => {
  for (const width of [390, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/sunset-v3");
    await openActivity(page);
    for (const theme of ["dark", "light"]) {
      await page.getByLabel("Display theme").selectOption(theme);
      for (const id of ["mdv3-activity-motion", "mdv3-activity-text-size"]) {
        const ratio = await page.locator('label[for="' + id + '"]').evaluate(element => {
          const panel = element.closest(".mdv3-activity-preferences");
          if (!panel) throw new Error("The expected settings panel is missing");
          const fg = getComputedStyle(element).color;
          const bg = getComputedStyle(panel).backgroundColor;
          const rgb = value => (value.match(/[0-9]+(?:[.][0-9]+)?/g) ?? [])
            .slice(0, 3).map(Number);
          const luminance = value => {
            const channels = rgb(value).map(c => {
              const v = c / 255;
              return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
            });
            if (channels.length !== 3) throw new Error("Unparseable computed RGB colour");
            return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
          };
          const high = Math.max(luminance(fg), luminance(bg));
          const low = Math.min(luminance(fg), luminance(bg));
          return (high + 0.05) / (low + 0.05);
        });
        expect(ratio, id + " at " + width + "px / " + theme)
          .toBeGreaterThanOrEqual(4.5);
      }
    }
  }
});
