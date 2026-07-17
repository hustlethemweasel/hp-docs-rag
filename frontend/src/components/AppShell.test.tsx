import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "./AppShell";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/c/conv-2",
}));

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

describe("AppShell", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("marks the conversation matching the current path as active", async () => {
    vi.mocked(fetch).mockResolvedValue(
      jsonResponse([
        { id: "conv-1", title: "First", updated_at: "2026-01-01" },
        { id: "conv-2", title: "Second", updated_at: "2026-01-02" },
      ]),
    );

    render(
      <AppShell>
        <p>page content</p>
      </AppShell>,
    );

    expect(screen.getByText("page content")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Second" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("link", { name: "First" })).not.toHaveAttribute(
      "aria-current",
    );
  });
});
