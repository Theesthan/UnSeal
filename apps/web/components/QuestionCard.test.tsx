import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { QuestionCard } from "./QuestionCard";
import { questionFixture } from "@/test/fixtures";
import { renderWithI18n } from "@/test/render";

function setup(overrides: Parameters<typeof questionFixture>[0] = {}, number = 1) {
  const onAccept = vi.fn().mockResolvedValue(undefined);
  const onSave = vi.fn().mockResolvedValue(undefined);
  const onRemove = vi.fn().mockResolvedValue(undefined);
  const question = questionFixture(overrides);
  renderWithI18n(
    <QuestionCard
      question={question}
      number={number}
      contentLang="en"
      onAccept={onAccept}
      onSave={onSave}
      onRemove={onRemove}
    />,
  );
  return { onAccept, onSave, onRemove, question, user: userEvent.setup() };
}

describe("QuestionCard", () => {
  it("shows the original, the rewrite, the records requested and the reason", () => {
    const { question } = setup();

    expect(screen.getByRole("heading", { name: "Question 1" })).toBeInTheDocument();
    expect(screen.getByText(question.original_text)).toBeInTheDocument();
    expect(screen.getByText(question.rewritten_text)).toBeInTheDocument();
    expect(screen.getByText("Certified copy of the evaluated answer script")).toBeInTheDocument();
    expect(screen.getByText("Mark list")).toBeInTheDocument();
    expect(screen.getByText(question.reason)).toBeInTheDocument();
  });

  it("names Accept with the question number and calls onAccept", async () => {
    const { onAccept, user } = setup({}, 2);

    await user.click(screen.getByRole("button", { name: "Accept question 2" }));

    expect(onAccept).toHaveBeenCalledTimes(1);
  });

  it("shows an Accepted label (text, not colour alone) once accepted", () => {
    setup({ accepted: true });

    expect(screen.getByText("Accepted")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Accept question 1" })).not.toBeInTheDocument();
  });

  it("edits: opens a field with the rewrite and saves the new wording", async () => {
    const { onSave, question, user } = setup();

    await user.click(screen.getByRole("button", { name: "Edit question 1" }));
    const field = screen.getByRole("textbox", { name: "Your wording for question 1" });
    expect(field).toHaveValue(question.rewritten_text);

    await user.clear(field);
    await user.type(field, "Provide the mark list for Mathematics II.");
    await user.click(screen.getByRole("button", { name: "Save question 1" }));

    expect(onSave).toHaveBeenCalledWith("Provide the mark list for Mathematics II.");
    expect(screen.queryByRole("textbox", { name: "Your wording for question 1" })).not.toBeInTheDocument();
  });

  it("cancel closes the editor without saving", async () => {
    const { onSave, user } = setup();

    await user.click(screen.getByRole("button", { name: "Edit question 1" }));
    await user.type(screen.getByRole("textbox", { name: "Your wording for question 1" }), " extra");
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onSave).not.toHaveBeenCalled();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("refuses to save an empty edit and says why", async () => {
    const { onSave, user } = setup();

    await user.click(screen.getByRole("button", { name: "Edit question 1" }));
    const field = screen.getByRole("textbox", { name: "Your wording for question 1" });
    await user.clear(field);
    await user.click(screen.getByRole("button", { name: "Save question 1" }));

    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("Write the question before saving.");
    expect(field).toHaveAttribute("aria-invalid", "true");
  });

  it("warns about another person's personal information and offers the suggestion", async () => {
    const suggestion = "Provide the number of students who applied for revaluation in April 2026.";
    const { onSave, user } = setup({
      personal_information: true,
      rewritten_text: "",
      suggestion,
    });

    expect(screen.getByText(/another person's personal information/)).toBeInTheDocument();
    expect(screen.getByText(suggestion)).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "Use this wording for question 1" }),
    );

    expect(onSave).toHaveBeenCalledWith(suggestion);
  });

  it("keeps the editor open with the user's text when saving fails", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn().mockResolvedValue(false);
    renderWithI18n(
      <QuestionCard
        question={questionFixture()}
        number={1}
        contentLang="en"
        onAccept={vi.fn()}
        onSave={onSave}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Edit question 1" }));
    const field = screen.getByRole("textbox", { name: "Your wording for question 1" });
    await user.clear(field);
    await user.type(field, "My own wording");
    await user.click(screen.getByRole("button", { name: "Save question 1" }));

    expect(onSave).toHaveBeenCalledWith("My own wording");
    expect(screen.getByRole("textbox", { name: "Your wording for question 1" })).toHaveValue(
      "My own wording",
    );
  });

  it("removes a question by its numbered button", async () => {
    const { onRemove, user } = setup({}, 3);

    await user.click(screen.getByRole("button", { name: "Remove question 3" }));

    expect(onRemove).toHaveBeenCalledTimes(1);
  });

  it("tags question text with its own language when it differs from the page", () => {
    renderWithI18n(
      <QuestionCard
        question={questionFixture({ original_text: "என் மதிப்பெண் ஏன் குறைவு?" })}
        number={1}
        contentLang="ta"
        onAccept={vi.fn()}
        onSave={vi.fn()}
      />,
      "en",
    );

    expect(screen.getByText("என் மதிப்பெண் ஏன் குறைவு?").closest("[lang]")).toHaveAttribute(
      "lang",
      "ta",
    );
  });
});
