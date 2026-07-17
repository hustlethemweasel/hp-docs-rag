import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConversationsProvider } from "@/hooks/ConversationsContext";
import { Sidebar } from "./Sidebar";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function renderSidebar(activeId?: string) {
  return render(
    <ConversationsProvider>
      <Sidebar activeId={activeId} />
    </ConversationsProvider>,
  );
}

describe("Sidebar", () => {
  beforeEach(() => {
    localStorage.clear();
    push.mockClear();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("lists conversations and highlights the active one", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse([
        { id: "1", title: "First chat", updated_at: "2026-01-01" },
        { id: "2", title: "Second chat", updated_at: "2026-01-02" },
      ]),
    );

    renderSidebar("2");

    expect(await screen.findByText("First chat")).toBeInTheDocument();
    const activeLink = screen.getByRole("link", { name: "Second chat" });
    expect(activeLink).toHaveAttribute("aria-current", "page");
  });

  it("creates a conversation and navigates to it", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse([]))
      .mockResolvedValueOnce(
        jsonResponse(
          { id: "new-id", title: "New conversation", updated_at: "2026-01-03" },
          201,
        ),
      );

    renderSidebar();
    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));

    await userEvent.click(
      screen.getByRole("button", { name: /new conversation/i }),
    );

    await waitFor(() => expect(push).toHaveBeenCalledWith("/c/new-id"));
  });

  it("deletes a conversation and navigates home if it was active", async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(
        jsonResponse([
          { id: "1", title: "First chat", updated_at: "2026-01-01" },
        ]),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    renderSidebar("1");
    await screen.findByText("First chat");

    await userEvent.click(
      screen.getByRole("button", { name: /delete first chat/i }),
    );

    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
    expect(screen.queryByText("First chat")).not.toBeInTheDocument();
  });
});
