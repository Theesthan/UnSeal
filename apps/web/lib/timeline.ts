// Turns a Case into the steps of the vertical timeline. It never computes a date: every date is
// read from the API (status, filed_on, received_on and the engine's deadlines).
import type { Case, Deadline } from "./types";

export type StageKey = "draft" | "filed" | "reply_due" | "reply" | "appealed" | "closed";
export type StageState = "done" | "current" | "upcoming";

export interface TimelineEntry {
  kind: "filed_on" | "received_on" | "reply_received_on" | "appeal_filed_on" | "deadline";
  deadlineKind?: string;
  date: string | null;
  at: string | null;
  estimated: boolean;
}

export interface TimelineStage {
  key: StageKey;
  /** Label key in messages.timeline.statuses */
  status: string;
  state: StageState;
  entries: TimelineEntry[];
}

export interface TimelineModel {
  stages: TimelineStage[];
  /** The raw status when it is not one this version knows; the UI shows a fallback. */
  unknownStatus: string | null;
}

const ORDER: StageKey[] = ["draft", "filed", "reply_due", "reply", "appealed", "closed"];

const STAGE_OF_STATUS: Record<string, StageKey> = {
  draft: "draft",
  filed: "filed",
  reply_due: "reply_due",
  replied: "reply",
  deemed_refused: "reply",
  appealed: "appealed",
  closed: "closed",
};

const STAGE_OF_DEADLINE: Record<string, StageKey> = {
  pio_reply: "reply_due",
  first_appeal: "reply",
  faa_decision: "appealed",
  second_appeal: "appealed",
};

function deadlineEntry(d: Deadline): TimelineEntry {
  return {
    kind: "deadline",
    deadlineKind: d.kind,
    date: d.due_on,
    at: d.due_at,
    estimated: d.estimated,
  };
}

function stageState(index: number, currentIndex: number): StageState {
  if (currentIndex < 0) return "upcoming";
  if (index < currentIndex) return "done";
  return index === currentIndex ? "current" : "upcoming";
}

function replyLabel(status: string): string {
  return status === "replied" || status === "deemed_refused" ? status : "reply_or_refused";
}

export function buildTimeline(c: Case): TimelineModel {
  const currentKey: StageKey | undefined = STAGE_OF_STATUS[c.status];
  const hasAppealDeadline =
    Boolean(c.appeal_filed_on) || c.deadlines.some((d) => STAGE_OF_DEADLINE[d.kind] === "appealed");
  const keys = ORDER.filter(
    (key) => !(key === "appealed" && c.status === "closed" && !hasAppealDeadline),
  );
  const currentIndex = currentKey ? keys.indexOf(currentKey) : -1;
  // An unknown deadline kind still shows, on the step the case is at (or the reply step).
  const fallbackStage: StageKey = currentKey ?? "reply_due";

  const stages = keys.map((key, index): TimelineStage => {
    const filingEntries: TimelineEntry[] =
      key !== "filed"
        ? []
        : [
            ...(c.filed_on
              ? [{ kind: "filed_on" as const, date: c.filed_on, at: null, estimated: false }]
              : []),
            ...(c.received_on
              ? [
                  {
                    kind: "received_on" as const,
                    date: c.received_on,
                    at: null,
                    estimated: c.received_estimated,
                  },
                ]
              : []),
          ];
    const dated = (kind: "reply_received_on" | "appeal_filed_on", date: string | null) =>
      date ? [{ kind, date, at: null, estimated: false }] : [];
    const eventEntries: TimelineEntry[] =
      key === "reply"
        ? dated("reply_received_on", c.reply_received_on)
        : key === "appealed"
          ? dated("appeal_filed_on", c.appeal_filed_on)
          : [];
    const deadlineEntries = c.deadlines
      .filter((d) => (STAGE_OF_DEADLINE[d.kind] ?? fallbackStage) === key)
      .map(deadlineEntry);
    return {
      key,
      status: key === "reply" ? replyLabel(c.status) : key,
      state: stageState(index, currentIndex),
      entries: [...filingEntries, ...eventEntries, ...deadlineEntries],
    };
  });

  return { stages, unknownStatus: currentKey ? null : c.status };
}
