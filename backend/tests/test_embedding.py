"""Behavior: asymmetric embedding encoding.

Queries must be encoded with a retrieval task instruction; documents are
encoded plain. sentence_transformers.SentenceTransformer is the external
boundary (model weights, compute) — doubled with create_autospec so the
wrapper's own call contract is verified without loading real weights.
"""

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


def test_count_tokens_uses_the_embedding_models_own_tokenizer():
    model = create_autospec(SentenceTransformer, instance=True)
    model.tokenizer.encode.return_value = [2, 7084, 506, 3645]
    embedder = Embedder(model=model)

    count = embedder.count_tokens("Open the front cover.")

    model.tokenizer.encode.assert_called_once_with("Open the front cover.")
    assert count == 4
