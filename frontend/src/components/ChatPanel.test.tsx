import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { streamFrom } from "@/test-utils/stream";
import { ChatPanel } from "./ChatPanel";

describe("ChatPanel", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends a message and renders the streamed answer with citations", async () => {
    const stream = streamFrom([
      'event: token\ndata: {"text":"Open the front door."}\n\n',
      'event: done\ndata: {"sources":[{"chunk_id":1,"document":"HP ENVY 6000 User Guide","pages":"12","score":0.9}],"user_message_id":"u1","assistant_message_id":"a1","latency_ms":10}\n\n',
    ]);
    vi.mocked(fetch).mockResolvedValue(new Response(stream, { status: 200 }));

    render(<ChatPanel conversationId="conv-1" initialMessages={[]} />);

    await userEvent.type(
      screen.getByRole("textbox"),
      "How do I replace the cartridge?{Enter}",
    );

    expect(
      screen.getByText("How do I replace the cartridge?"),
    ).toBeInTheDocument();
    expect(await screen.findByText("Open the front door.")).toBeInTheDocument();
    expect(
      screen.getByText("HP ENVY 6000 User Guide, p. 12"),
    ).toBeInTheDocument();
  });
});
