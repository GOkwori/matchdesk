/** Screen 13 browser regression: local-only notifications and safe dialogs. */
import { test, expect } from "@playwright/test";

async function openLibrary(page) {
  if (page.viewportSize().width <= 700) {
    await page.getByRole("navigation", { name: "Mobile demo navigation" }).locator(".mdv3-mobile-more-trigger").click();
    await page.getByRole("region", { name: "More demo destinations" }).getByRole("button", { name: /Notification & Dialogue Library/ }).click();
  } else {
    await page.getByRole("button", { name: "Settings & Help", exact: true }).click();
  }
}

test.beforeEach(async ({ page }) => { await page.goto("/sunset-v3"); });

test("semantic banners are labelled and critical notices remain visible", async ({ page }) => {
  await openLibrary(page);
  await expect(page.getByRole("heading", { name: "Notification & Dialogue Library" })).toBeVisible();
  for (const kind of ["success", "information", "warning", "error"]) {
    await expect(page.locator(".mdv3-notice-card.mdv3-notice-" + kind)).toBeVisible();
  }
  await page.getByRole("button", { name: "Dismiss success example" }).click();
  await expect(page.locator(".mdv3-notice-card.mdv3-notice-success")).toHaveCount(0);
  await expect(page.locator(".mdv3-notice-card.mdv3-notice-warning")).toBeVisible();
  await expect(page.locator(".mdv3-notice-card.mdv3-notice-error")).toBeVisible();
  await page.getByRole("button", { name: "Reset banner examples" }).click();
  await expect(page.locator(".mdv3-notice-card.mdv3-notice-success")).toBeVisible();
});

test("safe discard dialog traps focus, cancels with Escape and only clears local example", async ({ page }) => {
  const api = [], native = [];
  page.on("request", request => { if (new URL(request.url()).pathname.startsWith("/api/")) api.push(request.url()); });
  page.on("dialog", dialog => { native.push(dialog.type()); void dialog.dismiss(); });
  await openLibrary(page);
  const opener = page.getByRole("button", { name: "Try local discard" });
  await opener.click();
  const dialog = page.getByRole("dialog", { name: "Discard changes?" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByRole("textbox", { name: "Local example edit" })).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(dialog.getByRole("button", { name: "Discard local example" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
  await opener.click();
  await dialog.getByRole("button", { name: "Discard local example" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Local example cleared" })).toBeVisible();
  expect(api).toEqual([]);
  expect(native).toEqual([]);
});

test("reject, approve and publish are fail-closed UI examples", async ({ page }) => {
  const api = [];
  page.on("request", request => { if (new URL(request.url()).pathname.startsWith("/api/")) api.push(request.url()); });
  await openLibrary(page);
  for (const title of ["Reject this draft?", "Approve draft?", "Confirm publication?"]) {
    const card = page.locator(".mdv3-notice-dialog-card").filter({ has: page.getByRole("heading", { name: title }) });
    await card.getByRole("button", { name: "Inspect safe dialogue" }).click();
    const dialog = page.getByRole("dialog", { name: title });
    await expect(dialog).toBeVisible();
    await expect(dialog.locator("button:disabled")).toHaveCount(1);
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
  }
  expect(api).toEqual([]);
});

test("light and dark themes retain responsive readable status labels", async ({ page }) => {
  await openLibrary(page);
  for (const theme of ["dark", "light"]) {
    await page.getByLabel("Display theme").selectOption(theme);
    await expect(page.locator(".mdv3")).toHaveAttribute("data-theme", theme);
    const warning = page.locator(".mdv3-notice-card.mdv3-notice-warning");
    await expect(warning).toContainText("Warning");
    await warning.scrollIntoViewIfNeeded();
    await expect(warning).toBeInViewport();
  }
});
