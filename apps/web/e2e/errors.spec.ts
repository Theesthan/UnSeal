import { expect, test } from "@playwright/test";
import { en } from "../messages/en";
import { expectAccessible } from "./support/a11y";
import { CASE_ID, FIXTURES } from "./support/fixtures";
import { baseCase, mockApi, reviewQuestions, type Flag } from "./support/mock-api";

const f = FIXTURES.en;

test("busy (503): shows 'busy, try again' and the retry succeeds", async ({ page }) => {
  const api = await mockApi(page, { lang: "en", busyOnce: ["POST /cases/:id/intake"] });
  await page.goto("/en/new");
  await page.getByRole("textbox", { name: en.flow.describe.label }).fill(f.concern);
  await page.getByRole("button", { name: en.flow.describe.submit, exact: true }).click();

  const alert = page.getByRole("main").getByRole("alert");
  await expect(alert).toContainText(en.errors.busy);
  await expectAccessible(page);
  await alert.getByRole("button", { name: en.common.retry }).click();

  await expect(page.getByText(f.followUps[0])).toBeVisible();
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0);
  // The retry re-sent only the intake: the case was created once.
  expect(api.calls.filter((c) => c.method === "POST" && c.path === "/cases")).toHaveLength(1);
  expect(api.calls.filter((c) => c.path.endsWith("/intake"))).toHaveLength(2);
});

const readyToExport = {
  jurisdiction: "tamil_nadu",
  authority_name: f.authority.name,
  pio_address: f.authority.address,
  has_applicant: true,
  questions: reviewQuestions("en").map((q) => ({ ...q, accepted: true })),
};

test("blocked export: a blocking flag disables the download and points to the fix", async ({ page }) => {
  const flags: Flag[] = [
    { code: "missing_applicant_address", severity: "block", question: null, basis: null, under_challenge: false },
    { code: "personal_information", severity: "warn", question: 2, basis: "S. 8(1)(j)", under_challenge: true },
  ];
  await mockApi(page, { lang: "en", initialCase: readyToExport, flags });
  await page.goto(`/en/new?case=${CASE_ID}`);

  await expect(page.getByText(en.flags.codes.missing_applicant_address)).toBeVisible();
  await expect(page.getByText(en.flags.severity.block, { exact: true })).toBeVisible();
  await expect(page.getByText(en.flags.underChallenge)).toBeVisible();
  await expect(page.getByRole("button", { name: en.flow.check.download })).toBeDisabled();
  await expect(page.getByText(en.flow.check.blockedNote).first()).toBeVisible();
  await expectAccessible(page);

  await page.getByRole("button", { name: en.flow.check.editApplicant }).click();
  await expect(page.getByRole("heading", { name: en.flow.applicant.title })).toBeFocused();
});

test("blocked export: a 409 from the API shows its flags instead of a PDF", async ({ page }) => {
  const blocking: Flag[] = [
    { code: "missing_pio_address", severity: "block", question: null, basis: null, under_challenge: false },
  ];
  await mockApi(page, { lang: "en", initialCase: readyToExport, flags: [], applicationBlocked: blocking });
  await page.goto(`/en/new?case=${CASE_ID}`);

  await page.getByRole("textbox", { name: en.flow.check.placeLabel }).fill(f.place);
  await page.getByRole("button", { name: en.flow.check.download }).click();

  const alert = page.getByRole("main").getByRole("alert");
  await expect(alert).toContainText(en.errors.blocked);
  await expect(alert).toContainText(en.flags.codes.missing_pio_address);
  await expect(page.getByRole("button", { name: en.flow.check.download })).toBeDisabled();
  await expect(page.getByRole("button", { name: en.flow.check.editAuthority })).toBeVisible();
  await expectAccessible(page);
});

test("not found: an unknown case shows a way back, never a blank screen", async ({ page }) => {
  await mockApi(page, { lang: "en" });
  await page.goto(`/en/cases/${CASE_ID}`);
  await expect(page.getByRole("main").getByRole("alert")).toContainText(en.errors.not_found);
  await expect(page.getByRole("link", { name: en.errors.notFoundAction })).toBeVisible();
  await expectAccessible(page);
});

test("draft resume: a saved draft reopens at the first unfinished step", async ({ page }) => {
  await mockApi(page, {
    lang: "en",
    initialCase: baseCase("en", { ...readyToExport, has_applicant: false, questions: reviewQuestions("en") }),
  });
  await page.goto(`/en/new?case=${CASE_ID}`);
  await expect(page.getByRole("heading", { name: en.flow.questions.title, level: 2 })).toBeVisible();
  await expect(page.getByText(en.flow.questions.acceptAll)).toBeVisible();
});
