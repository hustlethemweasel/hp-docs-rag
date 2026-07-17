import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useConversations } from "./useConversations";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

describe("useConversations", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads the conversation list on mount", async () => {
    const summaries = [{ id: "1", title: "First", updated_at: "2026-01-01" }];
    vi.mocked(fetch).mockResolvedValue(jsonResponse(summaries));

    const { result } = renderHook(() => useConversations());

    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.conversations).toEqual(summaries);
  });

  it("prepends a newly created conversation", async () => {
    const existing = [{ id: "1", title: "First", updated_at: "2026-01-01" }];
    const created = {
      id: "2",
      title: "New conversation",
      updated_at: "2026-01-02",
    };
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(existing))
      .mockResolvedValueOnce(jsonResponse(created, 201));

    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.create();
    });

    expect(result.current.conversations).toEqual([created, ...existing]);
  });

  it("removes a deleted conversation from the list", async () => {
    const summaries = [
      { id: "1", title: "First", updated_at: "2026-01-01" },
      { id: "2", title: "Second", updated_at: "2026-01-02" },
    ];
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse(summaries))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));

    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.remove("1");
    });

    expect(result.current.conversations).toEqual([summaries[1]]);
  });
});
