from app.repositories.chunks import RetrievedChunk

SYSTEM_PROMPT = (
    "You are a support assistant for two HP product manuals: the HP ENVY "
    '6000 All-in-One User Guide and the OMEN 17.3" Gaming Laptop '
    "Maintenance & Service Guide. Answer only using the context below. "
    "Cite every claim inline as [Document, p. X]. If the context doesn't "
    "contain the answer, say plainly that it isn't in the documents rather "
    "than guessing."
)

NO_CONTEXT_MESSAGE = "No relevant context was found in the HP documents."


def format_context(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return NO_CONTEXT_MESSAGE
    return "\n\n".join(
        f"[{c.document}, p. {page_label(c)}]\n{c.content}" for c in chunks
    )


def build_system_prompt(chunks: list[RetrievedChunk]) -> str:
    return f"{SYSTEM_PROMPT}\n\nContext:\n{format_context(chunks)}"


def page_label(chunk: RetrievedChunk) -> str:
    if chunk.page_start == chunk.page_end:
        return str(chunk.page_start)
    return f"{chunk.page_start}-{chunk.page_end}"
