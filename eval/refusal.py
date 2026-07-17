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
    "do not contain",
    "don't have information",
    "no information about this",
    "unable to help with that",
    "not mentioned in the available context",
]


def is_refusal(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in REFUSAL_PHRASES)
