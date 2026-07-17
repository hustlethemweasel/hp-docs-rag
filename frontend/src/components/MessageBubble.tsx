import type { Message } from "@/lib/types";
import { Citations } from "./Citations";

export function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-2xl rounded-2xl px-4 py-2.5 ${
          isUser
            ? "bg-foreground text-background"
            : "bg-black/[.04] dark:bg-white/[.06]"
        }`}
      >
        <p className="whitespace-pre-wrap text-sm leading-relaxed">
          {message.content}
        </p>
        {message.status === "error" && (
          <p className="mt-2 text-xs text-red-600 dark:text-red-400">
            Couldn&apos;t finish this reply — the provider failed mid-stream.
            Try sending your question again.
          </p>
        )}
        {!isUser && <Citations sources={message.sources} />}
      </div>
    </div>
  );
}
