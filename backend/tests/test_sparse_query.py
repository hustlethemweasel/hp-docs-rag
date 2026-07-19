"""The sparse-leg query transform: AND-of-words websearch → OR-of-words.

Conjunctive websearch semantics defeat exact-token lookups: a question like
"What is HP spare part 747080-001?" fails against the terse catalog chunk
holding the token whenever the chunk lacks any surrounding ordinary word.
The transform ORs the query's words, quoting each so hyphenated tokens
stay intact as phrases (websearch turns a quoted "747080-001" into the
phrase query '747080' <-> '-001').
"""

from app.repositories.chunks import or_websearch


def test_words_are_quoted_and_joined_with_or():
    assert (
        or_websearch("What is HP spare part 747080-001?")
        == '"What" OR "is" OR "HP" OR "spare" OR "part" OR "747080-001?"'
    )


def test_single_word_query_is_just_quoted():
    assert or_websearch("M08117-001") == '"M08117-001"'


def test_embedded_double_quotes_are_stripped():
    assert or_websearch('the "special" mode') == '"the" OR "special" OR "mode"'


def test_whitespace_only_query_becomes_empty():
    assert or_websearch("   ") == ""
