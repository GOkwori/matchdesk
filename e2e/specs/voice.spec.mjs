/** Voice-over: stories, recaps, Ask answers and the replay can be read aloud. */
import { test, expect } from "@playwright/test";

test("a verified story can be read aloud, and says which voice reads it", async ({ page }) => {
  await page.goto("/story/okafor-header-restores-northbridge-lead?lang=es");
  const listen = page.getByRole("button", { name: /Escuchar/ });
  await expect(listen).toBeVisible();
  await listen.click();
  await expect(page.getByRole("status").filter({ hasText: /Voz: /i }).or(page.getByText("Sin voz en este dispositivo"))).toBeVisible();
});

test("the recap and the replay offer voice-over", async ({ page }) => {
  await page.goto("/story/recap");
  await expect(page.getByRole("button", { name: /Listen/ })).toBeVisible();
  await page.goto("/match/nbr-riv/live");
  const toggle = page.getByRole("button", { name: /Read overlays aloud/ });
  await expect(toggle).toBeVisible();
  await toggle.click();
  await expect(page.getByRole("button", { name: /Voice-over on/ })).toHaveAttribute("aria-pressed", "true");
});
