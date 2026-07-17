import threading

from sentence_transformers import SentenceTransformer

EMBEDDING_DIM = 640
QUERY_PROMPT_NAME = "web_search_query"


class Embedder:
    """Asymmetric wrapper around the fixed embedding model.

    Documents are encoded plain; queries get the model's retrieval-task
    instruction prompt. Omitting it measurably degrades retrieval, so this
    distinction is the wrapper's entire reason to exist rather than calling
    SentenceTransformer.encode directly.

    `Embedder` is a singleton shared across every request (app.state.embedder),
    and `embed_query` runs off the event loop via asyncio.to_thread — so
    concurrent requests can now call `.encode()` from different threads at
    once. sentence-transformers/PyTorch CPU inference isn't safe under that:
    a load test surfaced a real dtype-cast race. `_model_lock` serializes
    actual model invocations.
    """

    def __init__(self, model: SentenceTransformer) -> None:
        self._model = model
        self._model_lock = threading.Lock()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        with self._model_lock:
            return self._model.encode(texts).tolist()

    def embed_query(self, text: str) -> list[float]:
        with self._model_lock:
            encoded = self._model.encode([text], prompt_name=QUERY_PROMPT_NAME)
        return encoded[0].tolist()

    def count_tokens(self, text: str) -> int:
        """Token count per the embedding model's own tokenizer."""
        return len(self._model.tokenizer.encode(text))


def load_embedder(model_name: str) -> Embedder:
    return Embedder(model=SentenceTransformer(model_name))
