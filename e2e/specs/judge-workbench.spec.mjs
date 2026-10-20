/** Judge UI smoke in normal Compose; opt-in judge mode is separately rehearsed. */
import { expect, test } from "@playwright/test";

test("synthetic judge workbench presents an honest inactive state", async ({ page }) => {
  await page.goto("/judge");
  await expect(page.getByRole("heading", { name: /See the evidence/ })).toBeVisible();
  await expect(page.getByText("LOCAL · SYNTHETIC · READ ONLY")).toBeVisible();
  await expect(page.getByRole("heading", { name: "No active replay evidence" })).toBeVisible();
  // Both judge navigation links return to the supported studio home route.
  await expect(page.getByRole("link", { name: /MATCHDESK \/ SUNSET STUDIO/ })).toHaveAttribute("href", "/");
  await expect(page.getByRole("link", { name: "Back to Sunset Studio" })).toHaveAttribute("href", "/");
  await expect(page.getByRole("button", { name: "Reset" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "End session" })).toBeDisabled();
});

test("web runtime defaults to a disabled judge bridge", async ({ request }) => {
  if (process.env.MATCHDESK_LOCAL_JUDGE_ENABLED === "1") test.skip();
  const response = await request.post("/api/judge-local/sessions", {
    headers: { Origin: "http://127.0.0.1:3000", "Content-Type": "application/json" },
    data: "{}",
  });
  expect(response.status()).toBe(404);
  expect(response.headers()["cache-control"]).toContain("no-store");
});
