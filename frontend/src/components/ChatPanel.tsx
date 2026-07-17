"use client";

import { useChatStream } from "@/hooks/useChatStream";
import type { Message } from "@/lib/types";
import { Composer } from "./Composer";
import { MessageBubble } from "./MessageBubble";

export function ChatPanel({
  conversationId,
  initialMessages,
  onMessageSettled,
}: {
  conversationId: string;
  initialMessages: Message[];
  onMessageSettled?: () => void;
}) {
  const { messages, sending, error, send } = useChatStream(
    conversationId,
    initialMessages,
    onMessageSettled,
  );

  return (
    <div className="flex h-full flex-1 flex-col">
      <div className="flex-1 overflow-y-auto px-4 py-6">
        {messages.length === 0 ? (
          <p className="mx-auto max-w-3xl text-sm text-zinc-500">
            Ask a question about the HP ENVY 6000 or OMEN 17.3&quot; guides to
            get started.
          </p>
        ) : (
          <div className="mx-auto flex max-w-3xl flex-col gap-4">
            {messages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}
          </div>
        )}
      </div>
      {error && (
        <p className="mx-auto w-full max-w-3xl px-4 pb-1 text-xs text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
      <div className="mx-auto w-full max-w-3xl">
        <Composer onSend={send} disabled={sending} />
      </div>
    </div>
  );
}
