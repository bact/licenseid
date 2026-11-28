# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Word 3-grams of a normalised text, as stable 64-bit hashes, and the score
of each List text that shares grams with an input.

A text's tokens are its words, and each Han or kana character alone
(:func:`split_words`): Japanese and Chinese are written without spaces, so a
text wrapped at another width keeps its grams. A gram is three tokens in a
row; its hash is BLAKE2b of the three joined by a space (a token holds no
white space), cut to 8 bytes and read as a signed little-endian integer,
which SQLite stores as it is. Never ``hash()``: its value changes with the
process.

For every text that shares a gram with the input, ``shared`` is the number
of the input's distinct grams the text holds and ``score`` is ``shared /
min(grams of the input, grams of the text)`` (plan 3.1, step 2): the share
of the smaller side, so that a fragment of a long text and a short text
inside a long input both score high.

Standard library only: ``licenseid.gramstore`` builds an index from it at
``update`` and at a lookup, and ``licenseid.textcorpus`` takes its tokens
and its critical words from here.
"""

import hashlib
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Final, NamedTuple

#: Tokens in a gram. Its change, the hash's or the token rule's bumps the
#: database build (``dbschema.BUILD_VERSION``) and is in the stamp of the
#: stored postings (``licenseid.gramstore``).
GRAM_SIZE: Final = 3
#: The hash of a gram, as named in the stamp of the stored postings.
HASH_NAME: Final = "blake2b-64"
#: Words whose presence on one side only turns a grant around: a similarity
#: above 0.9 loses 5 % for each (``licenseid.similarity``), and the corpus
#: keeps their codes (``licenseid.textcorpus``).
CRITICAL_TOKENS: Final = frozenset({"not", "except", "unless", "irrevocable"})
#: Raised on a change to what a token is (:data:`TOKEN`, :func:`split_words`).
TOKEN_RULE: Final = 1

# Han and kana are written without spaces between words, so each of their
# characters is a token of its own; a phrase of 60 characters as one "word"
# would make a one-character change a whole-word miss. Written as escapes:
# an editor that normalises text would turn U+F900 into U+8C48.
_CJK: Final = "\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff"
#: A token: one Han or kana character, or a run of other characters that are
#: not white space.
TOKEN: Final = re.compile(f"[{_CJK}]|[^\\s{_CJK}]+")
# One character of a token of several: neither white space nor Han or kana.
_RUN_CHAR: Final = re.compile(f"[^\\s{_CJK}]")


def split_words(text: str) -> list[str]:
    """The tokens of *text*: its words, and each Han or kana character
    alone. ASCII text is split on white space only (the fast path)."""
    if text.isascii():
        return text.split()
    return TOKEN.findall(text)


def _joined(text: str, at: int) -> bool:
    """Whether position *at* of *text* falls inside a token, between two of
    its characters."""
    return (
        0 < at < len(text)
        and _RUN_CHAR.match(text, at - 1) is not None
        and _RUN_CHAR.match(text, at) is not None
    )


def whole_tokens(text: str, start: int, end: int) -> tuple[int, int]:
    """*start* and *end*, a slice of *text*, moved out to the edges of the
    tokens they cut (as :func:`split_words` reads them): the slice then
    shows every token it touches whole."""
    while _joined(text, start):
        start -= 1
    while _joined(text, end):
        end += 1
    return start, end


def gram_hash(gram: str) -> int:
    """The stable 64-bit hash of *gram*, as a signed integer. A lone
    surrogate (no List text holds one) is hashed as written, not refused."""
    digest = hashlib.blake2b(
        gram.encode("utf-8", "surrogatepass"), digest_size=8
    ).digest()
    return int.from_bytes(digest, "little", signed=True)


def gram_strings(words: Sequence[str]) -> list[str]:
    """The grams of *words* in order, repeats kept: none for fewer than
    :data:`GRAM_SIZE` words."""
    return list(map(" ".join, zip(*(words[at:] for at in range(GRAM_SIZE)))))


def input_grams(norm_text: str) -> list[int]:
    """The distinct gram hashes of *norm_text*, in the order each first
    appears: a caller that looks up only the first N reads the same N on
    every run."""
    return list(dict.fromkeys(map(gram_hash, gram_strings(split_words(norm_text)))))


class GramScore(NamedTuple):
    """A List text that shares grams with an input."""

    license_id: str
    #: The input's distinct grams the text holds.
    shared: int
    #: The text's distinct grams.
    size: int
    #: ``shared / min(grams of the input, size)``.
    score: float


class GramTable(NamedTuple):
    """The texts that share a gram with an input, and how many of its grams
    were looked up."""

    #: In row order (the order of the texts in the database), one per text.
    rows: tuple[GramScore, ...]
    #: The input's distinct grams looked up: the denominator of its side.
    grams: int
    #: The input's distinct grams: more than *grams* when a bound cut them.
    total: int

    @property
    def bounded(self) -> bool:
        """Whether a bound left some of the input's grams unread."""
        return self.grams < self.total


def score_rows(
    shared: Mapping[int, int],
    grams: int,
    ids: Sequence[str],
    sizes: Sequence[int],
) -> tuple[GramScore, ...]:
    """The score of each text *shared* counts (text number to shared grams),
    for an input of *grams* distinct grams; texts in number order, which is
    row order."""
    return tuple(
        GramScore(ids[k], shared[k], sizes[k], shared[k] / min(grams, sizes[k]))
        for k in sorted(shared)
    )


def ranked(rows: Iterable[GramScore]) -> list[GramScore]:
    """*rows* by score, highest first; of equal scores the earlier row first
    (a stable sort of rows in row order), never an order a hash gives."""
    return sorted(rows, key=lambda row: -row.score)
