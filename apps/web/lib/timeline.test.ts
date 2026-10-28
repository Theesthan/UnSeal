import { describe, expect, it } from "vitest";
import { buildTimeline } from "./timeline";
import { caseFixture } from "@/test/fixtures";

const keys = (m: ReturnType<typeof buildTimeline>) => m.stages.map((s) => s.key);
const states = (m: ReturnType<typeof buildTimeline>) => m.stages.map((s) => s.state);

describe("buildTimeline", () => {
  it("starts a draft at the first step", () => {
    const m = buildTimeline(caseFixture({ status: "draft" }));

    expect(keys(m)).toEqual(["draft", "filed", "reply_due", "reply", "appealed", "closed"]);
    expect(states(m)).toEqual(["current", "upcoming", "upcoming", "upcoming", "upcoming", "upcoming"]);
    expect(m.unknownStatus).toBeNull();
  });

  it("attaches the filing and receipt dates to 'filed' and the PIO deadline to 'reply due'", () => {
    const m = buildTimeline(
      caseFixture({
        status: "reply_due",
        filed_on: "2026-10-27",
        received_on: "2026-11-03",
        received_estimated: true,
        deadlines: [{ kind: "pio_reply", due_on: "2026-12-03", due_at: null, estimated: true }],
      }),
    );

    expect(states(m).slice(0, 3)).toEqual(["done", "done", "current"]);
    expect(m.stages[1].entries).toEqual([
      { kind: "filed_on", date: "2026-10-27", at: null, estimated: false },
      { kind: "received_on", date: "2026-11-03", at: null, estimated: true },
    ]);
    expect(m.stages[2].entries).toEqual([
      { kind: "deadline", deadlineKind: "pio_reply", date: "2026-12-03", at: null, estimated: true },
    ]);
  });

  it("names the reply step by what happened: replied or deemed refused", () => {
    expect(buildTimeline(caseFixture({ status: "replied" })).stages[3].status).toBe("replied");
    expect(buildTimeline(caseFixture({ status: "deemed_refused" })).stages[3].status).toBe(
      "deemed_refused",
    );
    expect(buildTimeline(caseFixture({ status: "reply_due" })).stages[3].status).toBe(
      "reply_or_refused",
    );
  });

  it("shows the reply date on the reply step and the appeal filing date on 'appealed'", () => {
    const m = buildTimeline(
      caseFixture({
        status: "appealed",
        reply_received_on: "2026-11-20",
        appeal_filed_on: "2026-11-25",
        deadlines: [{ kind: "faa_decision", due_on: "2026-12-25", due_at: null, estimated: false }],
      }),
    );

    expect(m.stages[3].entries[0]).toEqual({
      kind: "reply_received_on",
      date: "2026-11-20",
      at: null,
      estimated: false,
    });
    expect(m.stages[4].entries.map((e) => e.kind)).toEqual(["appeal_filed_on", "deadline"]);
  });

  it("keeps the first-appeal deadline on the reply step and appeal deadlines on 'appealed'", () => {
    const m = buildTimeline(
      caseFixture({
        status: "appealed",
        deadlines: [
          { kind: "first_appeal", due_on: "2027-01-02", due_at: null, estimated: false },
          { kind: "faa_decision", due_on: "2027-02-01", due_at: null, estimated: false },
          { kind: "second_appeal", due_on: "2027-05-02", due_at: null, estimated: false },
        ],
      }),
    );

    expect(m.stages[3].entries.map((e) => e.deadlineKind)).toEqual(["first_appeal"]);
    expect(m.stages[4].entries.map((e) => e.deadlineKind)).toEqual(["faa_decision", "second_appeal"]);
    expect(m.stages[4].state).toBe("current");
  });

  it("keeps a 48-hour deadline's timestamp", () => {
    const m = buildTimeline(
      caseFixture({
        status: "reply_due",
        life_liberty: true,
        deadlines: [{ kind: "pio_reply", due_on: null, due_at: "2026-10-29T10:00:00Z", estimated: false }],
      }),
    );

    expect(m.stages[2].entries[0]).toMatchObject({ date: null, at: "2026-10-29T10:00:00Z" });
  });

  it("leaves out the appeal step on a closed case that never went to appeal", () => {
    const m = buildTimeline(caseFixture({ status: "closed" }));

    expect(keys(m)).toEqual(["draft", "filed", "reply_due", "reply", "closed"]);
    expect(states(m)).toEqual(["done", "done", "done", "done", "current"]);
  });

  it("shows an unknown deadline kind on the current step rather than dropping it", () => {
    const m = buildTimeline(
      caseFixture({
        status: "reply_due",
        deadlines: [{ kind: "transfer_notice", due_on: "2026-11-01", due_at: null, estimated: false }],
      }),
    );

    expect(m.stages[2].entries.map((e) => e.deadlineKind)).toEqual(["transfer_notice"]);
  });

  it("reports an unknown status and marks no step as current", () => {
    const m = buildTimeline(caseFixture({ status: "transferred" }));

    expect(m.unknownStatus).toBe("transferred");
    expect(states(m).includes("current")).toBe(false);
  });
});
