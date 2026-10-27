// The intake conversation lives in the browser: the API keeps no intake history, so every turn
// sends all of it (docs/api.md, POST /cases/{id}/intake). The format is the first description,
// then for each follow-up one "Q: <question>" line and one "A: <answer>" line.

export interface IntakeTurn {
  question: string;
  answer: string;
}

/** The API's limit on `message`, counted in characters (code points, as Python's len does). */
export const INTAKE_MAX_CHARS = 4000;

const length = (s: string): number => [...s].length;
const oneLine = (s: string): string => s.replace(/\s*[\r\n]+\s*/g, " ").trim();
const turnText = (t: IntakeTurn): string => `Q: ${oneLine(t.question)}\nA: ${oneLine(t.answer)}`;

/**
 * Build the intake message. When it would be too long, the first description is always kept
 * and the oldest follow-up turns are dropped first; a description longer than the limit on its
 * own is cut to the limit.
 */
export function buildIntakeMessage(
  description: string,
  turns: IntakeTurn[],
  max: number = INTAKE_MAX_CHARS,
): string {
  const head = description.trim();
  if (length(head) >= max) return [...head].slice(0, max).join("");

  let used = length(head);
  const kept: string[] = [];
  for (let i = turns.length - 1; i >= 0; i -= 1) {
    const text = turnText(turns[i]);
    const cost = length(text) + 1; // the line break before it
    if (used + cost > max) break;
    kept.unshift(text);
    used += cost;
  }
  return [head, ...kept].join("\n");
}
