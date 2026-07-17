"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/apiClient";
import { parseSSEStream } from "@/lib/sse";
import type { Message, Source } from "@/lib/types";

function updateLast(
  messages: Message[],
  update: (m: Message) => Message,
): Message[] {
  if (messages.length === 0) return messages;
  return [...messages.slice(0, -1), update(messages[messages.length - 1])];
}

function placeholderMessage(role: Message["role"], content: string): Message {
  return {
    id: crypto.randomUUID(),
    role,
    content,
    sources: null,
    provider: null,
    model: null,
    latency_ms: null,
    status: "complete",
    created_at: new Date().toISOString(),
  };
}

export function useChatStream(
  conversationId: string,
  initialMessages: Message[],
  onSettled?: () => void,
) {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const send = useCallback(
    async (content: string) => {
      setError(null);
      setSending(true);
      setMessages((prev) => [
        ...prev,
        placeholderMessage("user", content),
        placeholderMessage("assistant", ""),
      ]);

      try {
        const stream = await api.sendMessage(conversationId, content);
        for await (const frame of parseSSEStream(stream)) {
          if (frame.event === "token") {
            const text = frame.data.text as string;
            setMessages((prev) =>
              updateLast(prev, (m) => ({ ...m, content: m.content + text })),
            );
          } else if (frame.event === "done") {
            const assistantId = frame.data.assistant_message_id as string;
            const sources = frame.data.sources as Source[];
            const latencyMs = frame.data.latency_ms as number;
            setMessages((prev) =>
              updateLast(prev, (m) => ({
                ...m,
                id: assistantId,
                sources,
                latency_ms: latencyMs,
                status: "complete",
              })),
            );
          } else if (frame.event === "error") {
            const assistantId = frame.data.assistant_message_id as string;
            const message = frame.data.message as string;
            setMessages((prev) =>
              updateLast(prev, (m) => ({
                ...m,
                id: assistantId,
                status: "error",
              })),
            );
            setError(message);
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "failed to send message");
      } finally {
        setSending(false);
        onSettled?.();
      }
    },
    [conversationId, onSettled],
  );

  return { messages, sending, error, send };
}
