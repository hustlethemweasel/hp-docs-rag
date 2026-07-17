import { beforeEach, describe, expect, it } from "vitest";
import { getUserId } from "./userId";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

describe("getUserId", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("generates a UUID on first call", () => {
    expect(getUserId()).toMatch(UUID_PATTERN);
  });

  it("returns the same id on subsequent calls", () => {
    const first = getUserId();
    const second = getUserId();
    expect(second).toBe(first);
  });

  it("persists the id in localStorage", () => {
    const id = getUserId();
    expect(localStorage.getItem("hp-docs-rag:user-id")).toBe(id);
  });

  it("generates a new id if storage was cleared", () => {
    const first = getUserId();
    localStorage.clear();
    const second = getUserId();
    expect(second).not.toBe(first);
  });
});
