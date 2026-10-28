import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { EMPTY_TRANSCRIPT, StepDescribe, type Transcript } from "./StepDescribe";
import { CASE_ID, caseFixture } from "@/test/fixtures";
import { renderWithI18n } from "@/test/render";
import type { Case, IntakeResponse } from "@/lib/types";

const mocks = vi.hoisted(() => ({ createCase: vi.fn(), intake: vi.fn() }));
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  api: mocks,
}));

function response(followUps: string[], ready = false): IntakeResponse {
  return {
    intake: {
      jurisdiction_hint: "tamil_nadu",
      authority: null,
      time_period: null,
      records_wanted: [],
      delivery_mode: "unknown",
      bpl: "unknown",
      follow_up_questions: followUps,
      ready_to_draft: ready,
    },
    authorities: [],
  };
}

function Harness() {
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [intake, setIntake] = useState<IntakeResponse | null>(null);
  const [transcript, setTranscript] = useState<Transcript>(EMPTY_TRANSCRIPT);
  return (
    <StepDescribe
      caseData={caseData}
      intake={intake}
      transcript={transcript}
      onTranscript={setTranscript}
      onCreated={setCaseData}
      onIntake={setIntake}
      onNext={vi.fn()}
    />
  );
}

describe("StepDescribe", () => {
  it("keeps the conversation in the browser and sends all of it on every turn", async () => {
    mocks.createCase.mockResolvedValue(caseFixture());
    mocks.intake
      .mockResolvedValueOnce(response(["Which university?", "Which session?"]))
      .mockResolvedValueOnce(response(["Post or in person?"]))
      .mockResolvedValueOnce(response([], true));
    const user = userEvent.setup();
    renderWithI18n(<Harness />);

    await user.type(screen.getByRole("textbox", { name: "Your concern" }), "My result looks wrong.");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(mocks.intake).toHaveBeenLastCalledWith(CASE_ID, "My result looks wrong.");

    // One answer per follow-up question; a blank answer is left out.
    await user.type(await screen.findByRole("textbox", { name: "Which university?" }), "Sample State University");
    await user.click(screen.getByRole("button", { name: "Send answer" }));
    expect(mocks.intake).toHaveBeenLastCalledWith(
      CASE_ID,
      "My result looks wrong.\nQ: Which university?\nA: Sample State University",
    );

    await user.type(await screen.findByRole("textbox", { name: "Post or in person?" }), "By post");
    await user.click(screen.getByRole("button", { name: "Send answer" }));
    expect(mocks.intake).toHaveBeenLastCalledWith(
      CASE_ID,
      [
        "My result looks wrong.",
        "Q: Which university?",
        "A: Sample State University",
        "Q: Post or in person?",
        "A: By post",
      ].join("\n"),
    );
    expect(mocks.createCase).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("We have enough to draft your application.")).toBeInTheDocument();
  });

  it("tells the user, on the concern and on every answer, not to write their name, address or phone", async () => {
    const hint =
      "Do not write your name, address or phone number here. You add those later, and they are never sent to the AI.";
    mocks.createCase.mockResolvedValue(caseFixture());
    mocks.intake.mockReset().mockResolvedValueOnce(response(["Which university?", "Which session?"]));
    const user = userEvent.setup();
    renderWithI18n(<Harness />);

    const concern = screen.getByRole("textbox", { name: "Your concern" });
    expect(concern).toHaveAccessibleDescription(expect.stringContaining(hint));
    expect(screen.getByText(hint)).toBeVisible();

    await user.type(concern, "Concern.");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    for (const name of ["Which university?", "Which session?"]) {
      expect(await screen.findByRole("textbox", { name })).toHaveAccessibleDescription(
        expect.stringContaining(hint),
      );
    }
  });

  it("asks for at least one answer before sending", async () => {
    mocks.createCase.mockResolvedValue(caseFixture());
    mocks.intake.mockReset().mockResolvedValueOnce(response(["Which university?"]));
    const user = userEvent.setup();
    renderWithI18n(<Harness />);

    await user.type(screen.getByRole("textbox", { name: "Your concern" }), "Concern.");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await screen.findByRole("textbox", { name: "Which university?" });
    await user.click(screen.getByRole("button", { name: "Send answer" }));

    expect(screen.getByRole("alert")).toHaveTextContent("Please answer at least one question, or continue without answering.");
    expect(mocks.intake).toHaveBeenCalledTimes(1);
  });
});
