import { expect, test, type Page } from "@playwright/test";
import { en } from "../messages/en";
import { hi } from "../messages/hi";
import { format } from "../lib/i18n-core";
import { expectAccessible, expectNoHorizontalScroll } from "./support/a11y";
import { CASE_ID } from "./support/fixtures";
import { filedCase, mockApi, overdueCase, SAMPLE_LETTER_PNG } from "./support/mock-api";

const main = (page: Page) => page.getByRole("main");

test("receipt date: the actual day replaces the estimate (Hindi)", async ({ page }) => {
  const api = await mockApi(page, {
    lang: "hi",
    initialCase: filedCase("hi", { filed_on: "2026-10-20", received_on: "2026-10-27" }),
  });
  await page.goto(`/hi/cases/${CASE_ID}`);
  // The deadline entry is a list item nested inside its timeline step.
  const replyRow = page.locator("ol li ul li").filter({ hasText: hi.timeline.deadlines.pio_reply });
  await expect(replyRow.getByText(hi.common.estimated, { exact: true })).toBeVisible();
  await expectAccessible(page);

  await page.getByLabel(hi.caseDetail.receiptLabel).fill("2026-10-23");
  await page.getByRole("button", { name: hi.caseDetail.receiptSave }).click();

  await expect(main(page).getByRole("status")).toContainText(hi.caseDetail.receiptSaved);
  await expect(replyRow.getByText(hi.common.estimated, { exact: true })).toHaveCount(0);
  expect(api.calls.find((c) => c.path.endsWith("/receipt"))).toMatchObject({
    method: "PUT",
    body: { received_on: "2026-10-23" },
  });
  await expectAccessible(page);
});

test("reply letter to first appeal: read, confirm the date, appeal, file (Hindi)", async ({ page }) => {
  const api = await mockApi(page, { lang: "hi", initialCase: overdueCase("hi") });
  await page.goto(`/hi/cases/${CASE_ID}`);
  await expectNoHorizontalScroll(page);

  // Consent first: nothing is uploaded without it.
  await page.getByLabel(hi.replyReader.fileLabel).setInputFiles({
    name: "reply-letter.png",
    mimeType: "image/png",
    buffer: SAMPLE_LETTER_PNG,
  });
  await page.getByRole("button", { name: hi.replyReader.read, exact: true }).click();
  await expect(main(page).getByRole("alert")).toHaveText(hi.errors.consent_required);
  expect(api.calls.filter((c) => c.path.endsWith("/reply/read"))).toHaveLength(0);

  await page.getByRole("checkbox", { name: hi.replyReader.consent }).check();
  await page.getByRole("button", { name: hi.replyReader.read, exact: true }).click();
  const points = page.getByRole("list", { name: hi.replyReader.points });
  await expect(points.getByRole("listitem")).toHaveCount(3);
  await expect(points.getByRole("listitem").nth(1)).toContainText(hi.replyReader.statuses.refused);
  await expect(points.getByRole("listitem").nth(1)).toContainText("8(1)(j)");
  await expect(page.getByText(format(hi.replyReader.transferredTo, { office: "नमूना ज़िला कार्यालय" }))).toBeVisible();
  const read = api.calls.find((c) => c.path.endsWith("/reply/read"));
  expect(read?.raw).toMatch(/name="consent"\r\n\r\ntrue/);
  expect(read?.raw).toMatch(/name="file"; filename="reply-letter.png"/);
  await expectAccessible(page);

  // The letter's date is only a default: the user says when it arrived.
  const received = page.getByLabel(hi.replyReader.receivedLabel);
  await expect(received).toHaveValue("2026-10-15");
  await received.fill("2026-10-17");
  await page.getByRole("button", { name: hi.replyReader.save }).click();
  await expect(page.getByText(hi.replyReader.appealNext)).toBeVisible();
  expect(api.calls.find((c) => c.path.endsWith("/reply"))?.body).toEqual({ received_on: "2026-10-17" });

  // The first appeal opens with the reader's grounds ticked and no "no reply" option.
  const appeal = page.locator("#first-appeal");
  await expect(appeal.getByRole("heading", { name: hi.appeal.title })).toBeFocused();
  await expect(appeal.getByRole("checkbox", { name: hi.appeal.grounds.incomplete })).toBeChecked();
  await expect(appeal.getByRole("checkbox", { name: hi.appeal.grounds.refused })).toBeChecked();
  await expect(appeal.getByRole("checkbox", { name: hi.appeal.grounds.no_reply })).toHaveCount(0);
  await expect(appeal.getByLabel(hi.appeal.delayLabel)).toHaveCount(0);
  await expectAccessible(page);

  await appeal.getByRole("checkbox", { name: hi.appeal.faaConfirm }).check();
  await appeal.getByLabel(hi.flow.check.placeLabel).fill("नमूना नगर");
  const download = page.waitForEvent("download");
  await appeal.getByRole("button", { name: hi.appeal.download }).click();
  expect((await download).suggestedFilename()).toBe("unseal-first-appeal.pdf");
  expect(api.calls.find((c) => c.path.endsWith("/appeal"))?.body).toMatchObject({
    grounds: ["incomplete", "refused"],
    delay_reason: "",
    place: "नमूना नगर",
  });

  await appeal.getByRole("button", { name: hi.appeal.fileSubmit }).click();
  await expect(page.getByText(hi.timeline.deadlines.faa_decision)).toBeVisible();
  await expect(page.getByText(hi.timeline.deadlines.second_appeal)).toBeVisible();
  await expect(page.getByRole("button", { name: hi.appeal.fileSubmit })).toHaveCount(0);
  await expectNoHorizontalScroll(page);
  await expectAccessible(page);

  for (const call of api.calls.filter((c) => c.method !== "GET")) expect(call.origin).toBe("http://localhost:3100");
});

