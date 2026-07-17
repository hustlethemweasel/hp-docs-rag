import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Citations } from "./Citations";

describe("Citations", () => {
  it("renders nothing for an empty or missing source list", () => {
    const { container: empty } = render(<Citations sources={[]} />);
    expect(empty).toBeEmptyDOMElement();

    const { container: missing } = render(<Citations sources={null} />);
    expect(missing).toBeEmptyDOMElement();
  });

  it("renders a document + page label per source", () => {
    render(
      <Citations
        sources={[
          {
            chunk_id: 1,
            document: "HP ENVY 6000 User Guide",
            pages: "12",
            score: 0.91,
          },
          {
            chunk_id: 2,
            document: "OMEN 17.3 Maintenance Guide",
            pages: "40-41",
            score: 0.8,
          },
        ]}
      />,
    );

    expect(
      screen.getByText("HP ENVY 6000 User Guide, p. 12"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("OMEN 17.3 Maintenance Guide, p. 40-41"),
    ).toBeInTheDocument();
  });
});
