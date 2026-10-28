import { expect, test } from "@playwright/test";

// These tests do not mock /api: requests go through the real Next.js rewrite (next.config.ts)
// to e2e/support/fake-upstream.mjs, which echoes what reached it.
const CASE_PATH = "/cases/3f0c9a8e-2b1d-4c5e-9f7a-1a2b3c4d5e6f/reply/read";

test("the /api proxy forwards the browser's Origin and keeps the session cookie first-party", async ({
  page,
  context,
}) => {
  await page.goto("/en");
  const result = await page.evaluate(async () => {
    const session = await fetch("/api/session", {
      method: "POST",
      credentials: "include",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ language: "en" }),
    });
    const sent = await session.json();
    const next = await (await fetch("/api/me", { credentials: "include" })).json();
    return { sent, next, scriptSeesCookie: document.cookie.includes("unseal_session") };
  });

  // The path loses its /api prefix; the browser's Origin reaches the API for its write check.
  expect(result.sent).toMatchObject({ method: "POST", path: "/session", origin: "http://localhost:3100" });
  expect(result.sent.forwardedHost).toBe("localhost:3100");
  // The cookie is set on the web app's own host and comes back on the next call.
  expect(result.next.cookie).toContain("unseal_session=fictional-test-session");
  expect(result.scriptSeesCookie).toBe(false);
  const cookie = (await context.cookies()).find((c) => c.name === "unseal_session");
  expect(cookie).toMatchObject({ domain: "localhost", httpOnly: true, sameSite: "Lax" });
});

test("a reply upload at the 10 MB limit streams through the proxy unchanged", async ({ page }) => {
  await page.goto("/en");
  const echo = await page.evaluate(async (path) => {
    const form = new FormData();
    form.append("file", new Blob([new Uint8Array(10 * 1024 * 1024)], { type: "application/pdf" }), "reply.pdf");
    form.append("consent", "true");
    const response = await fetch(`/api${path}`, { method: "POST", body: form, credentials: "include" });
    return response.json();
  }, CASE_PATH);

  expect(echo.path).toBe(CASE_PATH);
  expect(Number(echo.contentLength)).toBeGreaterThan(10 * 1024 * 1024);
  expect(echo.received).toBe(Number(echo.contentLength));
});

test("/api is never redirected to a language page", async ({ request }) => {
  const response = await request.get("/api/health", { maxRedirects: 0 });
  expect(response.status()).toBe(200);
  expect(await response.json()).toMatchObject({ path: "/health" });
});