test("deemed refusal: the appeal opens with 'no reply' ticked", async ({ page }) => {
  const api = await mockApi(page, { lang: "en", initialCase: overdueCase("en", { status: "deemed_refused" }) });
  await page.goto(`/en/cases/${CASE_ID}`);
  const appeal = page.locator("#first-appeal");
  await expect(appeal.getByRole("checkbox", { name: en.appeal.grounds.no_reply })).toBeChecked();

  // The address must be confirmed before the PDF is made.
  await appeal.getByRole("button", { name: en.appeal.download }).click();
  await expect(appeal.getByRole("alert")).toHaveText(en.appeal.faaConfirmRequired);
  await appeal.getByRole("checkbox", { name: en.appeal.faaConfirm }).check();
  const download = page.waitForEvent("download");
  await appeal.getByRole("button", { name: en.appeal.download }).click();
  expect((await download).suggestedFilename()).toBe("unseal-first-appeal.pdf");
  expect(api.calls.find((c) => c.path.endsWith("/appeal"))?.body).toMatchObject({ grounds: ["no_reply"] });
  await expectAccessible(page);
});

test("the API's wrong_status is worded in the user's language", async ({ page }) => {
  // The case moved on elsewhere (for example on Telegram), so the API refuses the read.
  await mockApi(page, { lang: "en", initialCase: filedCase("en") });
  await page.route("**/api/cases/*/reply/read", (route) =>
    route.fulfill({ status: 409, contentType: "application/json", body: '{"error":"wrong_status","detail":null}' }),
  );
  await page.goto(`/en/cases/${CASE_ID}`);
  await page.getByRole("checkbox", { name: en.replyReader.consent }).check();
  await page.getByLabel(en.replyReader.fileLabel).setInputFiles({
    name: "reply-letter.png",
    mimeType: "image/png",
    buffer: SAMPLE_LETTER_PNG,
  });
  await page.getByRole("button", { name: en.replyReader.read, exact: true }).click();
  await expect(main(page).getByRole("alert")).toContainText(en.errors.wrong_status);
  await expectAccessible(page);
});

test("dashboard: a 48-hour deadline shows its time", async ({ page }) => {
  await mockApi(page, {
    lang: "en",
    initialCase: filedCase("en", {
      life_liberty: true,
      deadlines: [{ kind: "pio_reply", due_on: null, due_at: "2026-10-29T10:00:00Z", estimated: false }],
    }),
  });
  await page.goto("/en/cases");
  const time = page.locator('time[datetime="2026-10-29T10:00:00Z"]');
  await expect(time).toContainText("29 October 2026");
  await expect(time).toContainText("3:30");
  await expectAccessible(page);
});
