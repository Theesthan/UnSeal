import { defineConfig, devices } from "@playwright/test";

// The real API is never started: specs mock /api with page.route (e2e/support/mock-api.ts), and
// e2e/deploy.spec.ts checks the /api rewrite against a small echo server.
const PORT = 3100;
const FAKE_API_PORT = 8100;
const APP_ORIGIN = `http://localhost:${PORT}`;

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: APP_ORIGIN,
    trace: "retain-on-failure",
    locale: "en-IN",
    timezoneId: "Asia/Kolkata",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      // Echo server behind the /api rewrite, for e2e/deploy.spec.ts only.
      command: `node e2e/support/fake-upstream.mjs`,
      url: `http://127.0.0.1:${FAKE_API_PORT}/health`,
      reuseExistingServer: !process.env.CI,
      env: { FAKE_API_PORT: String(FAKE_API_PORT) },
    },
    {
      command: `npm run build && npx next start -p ${PORT}`,
      url: `${APP_ORIGIN}/en`,
      reuseExistingServer: !process.env.CI,
      timeout: 600_000,
      // The production setup: the browser calls /api on its own origin (NEXT_PUBLIC_API_URL
      // empty) and Next.js forwards it to API_ORIGIN.
      env: { NEXT_PUBLIC_API_URL: "", API_ORIGIN: `http://127.0.0.1:${FAKE_API_PORT}` },
    },
  ],
});
