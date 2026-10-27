import AxeBuilder from "@axe-core/playwright";
import { expect, type Page } from "@playwright/test";

/** Run axe (WCAG 2.0 and 2.1, A and AA) and fail on any serious or critical violation. */
export async function expectAccessible(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
    .analyze();
  const blocking = results.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id} (${v.impact}): ${v.help} at ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`);
  expect(blocking, `axe on ${page.url()}`).toEqual([]);
}

/** The page body must never scroll sideways (responsive-design skill). */
export async function expectNoHorizontalScroll(page: Page): Promise<void> {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow, `horizontal overflow on ${page.url()}`).toBeLessThanOrEqual(0);
}
