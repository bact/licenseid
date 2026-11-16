# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The Tier 1 query: the ``MATCH`` string of the full-text search.

Standard library only. A word costs time in trigrams, not in words: one
10,000-character word of common trigrams took 1.2 s, the same word cut to
128 characters 0.007 s. The longest word of any indexed text of List 3.29.0
is 70 characters, so a cut at ``MAX_TERM_CHARS`` changes no result.
"""

from typing import Final

#: Words of the text the query holds (also the tail window of ``retrieval``).
MAX_TERMS: Final = 20
#: Characters kept of a word. Above the longest indexed word (70 in List
#: 3.29.0); ``tests/test_ftsquery.py`` holds the long-text fixtures to it.
MAX_TERM_CHARS: Final = 128


def match_query(norm_text: str) -> str:
    """Return the FTS5 ``MATCH`` string of *norm_text*, empty for no words.

    The first ``MAX_TERMS`` normalised words, joined with OR. OR maximises
    recall: a candidate matches if it contains any of the terms, and FTS5
    BM25 ranking still promotes documents that contain more terms. 20 words
    (up from 10) gives enough discriminating signal for licences whose
    preamble shares the first 10 words with many other licences (e.g. HPND
    family: "permission to use copy modify and distribute this software ...").

    Each word is cut to ``MAX_TERM_CHARS`` code points BEFORE ``"`` is
    doubled (a cut after quoting can leave a lone ``"``, a syntax error), then
    quoted: a word is a phrase to FTS5, never an operator, so a query cannot
    fail for its own text and every error is the database's.
    """
    words = norm_text.split()[:MAX_TERMS]
    return " OR ".join(
        '"' + word[:MAX_TERM_CHARS].replace('"', '""') + '"' for word in words
    )
