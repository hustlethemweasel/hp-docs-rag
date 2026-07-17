import type { Source } from "@/lib/types";

export function Citations({ sources }: { sources: Source[] | null }) {
  if (!sources || sources.length === 0) return null;

  return (
    <ul className="mt-2 flex flex-wrap gap-2">
      {sources.map((source) => (
        <li
          key={source.chunk_id}
          className="rounded-full border border-black/10 px-2.5 py-1 text-xs text-zinc-600 dark:border-white/15 dark:text-zinc-400"
        >
          {source.document}, p. {source.pages}
        </li>
      ))}
    </ul>
  );
}
