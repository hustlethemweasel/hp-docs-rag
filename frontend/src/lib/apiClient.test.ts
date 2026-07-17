import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./apiClient";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

describe("apiClient", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("lists conversations with the X-User-Id header", async () => {
    const summaries = [{ id: "1", title: "t", updated_at: "2026-01-01" }];
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify(summaries), { status: 200 }),
    );

    const result = await api.listConversations();

    expect(result).toEqual(summaries);
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/conversations");
    const headers = new Headers(init?.headers);
    expect(headers.get("X-User-Id")).toMatch(UUID_PATTERN);
  });

  it("creates a conversation with a POST request", async () => {
    const summary = {
      id: "1",
      title: "New conversation",
      updated_at: "2026-01-01",
    };
    vi.mocked(fetch).mockResolvedValue(
      new Response(JSON.stringify(summary), { status: 201 }),
    );

    const result = await api.createConversation();

    expect(result).toEqual(summary);
    const [, init] = vi.mocked(fetch).mock.calls[0];
    expect(init?.method).toBe("POST");
  });

  it("deletes a conversation and tolerates an empty 204 body", async () => {
    vi.mocked(fetch).mockResolvedValue(new Response(null, { status: 204 }));

    await expect(api.deleteConversation("1")).resolves.toBeUndefined();
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/conversations/1");
    expect(init?.method).toBe("DELETE");
  });

  it("throws an ApiError when the response is not ok", async () => {
    vi.mocked(fetch).mockResolvedValue(
      new Response("conversation not found", { status: 404 }),
    );

    await expect(api.getConversation("missing")).rejects.toMatchObject(
      new ApiError(404, "conversation not found"),
    );
  });

  it("sends a chat message as JSON and returns the response body stream", async () => {
    const body = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.close();
      },
    });
    vi.mocked(fetch).mockResolvedValue(new Response(body, { status: 200 }));

    const stream = await api.sendMessage("conv-1", "hello");

    expect(stream).toBeInstanceOf(ReadableStream);
    const [url, init] = vi.mocked(fetch).mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/conversations/conv-1/messages");
    expect(init?.method).toBe("POST");
    const headers = new Headers(init?.headers);
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(init?.body).toBe(JSON.stringify({ content: "hello" }));
  });
});
