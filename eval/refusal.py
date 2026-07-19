"""Refusal detection for the negative-case metric (§13 refusal correctness).

Matches both the deterministic REFUSAL_MESSAGE (retrieval-threshold guard)
and free-text refusals the model itself might phrase when given weak or
irrelevant context.
"""

REFUSAL_PHRASES = [
    "isn't in the documents",
    "not in the documents",
    "couldn't find this in the hp documents",
    "doesn't contain",
    "does not contain",
    "do not contain",
    "don't have information",
    "no information about this",
    "unable to help with that",
    "not mentioned in the available context",
    # pt-BR: the system prompt mirrors the user's language, so negative
    # cases asked in Portuguese refuse in Portuguese.
    "não está nos documentos",
    "não estão nos documentos",
    "não está contida",
    "não estão contidas",
    "não contém",
    "não contêm",
    "não encontrei",
    "não há informações",
]


def is_refusal(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in REFUSAL_PHRASES)
