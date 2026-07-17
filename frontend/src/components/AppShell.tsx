"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { Sidebar } from "./Sidebar";

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const activeId = pathname.match(/^\/c\/([^/]+)/)?.[1];

  return (
    <div className="flex h-screen">
      <Sidebar activeId={activeId} />
      <main className="min-w-0 flex-1">{children}</main>
    </div>
  );
}
