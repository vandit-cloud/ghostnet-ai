import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PriorityBadge, ReviewStatusBadge, UncertaintyLabel } from "@/components/Badges";

describe("PriorityBadge", () => {
  it("renders the priority label", () => {
    render(<PriorityBadge priority="critical" />);
    expect(screen.getByText("critical")).toBeInTheDocument();
  });
});

describe("ReviewStatusBadge", () => {
  it("renders a human-readable label for accepted_artificial", () => {
    render(<ReviewStatusBadge status="accepted_artificial" />);
    expect(screen.getByText("Accepted — Artificial")).toBeInTheDocument();
  });
});

describe("UncertaintyLabel", () => {
  it("renders a placeholder when uncertainty is null", () => {
    render(<UncertaintyLabel level={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders the uncertainty level", () => {
    render(<UncertaintyLabel level="low" />);
    expect(screen.getByText("low")).toBeInTheDocument();
  });
});
