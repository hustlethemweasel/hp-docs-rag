"""Behavior: asymmetric embedding encoding.

Queries must be encoded with a retrieval task instruction; documents are
encoded plain. sentence_transformers.SentenceTransformer is the external
boundary (model weights, compute) — doubled with create_autospec so the
wrapper's own call contract is verified without loading real weights.
"""

import threading
import time
from unittest.mock import create_autospec

import numpy as np
from sentence_transformers import SentenceTransformer

from app.ingest.embedding import QUERY_PROMPT_NAME, Embedder


def test_embed_documents_encodes_without_a_query_instruction():
    model = create_autospec(SentenceTransformer, instance=True)
    model.encode.return_value = np.array([[0.1, 0.2]])
    embedder = Embedder(model=model)

    result = embedder.embed_documents(["Open the front cover."])

    model.encode.assert_called_once_with(["Open the front cover."])
    assert result == [[0.1, 0.2]]


def test_embed_query_applies_the_retrieval_instruction():
    model = create_autospec(SentenceTransformer, instance=True)
    model.encode.return_value = np.array([[0.3, 0.4]])
    embedder = Embedder(model=model)

    result = embedder.embed_query("how do I clean the printhead?")

    model.encode.assert_called_once_with(
        ["how do I clean the printhead?"], prompt_name=QUERY_PROMPT_NAME
    )
    assert result == [0.3, 0.4]


def test_embed_query_serializes_concurrent_calls_on_the_shared_model():
    """sentence-transformers/PyTorch CPU inference isn't safe to invoke
    concurrently from multiple threads on one shared model instance — a
    load test surfaced a real dtype-cast race ("expected m1 and m2 to have
    the same dtype") once query embedding moved off the event loop onto
    worker threads (HybridRetriever.retrieve uses asyncio.to_thread, and
    Embedder is a singleton shared across every request). Actual model
    calls must be serialized.
    """
    max_concurrent = 0
    current = 0
    tracking_lock = threading.Lock()

    def tracking_encode(texts: list[str], **kwargs: object) -> np.ndarray:
        nonlocal max_concurrent, current
        with tracking_lock:
            current += 1
            max_concurrent = max(max_concurrent, current)
        time.sleep(0.05)
        with tracking_lock:
            current -= 1
        return np.array([[0.1] * 640 for _ in texts])

    model = create_autospec(SentenceTransformer, instance=True)
    model.encode.side_effect = tracking_encode
    embedder = Embedder(model=model)
    threads = [
        threading.Thread(target=embedder.embed_query, args=(f"query {i}",))
        for i in range(5)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert max_concurrent == 1


def test_count_tokens_uses_the_embedding_models_own_tokenizer():
    model = create_autospec(SentenceTransformer, instance=True)
    model.tokenizer.encode.return_value = [2, 7084, 506, 3645]
    embedder = Embedder(model=model)

    count = embedder.count_tokens("Open the front cover.")

    model.tokenizer.encode.assert_called_once_with("Open the front cover.")
    assert count == 4
