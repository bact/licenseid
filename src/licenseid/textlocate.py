# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Where a List text may sit in an input, and how well it fits there.

All work is on word codes (``licenseid.textcorpus``): one code point per
token. Steps, cheapest first:

1. ``build_index``: the input's word 5-grams and their positions.
2. ``sample_share``: the share of SAMPLES evenly spaced 5-grams of a text the
   input holds. A text that is there has most of them; most texts stop here.
3. ``windows``: up to about ANCHORS 5-grams of the text vote for an offset
   (input position less text position). Two neighbouring buckets of offsets
   holding MIN_VOTE_SHARE of the anchors make a window, so every copy of a
   repeated text gets one.
4. ``align``: the word-level matching blocks of the text in a window, end
   blocks trimmed while that raises ``2M / (L + span)``: the span the text
   covers, never the padded window (a perfect copy between two other texts
   would score low on the window).
5. ``span_fit``: the character-level Indel similarity of the text and its
   span (``fuzz.ratio``'s metric) and the key ``2 x matched - len(text)``;
   ``same_critical``: the same count of each critical word. A fit of
   MIN_SIMILARITY or more with the same critical words is a hit; one of
   NEAR_SIMILARITY or more is a look-alike that can cast doubt on another
   text's hit (``licenseid.wholetexts``).

Every cost is bounded by a count, never a clock (``Budget``): past one the
search raises ``LimitReached`` and its caller answers nothing, never a
partial list (a partial list names a look-alike on the copies the true text
did not get to claim). Prototype and measurements: the speed study of the
TEXTS step (PR to be linked).
"""

from bisect import bisect_left
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from rapidfuzz.distance import Indel, LCSseq

from licenseid.textcorpus import CodedText, Span, critical_counts

#: Words per anchor n-gram.
N_GRAM: Final = 5
#: The n-grams of a text looked up before its anchors.
SAMPLES: Final = 48
#: The n-grams of a text that vote for an offset, at most (about).
ANCHORS: Final = 200
#: The share of a text's samples, and of its anchors in one window, needed.
#: A word ratio of 0.8 with changes spread evenly leaves 0.8 ** 5 = 0.33 of
#: the 5-grams.
MIN_VOTE_SHARE: Final = 0.30
#: The word-level ratio of a span below which no character is compared.
WORD_GATE: Final = 0.80
#: The character-level similarity of a text and its span, at least.
MIN_SIMILARITY: Final = 0.95
#: The similarity of a look-alike: a text of another licence that fits a
#: hit's span this well casts doubt on the hit. BSD-3-Clause with filled-in
#: names fits at 0.94 where BSD-3-Clause-HP fits at 0.956 (PySocks 1.7.1).
NEAR_SIMILARITY: Final = 0.93
#: The similarity of a hit that a look-alike does not doubt. Copies of
#: BSD-3-Clause with "the author" for "the copyright holders" fit both it and
#: BSD-3-Clause-HP at 0.95 to 0.979; plain copies fit BSD-3-Clause at 0.98
#: or more (TEXTS measurements, PR to be linked).
SURE_SIMILARITY: Final = 0.98

#: Limits of one search; past one the step answers nothing.
MAX_INPUT_CHARS: Final = 400_000
MAX_INPUT_TOKENS: Final = 50_000
MAX_VOTES: Final = 3_000_000
MAX_WINDOWS: Final = 15_000
MAX_WORD_CELLS: Final = 5_000_000_000
MAX_CHAR_CELLS: Final = 20_000_000_000

# Blocks looked at from each end per trimming pass.
_TRIM_REACH: Final = 50


class LimitReached(Exception):
    """A search went past one of the limits: it answers nothing."""


class Budget:
    """What one search has spent. Each charge reads its limit when made."""

    def __init__(self) -> None:
        self.votes = 0
        self.windows = 0
        self.word_cells = 0
        self.char_cells = 0

    def charge_votes(self, count: int) -> None:
        """Count *count* offset votes."""
        self.votes += count
        if self.votes > MAX_VOTES:
            raise LimitReached("votes")

    def charge_windows(self, count: int) -> None:
        """Count *count* windows."""
        self.windows += count
        if self.windows > MAX_WINDOWS:
            raise LimitReached("windows")

    def charge_word_cells(self, count: int) -> None:
        """Count *count* word pairs of an alignment."""
        self.word_cells += count
        if self.word_cells > MAX_WORD_CELLS:
            raise LimitReached("word cells")

    def charge_char_cells(self, count: int) -> None:
        """Count *count* character pairs of a similarity."""
        self.char_cells += count
        if self.char_cells > MAX_CHAR_CELLS:
            raise LimitReached("character cells")


@dataclass(frozen=True)
class Window:
    """Where a text may sit: *start* to *end* (tokens) from its votes, and
    the window to align it in, padded by a tenth of the text each side."""

    start: int
    end: int
    pad_start: int
    pad_end: int


def build_index(codes: str) -> dict[str, list[int]]:
    """Every word 5-gram of *codes* and where it starts, in order."""
    index: dict[str, list[int]] = {}
    for position in range(len(codes) - N_GRAM + 1):
        index.setdefault(codes[position : position + N_GRAM], []).append(position)
    return index


def _starts(codes: str, count: int) -> range:
    """About *count* evenly spaced n-gram starts of *codes*."""
    grams = len(codes) - N_GRAM + 1
    return range(0, max(grams, 0), max(1, -(-grams // count)))


def sample_share(codes: str, index: dict[str, list[int]]) -> float:
    """The share of SAMPLES evenly spaced n-grams of *codes* in *index*."""
    starts = _starts(codes, SAMPLES)
    if not starts:
        return 0.0
    found = sum(1 for at in starts if codes[at : at + N_GRAM] in index)
    return found / len(starts)


def _votes(
    codes: str, index: dict[str, list[int]], budget: Budget
) -> tuple[list[int], int, int]:
    """The offsets the anchors of *codes* vote for, how many anchors found a
    place, and how many anchors there are."""
    starts = _starts(codes, ANCHORS)
    offsets: list[int] = []
    seen = 0
    for at in starts:
        places = index.get(codes[at : at + N_GRAM])
        if places:
            seen += 1
            offsets.extend([place - at for place in places])
    budget.charge_votes(len(offsets))
    return offsets, seen, len(starts)


def _runs(offsets: list[int], tolerance: int, need: int) -> list[Span]:
    """Offset ranges of two neighbouring buckets holding *need* votes or
    more, the fullest first, each bucket in one range at most."""
    votes = Counter(offset // tolerance for offset in offsets)
    pairs = sorted(
        ((count + votes.get(key + 1, 0), -key) for key, count in votes.items()),
        reverse=True,
    )
    used: set[int] = set()
    runs: list[Span] = []
    for total, negative in pairs:
        if total < need:
            break
        key = -negative
        if key in used or key + 1 in used:
            continue
        used.update((key, key + 1))
        runs.append((key * tolerance, (key + 2) * tolerance))
    return runs


def _window(first: int, last: int, length: int, n_input: int) -> Window:
    """The window of a text of *length* tokens whose votes run from offset
    *first* to *last*, in an input of *n_input* tokens."""
    pad = max(10, length // 10)
    return Window(
        start=max(0, first),
        end=min(n_input, last + length),
        pad_start=max(0, first - pad),
        pad_end=min(n_input, last + length + pad),
    )


def windows(
    codes: str, index: dict[str, list[int]], n_input: int, budget: Budget
) -> list[Window]:
    """The windows of an input of *n_input* tokens where the text *codes*
    may sit, one per run of votes (one per copy)."""
    offsets, seen, anchors = _votes(codes, index, budget)
    need = max(1, int(MIN_VOTE_SHARE * anchors))
    if seen < need:
        return []
    length = len(codes)
    runs = _runs(offsets, max(20, length // 4), need)
    budget.charge_windows(len(runs))
    offsets.sort()
    return [
        _window(
            offsets[bisect_left(offsets, low)],
            offsets[bisect_left(offsets, high) - 1],
            length,
            n_input,
        )
        for low, high in runs
    ]


@dataclass(frozen=True)
class _Blocks:
    """Matching blocks of a text of *length* words in a window: where each
    starts in the window and its size."""

    starts: list[int]
    sizes: list[int]
    length: int

    def ratio(self, first: int, last: int, matched: int) -> float:
        """``2M / (L + span)`` of blocks *first* to *last*."""
        span = self.starts[last] + self.sizes[last] - self.starts[first]
        return 2 * matched / (self.length + span)

    def trim_front(self, first: int, last: int, matched: int) -> tuple[int, int]:
        """The first block and match count after dropping the front blocks
        whose loss raises the ratio most."""
        best = self.ratio(first, last, matched)
        kept, kept_matched, left = first, matched, matched
        for drop in range(first, min(last, first + _TRIM_REACH)):
            left -= self.sizes[drop]
            ratio = self.ratio(drop + 1, last, left)
            if ratio > best:
                best, kept, kept_matched = ratio, drop + 1, left
        return kept, kept_matched

    def trim_back(self, first: int, last: int, matched: int) -> tuple[int, int]:
        """The last block and match count after dropping the end blocks
        whose loss raises the ratio most."""
        best = self.ratio(first, last, matched)
        kept, kept_matched, left = last, matched, matched
        for drop in range(last, max(first, last - _TRIM_REACH), -1):
            left -= self.sizes[drop]
            ratio = self.ratio(first, drop - 1, left)
            if ratio > best:
                best, kept, kept_matched = ratio, drop - 1, left
        return kept, kept_matched


def _blocks(text: str, window: str) -> _Blocks | None:
    """The non-empty matching blocks of *text* in *window*."""
    blocks = [b for b in Indel.editops(text, window).as_matching_blocks() if b.size]
    if not blocks:
        return None
    return _Blocks([b.b for b in blocks], [b.size for b in blocks], len(text))


def align(text: str, window: str) -> Span | None:
    """The span of *window* (start, end; word codes) that the text *text*
    covers, its ends trimmed, or None when its word-level ratio cannot reach
    WORD_GATE."""
    length = len(text)
    gate = round(WORD_GATE * 100)
    # 2M / (L + span) <= 2M / (L + M): M must reach g L / (2 - g).
    floor = -(-gate * length // (200 - gate))
    if LCSseq.similarity(text, window, score_cutoff=floor) < floor:
        return None
    blocks = _blocks(text, window)
    if blocks is None:
        return None
    first, last, matched = 0, len(blocks.sizes) - 1, sum(blocks.sizes)
    while first < last:
        new_first, matched = blocks.trim_front(first, last, matched)
        new_last, matched = blocks.trim_back(new_first, last, matched)
        if (new_first, new_last) == (first, last):
            break
        first, last = new_first, new_last
    start, end = blocks.starts[first], blocks.starts[last] + blocks.sizes[last]
    if 200 * matched < gate * (length + end - start):
        return None
    return start, end


@dataclass(frozen=True)
class Fit:
    """How well a text fits its span: the Indel *distance* of the two, their
    *total* length, and the key ``2 x matched - len(text)`` (found less
    missing, ``span length - distance``)."""

    key: int
    distance: int
    total: int

    def reaches(self, similarity: float) -> bool:
        """Whether ``1 - distance / total`` is *similarity* or more, in whole
        numbers (*similarity* to a whole percent), so equal fits tie exactly."""
        return self.distance <= _allowed(self.total, similarity)


def _allowed(total: int, similarity: float) -> int:
    """The largest distance of two strings of *total* characters whose
    similarity is *similarity* or more."""
    percent = round(similarity * 100)
    return total - (percent * total + 99) // 100


def same_critical(coded: CodedText, span_words: Sequence[str]) -> bool:
    """Whether each critical word is in the span as often as in the text
    *coded*: a span that drops or adds a "not" is not the text."""
    return critical_counts(span_words) == coded.critical


def span_fit(coded: CodedText, span_text: str, budget: Budget) -> Fit | None:
    """The fit of the text *coded* in its span, or None when it is under
    NEAR_SIMILARITY. Its critical words are not compared (``same_critical``).

    The similarity is ``fuzz.ratio``'s, ``1 - distance / (L + S)`` with the
    Indel distance."""
    length, size = len(coded.text), len(span_text)
    budget.charge_char_cells(length * size)
    total = length + size
    allowed = _allowed(total, NEAR_SIMILARITY)
    distance = Indel.distance(coded.text, span_text, score_cutoff=allowed)
    if distance > allowed:
        return None
    return Fit(key=size - distance, distance=distance, total=total)
