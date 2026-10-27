import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppealPanel } from "./AppealPanel";
import { CASE_ID, caseFixture } from "@/test/fixtures";
import { renderWithI18n } from "@/test/render";
import type { Case } from "@/lib/types";

const mocks = vi.hoisted(() => ({
  api: { downloadAppeal: vi.fn(), recordAppealFiling: vi.fn() },
  saveBlob: vi.fn(),
}));
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  api: mocks.api,
}));
vi.mock("@/lib/download", () => ({ saveBlob: mocks.saveBlob }));

const TODAY = "2026-12-10";
const refused = caseFixture({
  status: "deemed_refused",
  authority_name: "Sample State University",
  pio_address: "Exam Cell, Sample State University, Sample Town",
  deadlines: [{ kind: "first_appeal", due_on: "2027-01-08", due_at: null, estimated: false }],
});

const GROUND = {
  no_reply: "No reply in time",
  incomplete: "The reply is incomplete or not what I asked for",
  refused: "The request was refused",
  fee: "A fee was demanded that should not be payable",
};

function setup(caseData: Case = refused, suggested: string[] | null = null, today = TODAY) {
  const onCaseUpdated = vi.fn();
  renderWithI18n(
    <AppealPanel
      caseData={caseData}
      suggestedGrounds={suggested}
      onCaseUpdated={onCaseUpdated}
      today={today}
    />,
  );
  return { onCaseUpdated, user: userEvent.setup() };
}

describe("AppealPanel", () => {
  beforeEach(() => {
    mocks.api.downloadAppeal.mockReset();
    mocks.api.recordAppealFiling.mockReset();
    mocks.saveBlob.mockReset();
  });

  it("offers all four grounds on a deemed refusal, with 'no reply' ticked", () => {
    setup();

    expect(screen.getByRole("checkbox", { name: GROUND.no_reply })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: GROUND.incomplete })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: GROUND.refused })).not.toBeChecked();
    expect(screen.getByRole("checkbox", { name: GROUND.fee })).not.toBeChecked();
  });

  it("hides 'no reply' once a reply date exists and ticks the reader's suggestions", () => {
    setup(caseFixture({ ...refused, status: "replied", reply_received_on: "2026-11-20" }), [
      "no_reply",
      "refused",
    ]);

    expect(screen.queryByRole("checkbox", { name: GROUND.no_reply })).not.toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: GROUND.refused })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: GROUND.incomplete })).not.toBeChecked();
  });

  it("addresses the appellate authority of the same office and prefills the PIO's address to check", () => {
    setup();

    // Two runs in two languages (UI and case), so match the whole paragraph text.
    expect(
      screen.getByText(
        (_, el) => el?.tagName === "P" && el.textContent === "First Appellate Authority, Sample State University",
      ),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Address of the First Appellate Authority")).toHaveValue(
      "Exam Cell, Sample State University, Sample Town",
    );
  });

  it("shows the delay reason only after the first-appeal deadline", () => {
    setup(refused, null, "2027-01-08");
    expect(screen.queryByLabelText("Reason for the delay")).not.toBeInTheDocument();
  });

  it("asks for a delay reason when the appeal is late", () => {
    setup(refused, null, "2027-01-09");
    expect(screen.getByLabelText("Reason for the delay")).toBeInTheDocument();
  });

  it("needs a ground and a confirmed address before it downloads", async () => {
    const { user } = setup();

    await user.click(screen.getByRole("checkbox", { name: GROUND.no_reply }));
    await user.click(screen.getByRole("button", { name: "Download first appeal (PDF)" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Choose at least one reason.");

    await user.click(screen.getByRole("checkbox", { name: GROUND.incomplete }));
    await user.click(screen.getByRole("button", { name: "Download first appeal (PDF)" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Please confirm that you have checked the address.");
    expect(mocks.api.downloadAppeal).not.toHaveBeenCalled();
  });

  it("sends the grounds, address, details and place, and saves the PDF", async () => {
    const blob = new Blob(["%PDF"], { type: "application/pdf" });
    mocks.api.downloadAppeal.mockResolvedValue(blob);
    const { user } = setup();

    await user.click(screen.getByRole("checkbox", { name: GROUND.fee }));
    await user.click(screen.getByRole("checkbox", { name: "I have checked this address." }));
    await user.type(screen.getByLabelText("Anything else to add (optional)"), "No reply at all.");
    await user.type(screen.getByLabelText("Place (town or city)"), "Sample Town");
    await user.click(screen.getByRole("button", { name: "Download first appeal (PDF)" }));

    expect(mocks.api.downloadAppeal).toHaveBeenCalledWith(CASE_ID, {
      grounds: ["no_reply", "fee_demanded"],
      faa_address: "Exam Cell, Sample State University, Sample Town",
      details: "No reply at all.",
      delay_reason: "",
      place: "Sample Town",
    });
    expect(mocks.saveBlob).toHaveBeenCalledWith(blob, "unseal-first-appeal.pdf");
    expect(screen.getByText(/Your first appeal is downloaded/)).toBeInTheDocument();
  });

  it("records the appeal filing with today's date and no received date by default", async () => {
    const appealed = caseFixture({ ...refused, status: "appealed", appeal_filed_on: TODAY });
    mocks.api.recordAppealFiling.mockResolvedValue(appealed);
    const { user, onCaseUpdated } = setup();

    expect(screen.getByLabelText("Date you filed the appeal")).toHaveValue(TODAY);
    await user.click(screen.getByRole("button", { name: "I have filed the appeal" }));

    expect(mocks.api.recordAppealFiling).toHaveBeenCalledWith(CASE_ID, {
      filed_on: TODAY,
      received_on: null,
    });
    expect(onCaseUpdated).toHaveBeenCalledWith(appealed);
  });

  it("lets an appealed case download again but not file a second time", () => {
    setup(caseFixture({ ...refused, status: "appealed", appeal_filed_on: "2026-11-25" }));

    expect(screen.getByRole("button", { name: "Download first appeal (PDF)" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "I have filed the appeal" })).not.toBeInTheDocument();
    expect(screen.getByText(/Your appeal was filed on 25 November 2026/)).toBeInTheDocument();
  });
});
