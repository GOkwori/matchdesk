/** The broadcast overlay draws only re-verified cues, in the chosen style and language, on a transparent page. */
import { test, expect } from "@playwright/test";

test("the broadcast overlay shows a verified Spanish goal graphic on a transparent page", async ({ page }) => {
  await page.goto("/broadcast/nbr-riv?style=caption&lang=es&speed=1&from=34:17");
  const third = page.locator(".md-bc-third");
  await expect(third).toContainText("GOL", { timeout: 10_000 });
  await expect(third).toContainText("Verificado");
  await expect(page.locator(".md-bc-score")).toHaveText("1–0");
  expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe("rgba(0, 0, 0, 0)");
  expect(await page.evaluate(() => document.documentElement.lang)).toBe("es");
});

test("the verifier benchmark page states its results and its limits", async ({ page }) => {
  await page.goto("/match/nbr-riv/evidence/benchmark");
  await expect(page.getByRole("heading", { level: 1, name: "Can you trick the fact checker?" })).toBeVisible();
  await expect(page.getByText(/810 of 810/)).toBeVisible();
  await expect(page.getByText(/Barros replaced Kovac/).first()).toBeVisible();
  await expect(page.getByText(/they cannot prove there is no other way to be wrong/)).toBeVisible();
});
