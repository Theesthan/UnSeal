import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CaseList } from "./CaseList";
import { CASE_ID } from "@/test/fixtures";
import { renderWithI18n } from "@/test/render";

const mocks = vi.hoisted(() => ({ listCases: vi.fn() }));
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  api: mocks,
}));

describe("CaseList", () => {
  it("shows a 48-hour deadline with its time in India", async () => {
    mocks.listCases.mockResolvedValue([
      {
        id: CASE_ID,
        status: "reply_due",
        authority_name: "Sample District Hospital",
        next_deadline: { kind: "pio_reply", due_on: null, due_at: "2026-10-29T10:00:00Z", estimated: false },
        created_at: "2026-10-27T10:00:00Z",
      },
    ]);
    renderWithI18n(<CaseList />);

    const time = await screen.findByText(/29 October 2026.*3:30/);
    expect(time.tagName).toBe("TIME");
    expect(time).toHaveAttribute("datetime", "2026-10-29T10:00:00Z");
    expect(screen.queryByText("No deadlines yet")).not.toBeInTheDocument();
  });
});
