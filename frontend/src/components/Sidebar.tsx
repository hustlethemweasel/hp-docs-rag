"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useConversationsContext } from "@/hooks/ConversationsContext";

export function Sidebar({ activeId }: { activeId?: string }) {
  const router = useRouter();
  const { conversations, loading, create, remove } = useConversationsContext();

  async function handleNew() {
    const summary = await create();
    router.push(`/c/${summary.id}`);
  }

  async function handleDelete(id: string) {
    await remove(id);
    if (id === activeId) router.push("/");
  }

  return (
    <aside className="flex h-full w-64 flex-col border-r border-black/10 bg-zinc-50 dark:border-white/10 dark:bg-zinc-950">
      <div className="p-3">
        <button
          onClick={handleNew}
          className="w-full rounded-md bg-foreground px-3 py-2 text-sm font-medium text-background transition-colors hover:bg-[#383838] dark:hover:bg-[#ccc]"
        >
          New conversation
        </button>
      </div>
      <nav className="flex-1 overflow-y-auto px-2 pb-3">
        {loading && conversations.length === 0 ? (
          <p className="px-2 py-1 text-sm text-zinc-500">Loading…</p>
        ) : conversations.length === 0 ? (
          <p className="px-2 py-1 text-sm text-zinc-500">
            No conversations yet.
          </p>
        ) : (
          <ul className="flex flex-col gap-1">
            {conversations.map((c) => (
              <li key={c.id} className="group flex items-center gap-1">
                <Link
                  href={`/c/${c.id}`}
                  aria-current={c.id === activeId ? "page" : undefined}
                  className={`min-w-0 flex-1 truncate rounded-md px-2 py-1.5 text-sm ${
                    c.id === activeId
                      ? "bg-black/[.06] font-medium dark:bg-white/[.1]"
                      : "hover:bg-black/[.04] dark:hover:bg-white/[.06]"
                  }`}
                >
                  {c.title || "New conversation"}
                </Link>
                <button
                  aria-label={`Delete ${c.title || "New conversation"}`}
                  onClick={() => handleDelete(c.id)}
                  className="shrink-0 rounded px-1.5 py-1 text-sm text-zinc-500 opacity-0 hover:bg-black/[.06] group-hover:opacity-100 dark:hover:bg-white/[.1]"
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
      </nav>
    </aside>
  );
}
