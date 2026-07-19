"""Behavior: detect whether an answer is a refusal, for the negative-case metric.

Pure text matching; no doubles needed.
"""

from eval.refusal import is_refusal

from app.rag.chat_service import REFUSAL_MESSAGE


def test_detects_the_standard_refusal_message():
    assert is_refusal(REFUSAL_MESSAGE) is True


def test_detects_other_refusal_phrasing_from_the_model():
    assert is_refusal("That isn't in the documents I have access to.") is True
    assert is_refusal("I don't have information about that in the manuals.") is True
    assert is_refusal("I'm unable to help with that question.") is True
    assert (
        is_refusal(
            "The documents provided do not contain any information about "
            "Thunderbolt 5 support."
        )
        is True
    )
    assert (
        is_refusal("Thunderbolt 5 is not mentioned in the available context.") is True
    )
    # Observed verbatim from qwen3.5:4b during the live Ollama verification —
    # third-person singular, unlike the "do not contain" already listed.
    assert (
        is_refusal(
            "The provided context does not contain information about the "
            "capital of France."
        )
        is True
    )


def test_detects_portuguese_refusal_phrasing():
    # The system prompt answers in the user's language, so pt-BR negative
    # cases refuse in Portuguese (SPEC's multilingual section).
    assert is_refusal("Essa informação não está nos documentos.") is True
    assert is_refusal("Os manuais não contêm informações sobre isso.") is True
    assert is_refusal("Não encontrei essa informação nos manuais da HP.") is True
    assert is_refusal("O contexto fornecido não contém a resposta.") is True


def test_does_not_flag_a_normal_grounded_answer():
    assert is_refusal("Open the front cover and pull the cartridge out.") is False


def test_does_not_flag_a_normal_portuguese_answer():
    assert is_refusal("Abra a tampa frontal e retire o cartucho.") is False
