// When the first appeal (FR-10, S. 19(1)) may be drafted and which grounds apply. This compares
// today with dates the API already computed; it never computes a deadline itself. The API makes
// the same checks and answers 409 wrong_status or 400 invalid_grounds if the two ever disagree.
import type { Case, Deadline } from "./types";

export const GROUNDS = ["no_reply", "incomplete", "refused", "fee_demanded"] as const;
export type Ground = (typeof GROUNDS)[number];

export interface AppealState {
  /** The appeal PDF may be made (or made again once appealed). */
  canDraft: boolean;
  /** "I have filed the appeal" may be recorded. */
  canFile: boolean;
  /** Today is past the last day for the first appeal: ask for a reason for the delay. */
  late: boolean;
  grounds: Ground[];
}

const ANSWERED = new Set(["replied", "deemed_refused"]);

function find(deadlines: Deadline[], kind: string): Deadline | undefined {
  return deadlines.find((d) => d.kind === kind);
}

/** True once the day (or, on the 48-hour track, the moment) of a deadline has passed. */
function passed(d: Deadline | undefined, today: string, now: Date): boolean {
  if (!d) return false;
  if (d.due_at) return new Date(d.due_at).getTime() < now.getTime();
  return d.due_on !== null && d.due_on < today; // ISO dates compare as strings
}

export function appealState(
  c: Pick<Case, "status" | "deadlines" | "reply_received_on">,
  today: string,
  now: Date = new Date(),
): AppealState {
  const pioDayPassed = c.status === "reply_due" && passed(find(c.deadlines, "pio_reply"), today, now);
  const open = ANSWERED.has(c.status) || pioDayPassed;
  const appealed = c.status === "appealed";
  return {
    canDraft: open || appealed,
    canFile: open,
    late: passed(find(c.deadlines, "first_appeal"), today, now),
    grounds: GROUNDS.filter((g) => !(g === "no_reply" && c.reply_received_on)),
  };
}

/** Grounds ticked at first: the reply reader's suggestions, or "no reply" for a deemed refusal. */
export function initialGrounds(available: Ground[], suggested: string[] | null): Ground[] {
  if (suggested) return available.filter((g) => suggested.includes(g));
  return available.includes("no_reply") ? ["no_reply"] : [];
}
