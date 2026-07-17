import { getUserId } from "./userId";
import type { ConversationDetail, ConversationSummary } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function apiFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "X-User-Id": getUserId(),
      ...init.headers,
    },
  });
  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }
  return res;
}

async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await apiFetch(path, init);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  listConversations: () => apiJson<ConversationSummary[]>("/api/conversations"),

  createConversation: () =>
    apiJson<ConversationSummary>("/api/conversations", { method: "POST" }),

  getConversation: (id: string) =>
    apiJson<ConversationDetail>(`/api/conversations/${id}`),

  deleteConversation: (id: string) =>
    apiJson<void>(`/api/conversations/${id}`, { method: "DELETE" }),

  async sendMessage(
    conversationId: string,
    content: string,
  ): Promise<ReadableStream<Uint8Array>> {
    const res = await apiFetch(
      `/api/conversations/${conversationId}/messages`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      },
    );
    if (!res.body) {
      throw new Error("response has no body to stream");
    }
    return res.body;
  },
};
