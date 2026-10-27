import { expect, test, type Page } from "@playwright/test";
import { en } from "../messages/en";
import { hi } from "../messages/hi";
import { ta } from "../messages/ta";
import { expectAccessible, expectNoHorizontalScroll } from "./support/a11y";
import { CASE_ID, FIXTURES, type Lang } from "./support/fixtures";
import {
  baseCase,
  filedCase,
  mockApi,
  repliedCase,
  reviewQuestions,
  SAMPLE_LETTER_PNG,
} from "./support/mock-api";

const MESSAGES = { en, hi, ta };
const VIEWPORTS = [
  { width: 360, height: 800 },
  { width: 768, height: 1024 },
  { width: 1280, height: 800 },
];
const LANGS: Lang[] = ["en", "hi", "ta"];

async function settle(page: Page) {
  await page.evaluate(async () => {
    await document.fonts.ready;
  });
}

async function shoot(page: Page, name: string, lang: Lang, width: number, height: number) {
  await settle(page);
  await expectNoHorizontalScroll(page);
  await page.screenshot({
    path: `e2e/screenshots/${name}-${lang}-${width}x${height}.png`,
    fullPage: true,
  });
  await expectAccessible(page);
}

for (const lang of LANGS) {
  for (const { width, height } of VIEWPORTS) {
    test.describe(`${lang} at ${width}x${height}`, () => {
      test.use({ viewport: { width, height } });
      const t = MESSAGES[lang];
      const f = FIXTURES[lang];

      test("landing", async ({ page }) => {
        await mockApi(page, { lang });
        await page.goto(`/${lang}`);
        await expect(page.getByRole("heading", { name: t.landing.title, level: 1 })).toBeVisible();
        await expect(page.locator("html")).toHaveAttribute("lang", lang);
        await shoot(page, "landing", lang, width, height);
      });

      test("question review cards", async ({ page }) => {
        await mockApi(page, {
          lang,
          initialCase: baseCase(lang, {
            jurisdiction: "tamil_nadu",
            authority_name: f.authority.name,
            pio_address: f.authority.address,
            questions: reviewQuestions(lang),
          }),
        });
        await page.goto(`/${lang}/new?case=${CASE_ID}`);
        await expect(page.getByText(f.personal.suggestion)).toBeVisible();
        await expect(page.getByText(t.question.accepted, { exact: true })).toBeVisible();
        await shoot(page, "questions", lang, width, height);
      });

      test("describe and follow-up questions, with the no-personal-details hint", async ({ page }) => {
        await mockApi(page, { lang });
        await page.goto(`/${lang}/new`);
        const concern = page.getByRole("textbox", { name: t.flow.describe.label });
        await expect(page.getByText(t.flow.noPersonalDetails)).toBeVisible();
        await shoot(page, "describe", lang, width, height);

        await concern.fill(f.concern);
        await page.getByRole("button", { name: t.flow.describe.submit, exact: true }).click();
        await expect(page.getByRole("textbox", { name: f.followUps[0] })).toBeVisible();
        await expect(page.getByText(t.flow.noPersonalDetails)).toBeVisible();
        await shoot(page, "followups", lang, width, height);
      });

      test("reply letter read, first appeal ready", async ({ page }) => {
        await mockApi(page, { lang, initialCase: repliedCase(lang) });
        await page.goto(`/${lang}/cases/${CASE_ID}`);
        await page.getByRole("checkbox", { name: t.replyReader.consent }).check();
        await page.getByLabel(t.replyReader.fileLabel).setInputFiles({
          name: "reply-letter.png",
          mimeType: "image/png",
          buffer: SAMPLE_LETTER_PNG,
        });
        await page.getByRole("button", { name: t.replyReader.read, exact: true }).click();
        await expect(page.getByRole("list", { name: t.replyReader.points })).toBeVisible();
        await expect(page.getByRole("checkbox", { name: t.appeal.grounds.refused })).toBeChecked();
        await shoot(page, "appeal", lang, width, height);
      });

      test("case timeline", async ({ page }) => {
        await mockApi(page, { lang, initialCase: filedCase(lang) });
        await page.goto(`/${lang}/cases/${CASE_ID}`);
        await expect(page.getByText(t.timeline.deadlines.pio_reply)).toBeVisible();
        await expect(page.getByText(t.common.estimated).first()).toBeVisible();
        await shoot(page, "timeline", lang, width, height);
      });
    });
  }
}
