import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProjectsPage } from "./ProjectsPage";

describe("ProjectsPage", () => {
  it("introduces the durable projects workspace", () => {
    render(<ProjectsPage />);

    expect(screen.getByRole("heading", { name: "Projects" })).toBeDefined();
    expect(screen.getByText("Video forensics workspace")).toBeDefined();
  });
});
