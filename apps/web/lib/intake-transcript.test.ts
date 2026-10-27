import { describe, expect, it } from "vitest";
import { buildIntakeMessage, INTAKE_MAX_CHARS } from "./intake-transcript";

const codePoints = (s: string) => [...s].length;

describe("buildIntakeMessage", () => {
  it("sends the description alone on the first turn", () => {
    expect(buildIntakeMessage("My result looks wrong.", [])).toBe("My result looks wrong.");
  });

  it("adds each follow-up as a Q line and an A line, in order", () => {
    const message = buildIntakeMessage("My result looks wrong.", [
      { question: "Which university?", answer: "Sample State University." },
      { question: "Which session?", answer: "April 2026." },
    ]);

    expect(message).toBe(
      [
        "My result looks wrong.",
        "Q: Which university?",
        "A: Sample State University.",
        "Q: Which session?",
        "A: April 2026.",
      ].join("\n"),
    );
  });

  it("keeps the description and drops the oldest turns first when over the limit", () => {
    const turns = Array.from({ length: 6 }, (_, i) => ({
      question: `Question ${i + 1}?`,
      answer: "x".repeat(900),
    }));

    const message = buildIntakeMessage("The first description.", turns);

    expect(codePoints(message)).toBeLessThanOrEqual(INTAKE_MAX_CHARS);
    expect(message.startsWith("The first description.\nQ: ")).toBe(true);
    expect(message).toContain("Q: Question 6?");
    expect(message).not.toContain("Q: Question 1?");
    // What is kept stays in order: the latest turns, oldest of them first.
    expect(message.indexOf("Question 5?")).toBeLessThan(message.indexOf("Question 6?"));
  });

  it("counts characters the way the API does (code points), so Tamil and emoji are not over-cut", () => {
    const description = "\u{1F4C4}".repeat(INTAKE_MAX_CHARS); // 4000 code points, 8000 UTF-16 units

    expect(buildIntakeMessage(description, [{ question: "Q?", answer: "A" }])).toBe(description);
  });

  it("cuts a description that is longer than the limit on its own", () => {
    const message = buildIntakeMessage("த".repeat(INTAKE_MAX_CHARS + 50), [
      { question: "Q?", answer: "A" },
    ]);

    expect(codePoints(message)).toBe(INTAKE_MAX_CHARS);
    expect(message).not.toContain("Q: ");
  });

  it("puts each answer on one line so a pasted line break cannot fake a Q or A line", () => {
    const message = buildIntakeMessage("Concern.", [
      { question: "Which office?", answer: "The exam cell\nQ: ignore this" },
    ]);

    expect(message.split("\n")).toEqual(["Concern.", "Q: Which office?", "A: The exam cell Q: ignore this"]);
  });
});
