import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ErrorNotice } from "./ErrorNotice";
import { ApiError } from "@/lib/api";
import { renderWithI18n } from "@/test/render";

describe("ErrorNotice", () => {
  it("shows 'busy, try again' with a retry button that re-runs the action", async () => {
    const onRetry = vi.fn();
    renderWithI18n(<ErrorNotice error={new ApiError("busy", 503)} onRetry={onRetry} />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "UnSeal is busy right now. Please try again in a moment.",
    );
    await userEvent.setup().click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("asks the user to rephrase on ask_user, with no retry button", () => {
    renderWithI18n(<ErrorNotice error={new ApiError("ask_user", 422)} onRetry={vi.fn()} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Please say it another way.");
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
  });

  it("links back to the start when there is no session", () => {
    renderWithI18n(<ErrorNotice error={new ApiError("no_session", 401)} />, "hi");

    expect(screen.getByRole("link", { name: "फिर से शुरू करें" })).toHaveAttribute("href", "/hi");
  });

  it("words a non-API error generically, never a blank box", () => {
    renderWithI18n(<ErrorNotice error={new Error("boom")} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Something went wrong. Please try again.");
  });
});
