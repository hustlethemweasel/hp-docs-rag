"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/apiClient";
import type { ConversationDetail } from "@/lib/types";
import { ChatPanel } from "./ChatPanel";

export function ConversationView({
  conversationId,
}: {
  conversationId: string;
}) {
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    let active = true;

    api
      .getConversation(conversationId)
      .then((loaded) => {
        if (active) setDetail(loaded);
      })
      .catch((err: unknown) => {
        if (active && err instanceof ApiError && err.status === 404) {
          setNotFound(true);
        }
      });

    return () => {
      active = false;
    };
  }, [conversationId]);

  if (notFound) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 text-sm text-zinc-500">
        <p>This conversation doesn&apos;t exist, or isn&apos;t yours.</p>
        <Link href="/" className="underline">
          Start a new one
        </Link>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-zinc-500">
        Loading…
      </div>
    );
  }

  return (
    <ChatPanel
      conversationId={conversationId}
      initialMessages={detail.messages}
    />
  );
}
