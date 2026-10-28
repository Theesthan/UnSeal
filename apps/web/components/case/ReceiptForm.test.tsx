import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ReceiptForm } from "./ReceiptForm";
import { CASE_ID, caseFixture } from "@/test/fixtures";
import { renderWithI18n } from "@/test/render";

const mocks = vi.hoisted(() => ({ setReceipt: vi.fn() }));
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  api: mocks,
}));

const estimated = caseFixture({
  status: "reply_due",
  filed_on: "2026-10-27",
  received_on: "2026-11-03",
  received_estimated: true,
});

describe("ReceiptForm", () => {
  beforeEach(() => mocks.setReceipt.mockReset());

  it("saves the actual receipt date and hands back the updated case", async () => {
    const updated = caseFixture({ ...estimated, received_on: "2026-10-30", received_estimated: false });
    mocks.setReceipt.mockResolvedValue(updated);
    const onUpdated = vi.fn();
    renderWithI18n(<ReceiptForm caseData={estimated} onUpdated={onUpdated} />);

    expect(screen.getByRole("heading", { name: "When did the office receive it?" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Date the office received it"), {
      target: { value: "2026-10-30" },
    });
    await userEvent.setup().click(screen.getByRole("button", { name: "Save received date" }));

    expect(mocks.setReceipt).toHaveBeenCalledWith(CASE_ID, "2026-10-30");
    expect(onUpdated).toHaveBeenCalledWith(updated);
    expect(screen.getByRole("status")).toHaveTextContent("Your deadlines now count from this date.");
  });

  it("does not allow a date before the filing date or after today", () => {
    renderWithI18n(<ReceiptForm caseData={estimated} onUpdated={vi.fn()} />);

    expect(screen.getByLabelText("Date the office received it")).toHaveAttribute("min", "2026-10-27");
    expect(screen.getByLabelText("Date the office received it")).toHaveAttribute("max");
  });

  it("asks for a date before saving", async () => {
    renderWithI18n(<ReceiptForm caseData={estimated} onUpdated={vi.fn()} />);

    await userEvent.setup().click(screen.getByRole("button", { name: "Save received date" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Enter the date the office received it.");
    expect(mocks.setReceipt).not.toHaveBeenCalled();
  });
});
