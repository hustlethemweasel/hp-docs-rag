import { describe, expect, it } from "vitest";
import { streamFrom } from "@/test-utils/stream";
import { parseSSEStream } from "./sse";

async function collect(stream: ReadableStream<Uint8Array>) {
  const events = [];
  for await (const event of parseSSEStream(stream)) {
    events.push(event);
  }
  return events;
}

describe("parseSSEStream", () => {
  it("parses a single complete event", async () => {
    const stream = streamFrom(['event: token\ndata: {"text":"hi"}\n\n']);
    expect(await collect(stream)).toEqual([
      { event: "token", data: { text: "hi" } },
    ]);
  });

  it("parses multiple events across separate chunks", async () => {
    const stream = streamFrom([
      'event: token\ndata: {"text":"a"}\n\n',
      'event: token\ndata: {"text":"b"}\n\nevent: done\ndata: {"sources":[]}\n\n',
    ]);
    expect(await collect(stream)).toEqual([
      { event: "token", data: { text: "a" } },
      { event: "token", data: { text: "b" } },
      { event: "done", data: { sources: [] } },
    ]);
  });

  it("reassembles an event split mid-frame across chunk boundaries", async () => {
    const stream = streamFrom([
      "event: tok",
      'en\ndata: {"text":"split"}',
      "\n\n",
    ]);
    expect(await collect(stream)).toEqual([
      { event: "token", data: { text: "split" } },
    ]);
  });

  it("ignores a trailing incomplete frame with no terminating blank line", async () => {
    const stream = streamFrom([
      'event: token\ndata: {"text":"a"}\n\n',
      "event: token\ndata: {",
    ]);
    expect(await collect(stream)).toEqual([
      { event: "token", data: { text: "a" } },
    ]);
  });
});
