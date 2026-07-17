import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { streamFrom } from "@/test-utils/stream";
import { useChatStream } from "./useChatStream";

describe("useChatStream", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("streams tokens into a live assistant message and finalizes on done", async () => {
    const stream = streamFrom([
      'event: token\ndata: {"text":"Hel"}\n\n',
      'event: token\ndata: {"text":"lo"}\n\n',
      'event: done\ndata: {"sources":[{"chunk_id":1,"document":"HP ENVY 6000","pages":"12","score":0.9}],"user_message_id":"u1","assistant_message_id":"a1","latency_ms":42}\n\n',
    ]);
    vi.mocked(fetch).mockResolvedValue(new Response(stream, { status: 200 }));

    const { result } = renderHook(() => useChatStream("conv-1", []));

    act(() => {
      void result.current.send("hi");
    });

    await waitFor(() => expect(result.current.messages).toHaveLength(2));
    expect(result.current.messages[0]).toMatchObject({
      role: "user",
      content: "hi",
    });

    await waitFor(() => expect(result.current.sending).toBe(false));

    expect(result.current.messages[1]).toMatchObject({
      id: "a1",
      role: "assistant",
      content: "Hello",
      status: "complete",
      latency_ms: 42,
      sources: [
        { chunk_id: 1, document: "HP ENVY 6000", pages: "12", score: 0.9 },
      ],
    });
  });

  it("marks the assistant message as errored on a terminal error event", async () => {
    const stream = streamFrom([
      'event: token\ndata: {"text":"partial"}\n\n',
      'event: error\ndata: {"message":"provider unreachable","user_message_id":"u1","assistant_message_id":"a1"}\n\n',
    ]);
    vi.mocked(fetch).mockResolvedValue(new Response(stream, { status: 200 }));

    const { result } = renderHook(() => useChatStream("conv-1", []));

    act(() => {
      void result.current.send("hi");
    });

    await waitFor(() => expect(result.current.sending).toBe(false));

    expect(result.current.messages[1]).toMatchObject({
      id: "a1",
      content: "partial",
      status: "error",
    });
    expect(result.current.error).toBe("provider unreachable");
  });

  it("starts from the conversation's existing history", () => {
    const existing = [
      {
        id: "m1",
        role: "user" as const,
        content: "earlier question",
        sources: null,
        provider: null,
        model: null,
        latency_ms: null,
        status: "complete",
        created_at: "2026-01-01T00:00:00Z",
      },
    ];

    const { result } = renderHook(() => useChatStream("conv-1", existing));

    expect(result.current.messages).toEqual(existing);
  });
});
