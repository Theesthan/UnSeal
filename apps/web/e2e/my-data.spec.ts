import { expect, test } from "@playwright/test";
import { en } from "../messages/en";
import { hi } from "../messages/hi";
import { expectAccessible } from "./support/a11y";
import { filedCase, mockApi } from "./support/mock-api";

test("delete my data: needs a confirm step, then removes everything", async ({ page }) => {
  const api = await mockApi(page, { lang: "en", initialCase: filedCase("en") });
  await page.goto("/en/my-data");
  await expectAccessible(page);

  await page.getByRole("button", { name: en.myData.deleteButton, exact: true }).click();
  const confirm = page.getByRole("group", { name: en.myData.deleteConfirm });
  await expect(confirm).toBeFocused();
  expect(api.calls.filter((c) => c.method === "DELETE")).toHaveLength(0);
  await expectAccessible(page);

  // Cancel returns focus and deletes nothing.
  await confirm.getByRole("button", { name: en.common.cancel }).click();
  await expect(page.getByRole("button", { name: en.myData.deleteButton, exact: true })).toBeFocused();
  expect(api.calls.filter((c) => c.method === "DELETE")).toHaveLength(0);

  await page.getByRole("button", { name: en.myData.deleteButton, exact: true }).click();
  await page.getByRole("button", { name: en.myData.deleteYes }).click();
  await expect(page.getByText(en.myData.deleted)).toBeVisible();
  expect(api.calls.filter((c) => c.method === "DELETE").map((c) => c.path)).toEqual(["/me"]);
  expect(api.current()).toBeNull();
  await expectAccessible(page);
});

test("export my data: confirm, then a JSON file with a generic name", async ({ page }) => {
  await mockApi(page, { lang: "hi", initialCase: filedCase("hi") });
  await page.goto("/hi/my-data");
  await page.getByRole("button", { name: hi.myData.exportButton, exact: true }).click();
  await expect(page.getByText(hi.myData.exportConfirm)).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: hi.myData.exportYes }).click();
  expect((await download).suggestedFilename()).toBe("unseal-my-data.json");
  await expect(page.getByText(hi.myData.exported)).toBeVisible();
});
