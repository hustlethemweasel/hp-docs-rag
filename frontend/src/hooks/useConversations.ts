"use client";

import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/apiClient";
import type { ConversationSummary } from "@/lib/types";

export function useConversations() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const list = await api.listConversations();
      setConversations(list);
    } catch (err) {
      if (!(err instanceof ApiError)) throw err;
      // A failed list fetch shouldn't crash the app; the sidebar just keeps
      // showing whatever it last successfully loaded.
    }
  }, []);

  useEffect(() => {
    let active = true;
    // react-hooks/set-state-in-effect flags any setState reachable from an
    // effect body, even guarded async continuations; there's no data-fetching
    // library in scope, so fetch-on-mount is the intended pattern here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh().finally(() => {
      if (active) setLoading(false);
    });
    return () => {
      active = false;
    };
  }, [refresh]);

  const create = useCallback(async () => {
    const summary = await api.createConversation();
    setConversations((prev) => [summary, ...prev]);
    return summary;
  }, []);

  const remove = useCallback(async (id: string) => {
    await api.deleteConversation(id);
    setConversations((prev) => prev.filter((c) => c.id !== id));
  }, []);

  return { conversations, loading, refresh, create, remove };
}
