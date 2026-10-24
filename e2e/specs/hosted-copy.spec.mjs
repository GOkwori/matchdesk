/** The studio-only copy notice appears only on a Vercel build, never on the full demo. */
import { test, expect } from "@playwright/test";

test("the full demo does not show the studio-only copy notice", async ({ page }) => {
  await page.goto("/match/nbr-riv/live");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.locator(".md-hosted")).toHaveCount(0);
});
