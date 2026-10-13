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


test("modal backdrop covers viewport, prevents background interaction and survives zoom", async ({ page }) => {
  await openLibrary(page);
  const opener = page.getByRole("button", { name: "Try local discard" });
  await opener.click();
  const dialog = page.getByRole("dialog", { name: "Discard changes?" });
  await expect(dialog).toBeVisible();
  await page.evaluate(() => { document.documentElement.style.zoom = "2"; });
  const geometry = await page.evaluate(() => {
    const backdrop = document.querySelector(".mdv3-notice-backdrop").getBoundingClientRect();
    const modal = document.querySelector(".mdv3-notice-modal").getBoundingClientRect();
    return {
      backdrop: { left: backdrop.left, top: backdrop.top, right: backdrop.right, bottom: backdrop.bottom },
      modal: { left: modal.left, top: modal.top, right: modal.right, bottom: modal.bottom },
      viewport: { width: window.innerWidth, height: window.innerHeight },
    };
  });
  expect(geometry.backdrop.left).toBeLessThanOrEqual(1);
  expect(geometry.backdrop.top).toBeLessThanOrEqual(1);
  expect(geometry.backdrop.right).toBeGreaterThanOrEqual(geometry.viewport.width - 1);
  expect(geometry.backdrop.bottom).toBeGreaterThanOrEqual(geometry.viewport.height - 1);
  expect(geometry.modal.left).toBeGreaterThanOrEqual(-1);
  expect(geometry.modal.right).toBeLessThanOrEqual(geometry.viewport.width + 1);
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
});

/** Both custom modal implementations must make background controls inert,
 * preventing real DOM focus or pointer interaction. The inert property belongs
 * on an ancestor, so an inert descendant need not carry that property itself.
 * Playwright role-locator matching alone does not prove the browser's native
 * inert/focus semantics; this subset cannot replace issue #52 AT testing.
 */
async function expectBackgroundFocusBlocked(control) {
  const outcome = await control.evaluate(element => {
    const hasInertAncestor = Boolean(element.closest('[inert]'));
    element.focus();
    return { hasInertAncestor, receivedFocus: document.activeElement === element };
  });
  expect(outcome).toEqual({ hasInertAncestor: true, receivedFocus: false });
}

test("notification modal makes background inert and restores it after Escape", async ({ page }) => {
  await openLibrary(page);
  const opener = page.getByRole("button", { name: "Try local discard" });
  // The panel is a sibling of the backdrop; its nested button grid is inert
  // through inheritance rather than by having an inert property itself.
  const background = page.locator(".mdv3-notice-dialog-grid").locator("xpath=..");
  const mobileNavigation = page.locator(".mdv3-mobile-nav");
  await opener.click();
  const dialog = page.getByRole("dialog", { name: "Discard changes?" });
  await expect(dialog).toBeVisible();
  await expect(dialog).toHaveAttribute("aria-modal", "true");
  await expect(background).toHaveJSProperty("inert", true);
  await expect(mobileNavigation).toHaveJSProperty("inert", true);
  await expectBackgroundFocusBlocked(opener);
  await expect(dialog.getByRole("button", { name: "Continue editing" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(background).toHaveJSProperty("inert", false);
  await expect(mobileNavigation).toHaveJSProperty("inert", false);
  await expect(opener).toBeFocused();
  await opener.click();
  await expect(background).toHaveJSProperty("inert", true);
  await expectBackgroundFocusBlocked(opener);
  await dialog.getByRole("button", { name: "Continue editing" }).click();
  await expect(background).toHaveJSProperty("inert", false);
  await expect(mobileNavigation).toHaveJSProperty("inert", false);
  await expect(opener).toBeFocused();
});

test("blocked approval modal isolates whole application background and restores focus", async ({ page }) => {
  // Desktop/tablet show the sidebar; mobile uses a persistent bottom nav.
  // Exercise both pathways, instead of clicking a hidden desktop control.
  if (page.viewportSize().width <= 700) {
    await page.getByRole("navigation", { name: "Mobile demo navigation" })
      .getByRole("button", { name: /Overview/ }).click();
  } else {
    await page.getByRole("button", { name: "Overview", exact: true }).click();
  }
  const opener = page.getByRole("button", { name: "Why is approval blocked?" });
  const background = page.locator(".mdv3-shell");
  const mobileNavigation = page.locator(".mdv3-mobile-nav");
  await opener.click();
  const dialog = page.getByRole("dialog", { name: "Approval blocked" });
  await expect(dialog).toBeVisible();
  await expect(dialog).toHaveAttribute("aria-modal", "true");
  await expect(background).toHaveJSProperty("inert", true);
  await expect(mobileNavigation).toHaveJSProperty("inert", true);
  await expectBackgroundFocusBlocked(opener);
  await expect(dialog.getByRole("button", { name: "Understood" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(background).toHaveJSProperty("inert", false);
  await expect(mobileNavigation).toHaveJSProperty("inert", false);
  await expect(opener).toBeFocused();
  await opener.click();
  await expect(background).toHaveJSProperty("inert", true);
  await expectBackgroundFocusBlocked(opener);
  await dialog.getByRole("button", { name: "Understood" }).click();
  await expect(background).toHaveJSProperty("inert", false);
  await expect(mobileNavigation).toHaveJSProperty("inert", false);
  await expect(opener).toBeFocused();
});
