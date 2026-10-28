import { expect, test } from "@playwright/test";
import { ta } from "../messages/ta";
import { format } from "../lib/i18n-core";
import { expectAccessible, expectNoHorizontalScroll } from "./support/a11y";
import { CASE_ID, FIXTURES } from "./support/fixtures";
import { APP_ORIGIN, mockApi } from "./support/mock-api";

const f = FIXTURES.ta;

test("Tamil: consent, describe, office, questions, details, PDF, filing, timeline", async ({ page }) => {
  const api = await mockApi(page, { lang: "ta" });

  // Landing: consent is required before any session starts.
  await page.goto("/ta");
  await expect(page.locator("html")).toHaveAttribute("lang", "ta");
  await expect(page.getByText("Prepared with UnSeal. Not legal advice.")).toBeVisible();
  await expectAccessible(page);
  await page.getByRole("button", { name: ta.landing.start, exact: true }).click();
  await expect(page.getByRole("main").getByRole("alert")).toHaveText(ta.consent.agreeRequired);
  expect(api.calls.filter((c) => c.path === "/session")).toHaveLength(0);

  await page.getByRole("checkbox", { name: ta.consent.agree }).check();
  await page.getByRole("button", { name: ta.landing.start, exact: true }).click();
  await expect(page).toHaveURL(/\/ta\/new$/);
  expect(api.calls.find((c) => c.path === "/session")?.body).toEqual({ language: "ta" });

  // Describe (FR-1), then the follow-up questions.
  await page.getByRole("textbox", { name: ta.flow.describe.label }).fill(f.concern);
  await page.getByRole("button", { name: ta.flow.describe.submit, exact: true }).click();
  await expect(page.getByText(f.followUps[0])).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`/ta/new\\?case=${CASE_ID}$`));
  await expectAccessible(page);
  await expect(page.getByText(ta.flow.noPersonalDetails)).toBeVisible();
  await page.getByRole("textbox", { name: f.followUps[0] }).fill(f.answer);
  await page.getByRole("button", { name: ta.flow.followUp.send, exact: true }).click();
  await expect(page.getByText(ta.flow.followUp.ready)).toBeVisible();
  // The API keeps no intake history: the second call carries the whole conversation.
  expect(api.intakeMessages).toEqual([f.concern, `${f.concern}\nQ: ${f.followUps[0]}\nA: ${f.answer}`]);
  await page.getByRole("button", { name: ta.common.continue, exact: true }).click();

  // Office and PIO address (FR-4): pick the suggested office, confirm the address.
  await expect(page.getByRole("heading", { name: ta.flow.authority.title })).toBeFocused();
  await page.getByRole("radio", { name: new RegExp(f.authority.name_ta) }).check();
  await expect(page.getByRole("textbox", { name: ta.flow.authority.addressLabel })).toHaveValue(
    f.authority.address,
  );
  await expect(page.getByRole("radio", { name: ta.jurisdictions.tamil_nadu })).toBeChecked();
  await expectAccessible(page);
  await page.getByRole("button", { name: ta.flow.authority.confirm, exact: true }).click();

  // Questions (FR-2): the rewrite shows as a card; accept it.
  await expect(page.getByRole("heading", { name: ta.flow.questions.title, level: 2 })).toBeVisible();
  await page.getByRole("textbox", { name: ta.flow.questions.addLabel }).fill(f.question.original);
  await page.getByRole("button", { name: ta.flow.questions.addButton, exact: true }).click();
  await expect(page.getByText(f.question.rewritten)).toBeVisible();
  await expect(page.getByText(f.question.reason)).toBeVisible();
  await expect(page.getByRole("button", { name: ta.common.continue, exact: true })).toBeDisabled();
  await expectAccessible(page);
  await page.getByRole("button", { name: format(ta.question.acceptLabel, { n: 1 }) }).click();
  await expect(page.getByText(ta.question.accepted, { exact: true })).toBeVisible();
  await page.getByRole("button", { name: ta.common.continue, exact: true }).click();

  // Applicant details: sent once, never shown back.
  await page.getByRole("textbox", { name: ta.flow.applicant.name }).fill(f.applicant.name);
  await page.getByRole("textbox", { name: ta.flow.applicant.address }).fill(f.applicant.address);
  await expectAccessible(page);
  await page.getByRole("button", { name: ta.flow.applicant.save, exact: true }).click();
  await expect(page.getByText(ta.flow.applicant.saved)).toBeVisible();
  await expect(page.getByText(f.applicant.name)).toHaveCount(0);
  await page.getByRole("button", { name: ta.common.continue, exact: true }).click();

  // Check (FR-3), download (FR-5) and the filing checklist from GET /rules.
  await expect(page.getByText(ta.flow.check.noFlags)).toBeVisible();
  await expect(page.getByText(format(ta.checklist.fee, { fee: 10 }))).toBeVisible();
  await expect(page.getByRole("listitem").filter({ hasText: ta.paymentModes.court_fee_stamp })).toBeVisible();
  await expect(page.getByText(ta.checklist.confirm)).toBeVisible();
  await expectAccessible(page);
  await page.getByRole("textbox", { name: ta.flow.check.placeLabel }).fill(f.place);
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: ta.flow.check.download }).click();
  expect((await download).suggestedFilename()).toBe("unseal-application.pdf");
  await expect(page.getByText(ta.flow.check.downloaded)).toBeVisible();
  expect(api.calls.find((c) => c.path.endsWith("/application"))?.body).toEqual({
    payment_mode: "cash",
    place: f.place,
  });
  await page.getByRole("button", { name: ta.flow.check.next, exact: true }).click();

  // File (FR-6): the API computes deadlines; the timeline shows them, estimated.
  await expect(page.getByRole("heading", { name: ta.flow.file.title })).toBeFocused();
  await page.getByRole("button", { name: ta.flow.file.submit }).click();
  await expect(page).toHaveURL(new RegExp(`/ta/cases/${CASE_ID}$`));
  await expect(page.getByText(ta.timeline.deadlines.pio_reply)).toBeVisible();
  await expect(page.getByText(ta.common.estimated).first()).toBeVisible();
  await expectNoHorizontalScroll(page);
  await expectAccessible(page);

  // Contract checks: writes carry the browser's Origin; no personal data in any API URL.
  const writes = api.calls.filter((c) => c.method !== "GET");
  expect(writes.length).toBeGreaterThan(5);
  for (const call of writes) expect(call.origin, `${call.method} ${call.path}`).toBe(APP_ORIGIN);
  for (const call of api.calls) {
    expect(decodeURIComponent(call.path + call.search)).not.toContain(f.applicant.name);
  }
  expect(page.url()).not.toContain(encodeURIComponent(f.applicant.name));
});
