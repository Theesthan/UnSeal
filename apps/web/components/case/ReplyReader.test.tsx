import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ReplyReader } from "./ReplyReader";
import { CASE_ID, caseFixture } from "@/test/fixtures";
import { renderWithI18n } from "@/test/render";
import type { ReplyReading } from "@/lib/types";

const mocks = vi.hoisted(() => ({ readReply: vi.fn(), recordReply: vi.fn() }));
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  api: mocks,
}));

const replyDue = caseFixture({ status: "reply_due", filed_on: "2026-10-27" });
const reading: ReplyReading = {
  letter_date: "2026-11-18",
  items: [
    { number: 1, status: "given", section_cited: null },
    { number: 2, status: "refused", section_cited: "8(1)(j)" },
    { number: 3, status: "transferred", section_cited: null },
  ],
  fee_demanded: true,
  transferred_to: "Sample District Office",
  suggested_grounds: ["refused", "fee_demanded"],
};
const pdf = () => new File(["%PDF-1.7"], "reply.pdf", { type: "application/pdf" });

function setup(caseData = replyDue) {
  const onCaseUpdated = vi.fn();
  const onGrounds = vi.fn();
  renderWithI18n(
    <ReplyReader caseData={caseData} onCaseUpdated={onCaseUpdated} onGrounds={onGrounds} />,
  );
  return { onCaseUpdated, onGrounds, user: userEvent.setup({ applyAccept: false }) };
}

const CONSENT =
  "This letter has personal details. I agree that UnSeal sends it to the AI model only to read it. It is not stored.";

describe("ReplyReader", () => {
  beforeEach(() => {
    mocks.readReply.mockReset();
    mocks.recordReply.mockReset();
  });

  it("does not upload anything until the consent box is ticked", async () => {
    const { user } = setup();

    await user.upload(screen.getByLabelText("Photo or PDF of the reply letter"), pdf());
    await user.click(screen.getByRole("button", { name: "Read the letter" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Please tick the box to agree before the letter is read.");
    expect(mocks.readReply).not.toHaveBeenCalled();
  });

  it("refuses a file over 10 MB or of the wrong type before uploading", async () => {
    const { user } = setup();
    await user.click(screen.getByRole("checkbox", { name: CONSENT }));
    const input = screen.getByLabelText("Photo or PDF of the reply letter");

    const big = new File([new Uint8Array(10 * 1024 * 1024 + 1)], "big.pdf", { type: "application/pdf" });
    await user.upload(input, big);
    await user.click(screen.getByRole("button", { name: "Read the letter" }));
    expect(screen.getByRole("alert")).toHaveTextContent("larger than 10 MB");

    await user.upload(input, new File(["x"], "letter.docx", { type: "application/msword" }));
    await user.click(screen.getByRole("button", { name: "Read the letter" }));
    expect(screen.getByRole("alert")).toHaveTextContent("We could not open that file.");

    expect(mocks.readReply).not.toHaveBeenCalled();
  });

  it("shows each numbered point with its status and section, the fee and the transfer", async () => {
    mocks.readReply.mockResolvedValue(reading);
    const { user } = setup();
    const file = pdf();

    await user.click(screen.getByRole("checkbox", { name: CONSENT }));
    await user.upload(screen.getByLabelText("Photo or PDF of the reply letter"), file);
    await user.click(screen.getByRole("button", { name: "Read the letter" }));

    expect(mocks.readReply).toHaveBeenCalledWith(CASE_ID, file);
    const points = screen.getByRole("list", { name: "Answers to your questions" });
    const rows = within(points).getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("Point 1");
    expect(rows[0]).toHaveTextContent("Given");
    expect(rows[1]).toHaveTextContent("Refused");
    expect(rows[1]).toHaveTextContent("Section cited: 8(1)(j)");
    expect(rows[2]).toHaveTextContent("Transferred");
    expect(screen.getByText("The letter asks for a further fee.")).toBeInTheDocument();
    expect(screen.getByText("Transferred to: Sample District Office")).toBeInTheDocument();
    expect(screen.getByText("18 November 2026")).toBeInTheDocument();
  });

  it("asks when the letter arrived (defaulting to its date), records the reply, passes on the grounds", async () => {
    mocks.readReply.mockResolvedValue(reading);
    const replied = caseFixture({ ...replyDue, status: "replied", reply_received_on: "2026-11-20" });
    mocks.recordReply.mockResolvedValue(replied);
    const { user, onCaseUpdated, onGrounds } = setup();

    await user.click(screen.getByRole("checkbox", { name: CONSENT }));
    await user.upload(screen.getByLabelText("Photo or PDF of the reply letter"), pdf());
    await user.click(screen.getByRole("button", { name: "Read the letter" }));

    const date = screen.getByLabelText("Date you received the letter");
    expect(date).toHaveValue("2026-11-18");
    fireEvent.change(date, { target: { value: "2026-11-20" } });
    await user.click(screen.getByRole("button", { name: "Save and continue" }));

    expect(mocks.recordReply).toHaveBeenCalledWith(CASE_ID, "2026-11-20");
    expect(onCaseUpdated).toHaveBeenCalledWith(replied);
    expect(onGrounds).toHaveBeenCalledWith(["refused", "fee_demanded"]);
  });

  it("leaves the date empty when the letter date could not be read, and requires one", async () => {
    mocks.readReply.mockResolvedValue({ ...reading, letter_date: null });
    const { user } = setup();

    await user.click(screen.getByRole("checkbox", { name: CONSENT }));
    await user.upload(screen.getByLabelText("Photo or PDF of the reply letter"), pdf());
    await user.click(screen.getByRole("button", { name: "Read the letter" }));

    expect(screen.getByText("Not readable")).toBeInTheDocument();
    expect(screen.getByLabelText("Date you received the letter")).toHaveValue("");
    await user.click(screen.getByRole("button", { name: "Save and continue" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter the date you received the letter.");
    expect(mocks.recordReply).not.toHaveBeenCalled();
  });

  it("on a case already replied, skips the date and offers the appeal grounds at once", async () => {
    mocks.readReply.mockResolvedValue(reading);
    const { user, onGrounds } = setup(
      caseFixture({ status: "replied", reply_received_on: "2026-11-20" }),
    );

    await user.click(screen.getByRole("checkbox", { name: CONSENT }));
    await user.upload(screen.getByLabelText("Photo or PDF of the reply letter"), pdf());
    await user.click(screen.getByRole("button", { name: "Read the letter" }));

    expect(screen.queryByLabelText("Date you received the letter")).not.toBeInTheDocument();
    expect(onGrounds).toHaveBeenCalledWith(["refused", "fee_demanded"]);
  });
});
