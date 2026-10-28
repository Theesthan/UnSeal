import { describe, expect, it } from "vitest";
import { appealState, initialGrounds } from "./appeal";
import { caseFixture } from "@/test/fixtures";
import type { Deadline } from "./types";

const TODAY = "2026-12-10";
const NOW = new Date("2026-12-10T06:00:00Z");
const pio = (due_on: string | null, due_at: string | null = null): Deadline => ({
  kind: "pio_reply",
  due_on,
  due_at,
  estimated: false,
});
const firstAppeal = (due_on: string): Deadline => ({
  kind: "first_appeal",
  due_on,
  due_at: null,
  estimated: false,
});

describe("appealState", () => {
  it("is closed while the case is a draft, just filed, or still inside the PIO's time", () => {
    for (const status of ["draft", "filed", "closed"]) {
      expect(appealState(caseFixture({ status }), TODAY, NOW).canDraft).toBe(false);
    }
    const waiting = caseFixture({ status: "reply_due", deadlines: [pio("2026-12-20")] });
    expect(appealState(waiting, TODAY, NOW).canDraft).toBe(false);
  });

  it("opens once the PIO's day has passed, even before the status flips to deemed refused", () => {
    const passed = caseFixture({ status: "reply_due", deadlines: [pio("2026-12-09")] });
    const dueToday = caseFixture({ status: "reply_due", deadlines: [pio(TODAY)] });

    expect(appealState(passed, TODAY, NOW)).toMatchObject({ canDraft: true, canFile: true });
    expect(appealState(dueToday, TODAY, NOW).canDraft).toBe(false);
  });

  it("uses the timestamp for a 48-hour deadline", () => {
    const passed = caseFixture({ status: "reply_due", deadlines: [pio(null, "2026-12-10T05:00:00Z")] });
    const running = caseFixture({ status: "reply_due", deadlines: [pio(null, "2026-12-10T07:00:00Z")] });

    expect(appealState(passed, TODAY, NOW).canDraft).toBe(true);
    expect(appealState(running, TODAY, NOW).canDraft).toBe(false);
  });

  it("offers every ground on a deemed refusal, and drops 'no reply' once a reply date exists", () => {
    const refused = appealState(caseFixture({ status: "deemed_refused" }), TODAY, NOW);
    const replied = appealState(
      caseFixture({ status: "replied", reply_received_on: "2026-11-20" }),
      TODAY,
      NOW,
    );

    expect(refused.grounds).toEqual(["no_reply", "incomplete", "refused", "fee_demanded"]);
    expect(replied.grounds).toEqual(["incomplete", "refused", "fee_demanded"]);
    expect(replied).toMatchObject({ canDraft: true, canFile: true });
  });

  it("lets an appealed case download again but not file twice", () => {
    expect(appealState(caseFixture({ status: "appealed" }), TODAY, NOW)).toMatchObject({
      canDraft: true,
      canFile: false,
    });
  });

  it("is late only after the first-appeal day, not on it", () => {
    const onTheDay = caseFixture({ status: "replied", deadlines: [firstAppeal(TODAY)] });
    const after = caseFixture({ status: "replied", deadlines: [firstAppeal("2026-12-09")] });

    expect(appealState(onTheDay, TODAY, NOW).late).toBe(false);
    expect(appealState(after, TODAY, NOW).late).toBe(true);
  });
});

describe("initialGrounds", () => {
  it("preselects the reader's suggested grounds that this case allows", () => {
    expect(
      initialGrounds(["incomplete", "refused", "fee_demanded"], ["no_reply", "refused", "made_up"]),
    ).toEqual(["refused"]);
  });

  it("preselects 'no reply' for a deemed refusal when nothing was suggested", () => {
    expect(initialGrounds(["no_reply", "incomplete", "refused", "fee_demanded"], null)).toEqual([
      "no_reply",
    ]);
    expect(initialGrounds(["incomplete", "refused", "fee_demanded"], null)).toEqual([]);
  });
});
