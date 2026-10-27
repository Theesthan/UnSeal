import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Timeline } from "./Timeline";
import { caseFixture } from "@/test/fixtures";
import { renderWithI18n } from "@/test/render";

const filedCase = caseFixture({
  status: "reply_due",
  authority_name: "Sample State University",
  filed_on: "2026-10-27",
  received_on: "2026-11-03",
  received_estimated: true,
  deadlines: [
    { kind: "pio_reply", due_on: "2026-12-03", due_at: null, estimated: true },
    { kind: "first_appeal", due_on: "2027-01-02", due_at: null, estimated: false },
  ],
});

function rowFor(text: string): HTMLElement {
  const row = screen.getByText(text).closest("li");
  if (!row) throw new Error(`no list item for ${text}`);
  return row;
}

describe("Timeline", () => {
  it("shows 'estimated' next to an estimated deadline and not next to an exact one", () => {
    renderWithI18n(<Timeline caseData={filedCase} />, "en");

    expect(
      within(rowFor("Reply due from the Public Information Officer")).getByText("estimated"),
    ).toBeInTheDocument();
    expect(
      within(rowFor("Last day to file the first appeal")).queryByText("estimated"),
    ).not.toBeInTheDocument();
  });

  it("puts each date in a <time> element and formats it in the UI language", () => {
    renderWithI18n(<Timeline caseData={filedCase} />, "ta");

    const time = within(rowFor("பொதுத் தகவல் அலுவலர் பதில் அளிக்க வேண்டிய கடைசி நாள்")).getByText(
      /டிசம்பர்/,
    );
    expect(time.tagName).toBe("TIME");
    expect(time).toHaveAttribute("datetime", "2026-12-03");
    expect(screen.getAllByText("தோராயமானது").length).toBeGreaterThan(0);
  });

  it("is an ordered list that marks the current step and labels every step in text", () => {
    renderWithI18n(<Timeline caseData={filedCase} />, "en");

    const list = screen.getByRole("list", { name: "Timeline" });
    expect(list.tagName).toBe("OL");
    const current = list.querySelector('[aria-current="step"]');
    expect(current).toHaveTextContent("Reply due");
    expect(current).toHaveTextContent("Now");
    expect(within(list).getAllByText("Done").length).toBe(2);
  });

  it("shows the receipt date with its own estimated label", () => {
    renderWithI18n(<Timeline caseData={filedCase} />, "en");

    const received = screen.getByText(/Received by the office on/).closest("li");
    expect(received).not.toBeNull();
    expect(within(received as HTMLElement).getByText("estimated")).toBeInTheDocument();
  });

  it("shows a clear fallback for an unknown status instead of a blank card", () => {
    renderWithI18n(<Timeline caseData={caseFixture({ status: "transferred" })} />, "en");

    expect(screen.getByRole("status")).toHaveTextContent("Status not recognised (transferred)");
    expect(screen.getByRole("list", { name: "Timeline" })).toBeInTheDocument();
  });
});
