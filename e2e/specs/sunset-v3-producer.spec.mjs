/** Screen 08: inspect-only producer queue with design reference eligibility. */
import { test, expect } from "@playwright/test";

async function openProducer(page) {
  if (page.viewportSize()?.width < 640) {
    const nav = page.getByRole("navigation", { name: "Mobile demo navigation" });
    await nav.locator(".mdv3-mobile-more-trigger").click();
    await page.getByRole("region", { name: "More demo destinations" })
      .getByRole("button", { name: /Producer Review Queue/ }).click();
  } else {
    await page.getByRole("button", { name: "Producer Desk", exact: true }).click();
  }
}

test.beforeEach(async ({ page }) => { await page.goto("/sunset-v3"); });

test("producer queue is reference-only and cannot execute approval or publication", async ({ page }) => {
  const requests = [];
  page.on("request", request => {
    if (new URL(request.url()).pathname.startsWith("/api/")) requests.push(request.url());
  });
  await openProducer(page);
  await expect(page.getByRole("heading", { name: "Producer Review Queue" })).toBeVisible();
  const queue = page.getByRole("table", { name: "Synthetic producer review queue" });
  await expect(queue.locator("tbody tr")).toHaveCount(2);
  await expect(page.getByRole("region", { name: "Selected draft inspection" })).toContainText("CL-0216");
  await expect(page.getByRole("button", { name: "Approve · Unavailable" })).toBeDisabled();

  await page.getByRole("button", { name: "Reference eligible" }).click();
  await expect(queue.locator("tbody tr")).toHaveCount(1);
  await page.getByRole("button", { name: "Inspect D-029 v2" }).click();
  const detail = page.getByRole("region", { name: "Selected draft inspection" });
  await expect(detail).toContainText("neither approved nor published");
  await expect(detail.getByRole("button", { name: "Inspect reference evidence" })).toBeDisabled();
  await expect(detail.getByRole("button", { name: "Approve · Unavailable" })).toBeDisabled();
  expect(requests).toEqual([]);
});

test("reviewed filter has honest empty state; evidence is local-only", async ({ page }) => {
  await openProducer(page);
  await page.getByRole("button", { name: "Reviewed", exact: true }).click();
  await expect(page.getByText("No reviewed drafts are supplied")).toBeVisible();
  await expect(page.getByRole("region", { name: "Selected draft inspection" })).toContainText("Choose an available draft");
  await page.getByRole("button", { name: "All drafts" }).click();
  await page.getByRole("button", { name: "Inspect reference evidence" }).click();
  await expect(page.getByRole("heading", { name: "Evidence Verification Explorer" })).toBeVisible();
});

for (const width of [390, 768, 1280, 1440]) {
  test(`producer queue stays within document width at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 880 });
    await openProducer(page);
    await expect(page.getByRole("heading", { name: "Producer Review Queue" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await expect(page.getByRole("button", { name: "Approve · Unavailable" })).toBeDisabled();
  });
}

/** At phone width, preserve the approved card presentation and table semantics. */
test("producer review mobile draft cards retain accessible row/inspect controls", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openProducer(page);
  const queue = page.getByRole("table", { name: "Synthetic producer review queue" });
  const rows = queue.getByRole("row").filter({ has: page.locator("button") });
  await expect(rows).toHaveCount(2);
  await expect(queue.getByRole("rowheader")).toHaveCount(2);
  await expect(rows.first()).toHaveCSS("display", "grid");
  await expect(rows.first().getByRole("button", { name: "Inspect D-031 v3" })).toBeVisible();
  await queue.getByRole("button", { name: "Inspect D-029 v2" }).click();
  await expect(page.getByRole("region", { name: "Selected draft inspection" })).toContainText("D-029 v2");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
