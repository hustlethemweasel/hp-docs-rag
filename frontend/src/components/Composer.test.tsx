import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Composer } from "./Composer";

describe("Composer", () => {
  it("submits the typed message and clears the input", async () => {
    const onSend = vi.fn();
    render(<Composer onSend={onSend} disabled={false} />);

    const textbox = screen.getByRole("textbox");
    await userEvent.type(textbox, "How do I replace the cartridge?");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    expect(onSend).toHaveBeenCalledWith("How do I replace the cartridge?");
    expect(textbox).toHaveValue("");
  });

  it("submits on Enter without adding a newline", async () => {
    const onSend = vi.fn();
    render(<Composer onSend={onSend} disabled={false} />);

    const textbox = screen.getByRole("textbox");
    await userEvent.type(textbox, "hello{Enter}");

    expect(onSend).toHaveBeenCalledWith("hello");
  });

  it("does not submit empty or whitespace-only input", async () => {
    const onSend = vi.fn();
    render(<Composer onSend={onSend} disabled={false} />);

    await userEvent.type(screen.getByRole("textbox"), "   {Enter}");

    expect(onSend).not.toHaveBeenCalled();
  });

  it("disables the send button while a reply is in flight", () => {
    render(<Composer onSend={vi.fn()} disabled={true} />);

    expect(screen.getByRole("button", { name: /send/i })).toBeDisabled();
  });
});
