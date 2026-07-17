"""Slow suite: the real harrier-oss-v1-270m model (SPEC §7.3, §11).

Downloads/loads real weights; confirms the asymmetric encoding contract
actually holds against the real model, not just the wrapper's call shape.
"""

import numpy as np
import pytest

from app.ingest.embedding import EMBEDDING_DIM, load_embedder

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def embedder():
    return load_embedder("microsoft/harrier-oss-v1-270m")


def test_embeddings_are_640_dim_and_l2_normalized(embedder):
    [vector] = embedder.embed_documents(["Replace the ink cartridge."])

    assert len(vector) == EMBEDDING_DIM
    assert np.linalg.norm(vector) == pytest.approx(1.0, abs=1e-2)


def test_query_instruction_changes_the_embedding(embedder):
    text = "how do I clean the printhead?"

    [as_document] = embedder.embed_documents([text])
    as_query = embedder.embed_query(text)

    assert as_document != as_query
