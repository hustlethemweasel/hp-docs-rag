from sentence_transformers import SentenceTransformer

EMBEDDING_DIM = 640
QUERY_PROMPT_NAME = "web_search_query"


class Embedder:
    """Asymmetric wrapper around the fixed embedding model (SPEC §7.3).

    Documents are encoded plain; queries get the model's retrieval-task
    instruction prompt. Omitting it measurably degrades retrieval, so this
    distinction is the wrapper's entire reason to exist rather than calling
    SentenceTransformer.encode directly.
    """

    def __init__(self, model: SentenceTransformer) -> None:
        self._model = model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts).tolist()

    def embed_query(self, text: str) -> list[float]:
        return self._model.encode([text], prompt_name=QUERY_PROMPT_NAME)[0].tolist()

    def count_tokens(self, text: str) -> int:
        """Token count per the embedding model's own tokenizer (SPEC §7.2)."""
        return len(self._model.tokenizer.encode(text))


def load_embedder(model_name: str) -> Embedder:
    return Embedder(model=SentenceTransformer(model_name))
