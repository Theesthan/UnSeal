import { expect, test } from "@playwright/test";
import { en } from "../messages/en";
import { hi } from "../messages/hi";
import { format } from "../lib/i18n-core";
import { expectAccessible, expectNoHorizontalScroll } from "./support/a11y";

test("sample gallery: three labelled samples, no API calls, local accept", async ({ page }) => {
  const apiRequests: string[] = [];
  page.on("request", (r) => {
    // The API is reached through the same-origin /api proxy.
    if (new URL(r.url()).pathname.startsWith("/api/")) apiRequests.push(r.url());
  });

  await page.goto("/hi/samples");
  await expect(page.getByRole("heading", { name: hi.samples.title, level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: new RegExp(hi.samples.open) })).toHaveCount(3);
  await expectAccessible(page);

  await page
    .getByRole("link", { name: format(hi.samples.openLabel, { title: hi.samples.cases["answer-sheet"].title }) })
    .click();
  await expect(page.getByRole("note").first()).toContainText(hi.samples.banner);
  // The Tamil case content is marked as Tamil inside the Hindi page.
  await expect(page.locator('blockquote[lang="ta"]')).toBeVisible();
  await page.getByRole("button", { name: format(hi.question.acceptLabel, { n: 2 }) }).click();
  await expect(page.getByText(hi.question.accepted, { exact: true })).toHaveCount(2);
  await expectNoHorizontalScroll(page);
  await expectAccessible(page);

  expect(apiRequests).toEqual([]);
});

test("every sample page renders in English with its timeline", async ({ page }) => {
  for (const slug of ["answer-sheet", "ward-road", "passport-delay"] as const) {
    await page.goto(`/en/samples/${slug}`);
    await expect(page.getByRole("heading", { name: en.samples.cases[slug].title })).toBeVisible();
    await expect(page.getByRole("list", { name: en.timeline.title })).toBeVisible();
    await expectAccessible(page);
  }
});
