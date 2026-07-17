import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Message } from "@/lib/types";
import { MessageBubble } from "./MessageBubble";

function message(overrides: Partial<Message>): Message {
  return {
    id: "1",
    role: "assistant",
    content: "The cartridge is on the left.",
    sources: null,
    provider: null,
    model: null,
    latency_ms: null,
    status: "complete",
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("MessageBubble", () => {
  it("renders assistant content with its citations", () => {
    render(
      <MessageBubble
        message={message({
          sources: [
            {
              chunk_id: 1,
              document: "HP ENVY 6000 User Guide",
              pages: "12",
              score: 0.9,
            },
          ],
        })}
      />,
    );

    expect(
      screen.getByText("The cartridge is on the left."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("HP ENVY 6000 User Guide, p. 12"),
    ).toBeInTheDocument();
  });

  it("shows a retry affordance for an errored message", () => {
    render(
      <MessageBubble
        message={message({ status: "error", content: "partial" })}
      />,
    );

    expect(screen.getByText(/couldn't finish this reply/i)).toBeInTheDocument();
  });

  it("does not render citations for a user message", () => {
    render(
      <MessageBubble
        message={message({
          role: "user",
          content: "How do I replace the cartridge?",
          sources: [
            {
              chunk_id: 1,
              document: "HP ENVY 6000 User Guide",
              pages: "12",
              score: 0.9,
            },
          ],
        })}
      />,
    );

    expect(screen.queryByText(/p\. 12/)).not.toBeInTheDocument();
  });
});
