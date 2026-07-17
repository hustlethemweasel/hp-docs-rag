import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConversationsProvider } from "@/hooks/ConversationsContext";
import { ConversationView } from "./ConversationView";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function renderConversationView(conversationId: string) {
  return render(
    <ConversationsProvider>
      <ConversationView conversationId={conversationId} />
    </ConversationsProvider>,
  );
}

describe("ConversationView", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows a loading state, then the chat panel once history loads", async () => {
    // The sidebar's ConversationsProvider fetches concurrently with this
    // view's own conversation-detail fetch, so each call needs a fresh
    // Response instance rather than one shared, already-consumed body.
    vi.mocked(fetch).mockImplementation(() =>
      Promise.resolve(
        jsonResponse({
          id: "conv-1",
          title: "Cartridge replacement",
          messages: [
            {
              id: "m1",
              role: "user",
              content: "How do I replace the cartridge?",
              sources: null,
              provider: null,
              model: null,
              latency_ms: null,
              status: "complete",
              created_at: "2026-01-01T00:00:00Z",
            },
          ],
        }),
      ),
    );

    renderConversationView("conv-1");

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
    expect(
      await screen.findByText("How do I replace the cartridge?"),
    ).toBeInTheDocument();
  });

  it("shows a not-found state for a missing or foreign conversation", async () => {
    vi.mocked(fetch).mockImplementation(() =>
      Promise.resolve(new Response("conversation not found", { status: 404 })),
    );

    renderConversationView("missing");

    expect(
      await screen.findByText(/doesn't exist, or isn't yours/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /start a new one/i }),
    ).toHaveAttribute("href", "/");
  });
});
