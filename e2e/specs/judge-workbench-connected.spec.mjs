/** Actual localhost browser-to-judge HTTP qualification with disposable sessions. */
import { expect, test } from "@playwright/test";

// Ordinary Compose browser regressions intentionally skip this opt-in suite.
test.skip(process.env.MATCHDESK_LOCAL_JUDGE_ENABLED !== "1", "Requires the isolated loopback judge hosts");

test("actual judge browser replays, rotates, and revokes a disposable session", async ({ page }, info) => {
  // This suite only runs against the opt-in 127.0.0.1 Python and Next servers.
  expect(process.env.MATCHDESK_LOCAL_JUDGE_ENABLED).toBe("1");
  // Capture only HTTP status/route and safe on-page error, never bearer headers or bodies.
  const httpStatus = [];
  page.on("response", (response) => {
    if (response.url().includes("/api/judge-local/")) {
      httpStatus.push(`${response.request().method()} ${new URL(response.url()).pathname} ${response.status()} denial=${response.headers()["x-matchdesk-judge-denial"] ?? "none"}`);
    }
  });
  await page.goto("/judge");
  await expect(page.getByRole("heading", { name: "No active replay evidence" })).toBeVisible();
  await page.getByRole("button", { name: "Start demo" }).click();
  await expect.poll(async () => {
    const found = await page.getByRole("heading", { name: "Match evidence" }).count();
    const alert = await page.getByRole("alert").allTextContents();
    return found ? "evidence" : `http=${httpStatus.join(",")} alert=${alert.join(" ")}`;
  }, { timeout: 10000 }).toBe("evidence");
  await expect(page.getByRole("heading", { name: "Can we say this?" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Different formats, same evidence" })).toBeVisible();
  await expect(page.getByText("needs_revision", { exact: true })).toBeVisible();
  await expect(page.getByText("Approval disabled")).toBeVisible();
  await expect(page.getByText("Publication disabled")).toBeVisible();
  await expect(page.getByText("Verified run")).toBeVisible();
  // Evidence screenshot excludes the bearer, which never appears in the DOM.
  await info.attach("synthetic-judge-view", {
    body: await page.screenshot({ fullPage: true }), contentType: "image/png",
  });
  await page.getByRole("button", { name: "Reset" }).click();
  await expect(page.getByText(/Generation 2/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "No active replay evidence" })).toBeVisible();
  await page.getByRole("button", { name: "Replay" }).click();
  await expect(page.getByRole("heading", { name: "Match evidence" })).toBeVisible();
  await page.getByRole("button", { name: "End session" }).click();
  await expect(page.getByRole("heading", { name: "No active replay evidence" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Start demo" })).toBeEnabled();
});

test("two browsers independently retain their isolated synthetic runs", async ({ browser }) => {
  // Prove reset on one browser does not reset or end the other.
  expect(process.env.MATCHDESK_LOCAL_JUDGE_ENABLED).toBe("1");
  const first = await browser.newContext();
  const second = await browser.newContext();
  try {
    const a = await first.newPage();
    const b = await second.newPage();
    await a.goto("/judge");
    await b.goto("/judge");
    await a.getByRole("button", { name: "Start demo" }).click();
    await b.getByRole("button", { name: "Start demo" }).click();
    await expect(a.getByRole("heading", { name: "Match evidence" })).toBeVisible();
    await expect(b.getByRole("heading", { name: "Match evidence" })).toBeVisible();
    await a.getByRole("button", { name: "Reset" }).click();
    await expect(a.getByText(/Generation 2/)).toBeVisible();
    await b.getByRole("button", { name: "Replay" }).click();
    await expect(b.getByRole("heading", { name: "Match evidence" })).toBeVisible();
    await a.getByRole("button", { name: "Replay" }).click();
    await a.getByRole("button", { name: "End session" }).click();
    await b.getByRole("button", { name: "End session" }).click();
  } finally {
    await first.close();
    await second.close();
  }
});

test("local bridge denies cross-origin and forwarded header spoofing", async ({ request }) => {
  expect(process.env.MATCHDESK_LOCAL_JUDGE_ENABLED).toBe("1");
  const url = "/api/judge-local/sessions";
  const content = { "Content-Type": "application/json" };
  const offsite = await request.post(url, {
    headers: { ...content, Origin: "https://evil.example" }, data: "{}",
  });
  expect(offsite.status()).toBe(403);
  const forged = await request.post(url, {
    headers: { ...content, Origin: "http://127.0.0.1:3000", Forwarded: "for=10.0.0.1" },
    data: "{}",
  });
  expect(forged.status()).toBe(403);
  const query = await request.post(url + "?access=1", {
    headers: { ...content, Origin: "http://127.0.0.1:3000" }, data: "{}",
  });
  expect(query.status()).toBe(403);
});
