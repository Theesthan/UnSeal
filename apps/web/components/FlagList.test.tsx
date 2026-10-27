import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FlagList } from "./FlagList";
import { renderWithI18n } from "@/test/render";
import { ta } from "@/messages/ta";
import type { ValidationFlag } from "@/lib/types";

const warn: ValidationFlag = {
  code: "personal_information",
  severity: "warn",
  question: 0,
  basis: "S. 8(1)(j)",
  under_challenge: true,
};
const block: ValidationFlag = {
  code: "missing_applicant_address",
  severity: "block",
  question: null,
  basis: null,
  under_challenge: false,
};

describe("FlagList", () => {
  it("words each flag in the user's language with a text severity label", () => {
    renderWithI18n(<FlagList flags={[warn, block]} />, "ta");

    expect(screen.getByText(ta.flags.codes.missing_applicant_address)).toBeInTheDocument();
    expect(screen.getByText(ta.flags.codes.personal_information)).toBeInTheDocument();
    expect(screen.getByText(ta.flags.severity.block)).toBeInTheDocument();
    expect(screen.getByText(ta.flags.severity.warn)).toBeInTheDocument();
  });

  it("names the question (1-based), shows the basis and the under-challenge note", () => {
    renderWithI18n(<FlagList flags={[warn]} />, "ta");

    expect(screen.getByText("கேள்வி 1")).toBeInTheDocument();
    expect(screen.getByText("அடிப்படை: S. 8(1)(j)")).toBeInTheDocument();
    expect(screen.getByText(ta.flags.underChallenge)).toBeInTheDocument();
  });

  it("lists blocking flags first", () => {
    renderWithI18n(<FlagList flags={[warn, block]} />, "en");

    const items = within(screen.getByRole("list")).getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Must fix");
    expect(items[1]).toHaveTextContent("Worth checking");
  });

  it("words an unknown flag code generically instead of crashing", () => {
    renderWithI18n(
      <FlagList flags={[{ ...block, code: "brand_new_check", severity: "warn" }]} />,
      "en",
    );

    expect(screen.getByText("Please check this item (brand_new_check).")).toBeInTheDocument();
  });

  it("says so when there are no flags", () => {
    renderWithI18n(<FlagList flags={[]} />, "en");

    expect(screen.getByText("No problems found.")).toBeInTheDocument();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });
});
