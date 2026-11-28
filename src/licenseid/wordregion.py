# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Where in a List text Tier 2 aligns a fragment, found by words first.

Tier 2's character steps (``licenseid.similarity.fragment_similarity``)
slide the fragment over the whole text, and RapidFuzz's cost grows with
the characters on both sides: a 3,000-character fragment of Apache-2.0
costs tens of milliseconds a candidate. The texts are already coded as
words (``licenseid.textcorpus``, one code point a token). The input coded
with the same vocabulary is aligned with a text's codes first, at a cost in
words, not characters; the character steps then run on the region that
alignment found, padded by PAD_WORDS tokens on each side, instead of the
whole text.

A region is given only on positive evidence: a word alignment of
ACCEPT_SCORE or more with the codes of the very text the candidate holds.
Otherwise (no codes for the candidate: an ID the corpus has no text of, a
text other than the corpus's; or a weak alignment) there is none, and Tier
2 scans the whole text as before. An alignment that cannot reach
ACCEPT_SCORE, by the count of codes the two share, is not made
(:func:`best_possible`): the words of an English text against a Japanese
input, one code a character, would cost as much as the character steps.
A corpus restored from damaged stored codes is built again in memory
(``licenseid.textstore``): its codes, and so its regions, are those of an
``update`` build.

Han and kana characters are tokens of their own (``textgrams.split_words``),
so for Japanese and Chinese the padding is PAD_WORDS characters.

Both numbers are those of the speed plan (``speed-0-10-plan.md``, 3.2),
measured in ``working-docs/implementation/word-region.md``.
"""

from collections import Counter
from collections.abc import Callable
from typing import Final, cast

from rapidfuzz import fuzz
from rapidfuzz.distance import ScoreAlignment

from licenseid.textcorpus import RunChars, Span, TextCorpus
from licenseid.textgrams import split_words

#: The least word alignment (RapidFuzz's 0 to 100) that locates the input
#: in a text; under it the whole text is scanned.
ACCEPT_SCORE: Final = 60.0
#: Tokens added on each side of the located region.
PAD_WORDS: Final = 4


def best_possible(input_counts: Counter[str], input_len: int, text_codes: str) -> float:
    """The highest score RapidFuzz's alignment of an input (*input_len*
    codes, counted in *input_counts*) with *text_codes* can give, from the
    codes the two share (*shared*, as a multiset) alone.

    The shorter of the two (*n* codes) is compared whole with windows of the
    longer, at most *n* long (shorter at its ends): a window of *k* codes
    scores 2 x LCS / (n + k), and the LCS is at most min(k, shared), so no
    window scores over 2 x shared / (n + shared)."""
    shared = (input_counts & Counter(text_codes)).total()
    shorter = min(input_len, len(text_codes))
    return 200.0 * shared / (shorter + shared) if shared else 0.0


def located(
    input_codes: str,
    text_codes: str,
    text: str,
    input_counts: Counter[str] | None = None,
) -> Span | None:
    """Where *text* (coded *text_codes*) holds the input coded *input_codes*
    (counted in *input_counts*, else counted here), as a slice of *text*'s
    characters from the start of a token to the end of one: the best word
    alignment, as many tokens as the input at least, padded by PAD_WORDS
    tokens on each side. None when that alignment scores under ACCEPT_SCORE,
    or cannot (:func:`best_possible`), which costs no alignment."""
    counts = Counter(input_codes) if input_counts is None else input_counts
    if best_possible(counts, len(input_codes), text_codes) < ACCEPT_SCORE:
        return None
    # None only under a score_cutoff, which is not given.
    alignment = cast(
        ScoreAlignment, fuzz.partial_ratio_alignment(input_codes, text_codes)
    )
    if alignment.score < ACCEPT_SCORE:  # an empty input scores 0
        return None
    start, end, count = alignment.dest_start, alignment.dest_end, len(text_codes)
    # RapidFuzz may give a window shorter than the input at an end of the
    # text (a trimmed one): the region still holds as many tokens as the
    # input, so the characters can align where the words did not.
    if start == 0:
        end = max(end, min(count, len(input_codes)))
    if end == count:
        start = min(start, max(0, count - len(input_codes)))
    return RunChars(text).bounds(max(0, start - PAD_WORDS), min(count, end + PAD_WORDS))


class WordRegions:
    """The regions of one input, for the candidates of one ``detect()`` call
    (or ``--diff``): the input is coded once, at the first candidate that
    asks, from the corpus *corpus* gives (read at that time, not before: an
    input no candidate aligns never loads it)."""

    def __init__(self, norm_input: str, corpus: Callable[[], TextCorpus]) -> None:
        self._norm_input = norm_input
        self._corpus = corpus
        self._coded: tuple[TextCorpus, str, Counter[str]] | None = None

    def _input(self) -> tuple[TextCorpus, str, Counter[str]]:
        """The corpus, the input's codes in it and their counts."""
        if self._coded is None:
            corpus = self._corpus()
            codes = corpus.encode(split_words(self._norm_input))
            self._coded = corpus, codes, Counter(codes)
        return self._coded

    def region(self, license_id: str, text: str) -> Span | None:
        """Where *text*, the text of the candidate *license_id*, holds the
        input (:func:`located`), or None: no codes of that text, or a weak
        alignment."""
        corpus, codes, counts = self._input()
        entry = corpus.entry(license_id)
        if entry is None or entry.text.text != text:
            return None
        return located(codes, entry.text.codes, text, counts)
