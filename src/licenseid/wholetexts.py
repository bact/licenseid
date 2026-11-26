# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The List texts an input holds whole (the ``TEXTS`` field).

``found_texts`` scans every text of a ``licenseid.textcorpus.TextCorpus`` (and
its core) against a normalised input with ``licenseid.textlocate``, then
keeps the hits that do not overlap, best first:

* key ``2 x matched - len(text)`` in characters (found less missing): the
  longer of two nested texts wins when the input holds it whole, the exact
  text wins over a longer look-alike;
* on equal keys the answer's group first, then the ID;
* a text whose span misses a run of MAX_GAP_CHARS of it is no hit (it
  lacks a clause), but still a look-alike;
* a hit overlapping a kept one by more than a tenth of the shorter span is
  dropped;
* a kept span names nothing when a look-alike, a text of another same-text
  group, fits a span overlapping it and either keys above it at
  MIN_SIMILARITY or more (a hit refused only by a critical word: a word
  dropped from the true text must not name a look-alike) or, for a span
  under SURE_SIMILARITY, keys at LOOKALIKE_REACH of it or more at
  NEAR_SIMILARITY or more with the same critical words (the input is about
  as close to either text), or, both fits with their variable parts left out
  (``licenseid.textmask``), ties it: keys at TIE_REACH of it or more as
  closely (two texts that differ only in their variable parts). Against a
  span fitted with its variable parts left out, the look-alike's parts are
  left out with no bound on their fills (``textmask.exempt_runs``): a
  clause too long for FILL_SLACK in a longer text must not name a shorter
  text inside it. A doubtful name is worse than none. The span stays
  claimed, so no third look-alike takes it.

Each copy of a text is a hit of its own; only then are the names deduped,
never before: a text kept once would leave its other copies to a look-alike.
``found_texts`` gives the names in the order the input holds them (by the
start of each one's first kept span), so ``Found.first`` is the text the input
gives first: ``licenseid.firsttext`` keeps a text answer only when it is that
one.

No database access and no detector state: the corpus is immutable and
every search keeps its state in local objects, so threads may share a
corpus.
"""

import heapq
from bisect import bisect_left
from dataclasses import dataclass
from typing import Final, NamedTuple

from licenseid import textlocate
from licenseid.textcorpus import (
    CodedText,
    CorpusEntry,
    RunChars,
    Span,
    TextCorpus,
    input_tokens,
)
from licenseid.textlocate import (
    MAX_GAP_CHARS,
    MIN_SIMILARITY,
    MIN_VOTE_SHARE,
    NEAR_SIMILARITY,
    SURE_SIMILARITY,
    Alignment,
    Budget,
    Fit,
    LimitReached,
    Window,
    align,
    build_index,
    can_reach,
    longest_gap,
    same_critical,
    sample_share,
    span_fit,
    windows,
)
from licenseid.textmask import exempt_runs, masked_fit

#: A List text (or core) of fewer tokens is never listed: too short to tell
#: a copy from a look-alike.
MIN_WORDS: Final = 40
#: An input of fewer tokens is not searched.
MIN_INPUT_WORDS: Final = 40
#: The core is the text less its optional parts: of the text's samples it
#: holds about its share of the characters. Half that share lets it be tried.
CORE_SAMPLE_FACTOR: Final = 0.5
#: A look-alike's key is at least this share of the hit's: a text of about
#: the same extent. A text the hit holds as a part (PSF-2.0 in Python-2.0.1,
#: a key of a quarter) is no look-alike. On the real licence files any share
#: from 0.80 to 0.93 gives the same answers (TEXTS measurements).
LOOKALIKE_REACH: Final = 0.90
#: Two masked fits whose keys are this close tie (``_outkeys``): the cores
#: of OLDAP-1.1 and NBPL-1.0 key 4,537 and 4,591 (0.988). At 0.90 a nested
#: text that fits its shorter span more closely (SMLNJ's core in Pillow's
#: MIT-CMU, 0.954) doubts the true one.
TIE_REACH: Final = 0.98


@dataclass(frozen=True)
class _Input:
    """The input as tokens, word codes and a 5-gram index."""

    text: str
    words: list[str]
    offsets: list[Span] | None
    codes: str
    index: dict[str, list[int]]

    def span_text(self, start: int, end: int) -> str:
        """The characters of tokens *start* to *end*."""
        if self.offsets is None:
            return " ".join(self.words[start:end])
        return self.text[self.offsets[start][0] : self.offsets[end - 1][1]]


class _Item(NamedTuple):
    """A window to score, or a scored span, in the order of the greedy pick.

    An unscored item's key is its bound, the text's length (2 x matched -
    len(text) <= len(text)); unscored before scored on equal keys keeps the
    order exact. *serial* is unique, so *coded*, *window* and *fit* are
    never compared."""

    negative_key: int
    scored: int
    rank: int
    row_id: str
    start: int
    end: int
    serial: int
    coded: CodedText
    window: Window
    fit: Fit | None = None


def _meet(first: Span, second: Span) -> bool:
    """Whether two spans overlap by more than a tenth of the shorter."""
    shared = min(first[1], second[1]) - max(first[0], second[0])
    return 10 * shared > min(first[1] - first[0], second[1] - second[0])


class _Taken:
    """Kept spans by start. They overlap each other by a tenth at most, so a
    span meets few of them."""

    def __init__(self) -> None:
        self.starts: list[int] = []
        self.ends: list[int] = []
        self.longest = 0

    def add(self, start: int, end: int) -> None:
        """Keep [start, end)."""
        at = bisect_left(self.starts, start)
        self.starts.insert(at, start)
        self.ends.insert(at, end)
        self.longest = max(self.longest, end - start)

    def _near(self, start: int, end: int) -> list[Span]:
        """The kept spans that may meet [start, end)."""
        first = bisect_left(self.starts, start - self.longest)
        last = bisect_left(self.starts, end)
        return list(zip(self.starts[first:last], self.ends[first:last]))

    def overlaps(self, start: int, end: int) -> bool:
        """Whether a kept span overlaps [start, end) by more than a tenth of
        the shorter of the two."""
        return any(_meet(span, (start, end)) for span in self._near(start, end))

    def covers_half(self, start: int, end: int) -> bool:
        """Whether a kept span holds half of [start, end) or more: a window
        there is not worth aligning."""
        for kept_start, kept_end in self._near(start, end):
            if 2 * (min(end, kept_end) - max(start, kept_start)) >= end - start:
                return True
        return False


def _read_input(norm_input: str, corpus: TextCorpus) -> _Input | None:
    """*norm_input* ready to search, or None when it is too long or too short
    to search."""
    if len(norm_input) > textlocate.MAX_INPUT_CHARS:
        return None
    words, offsets = input_tokens(norm_input, textlocate.MAX_INPUT_TOKENS)
    if len(words) > textlocate.MAX_INPUT_TOKENS or len(words) < MIN_INPUT_WORDS:
        return None
    codes = corpus.encode(words)
    return _Input(norm_input, words, offsets, codes, build_index(codes))


def _fits(coded: CodedText, source: _Input) -> bool:
    """Whether *coded* is long enough to list and short enough to fit the
    input at NEAR_SIMILARITY: a look-alike (``_Search.doubted``) as well as
    a hit. A text longer than the input is still tried: a copy that lost a
    clause can fit it at MIN_SIMILARITY. The length is the text's less its
    variable parts (``CodedText.least``): a copy with short fills and no
    copyright line (PostgreSQL's) must not leave a shorter look-alike
    alone."""
    return len(coded.codes) >= MIN_WORDS and can_reach(
        coded.least, len(source.text), NEAR_SIMILARITY
    )


def _entry_windows(
    entry: CorpusEntry, source: _Input, budget: Budget
) -> list[tuple[CodedText, Window]]:
    """The windows of *entry*'s text and core that pass the sample check."""
    text, core = entry.text, entry.core
    if len(text.codes) < MIN_WORDS or (core is None and not _fits(text, source)):
        return []
    found: list[tuple[CodedText, Window]] = []
    n_input = len(source.codes)
    share = sample_share(text.codes, source.index)
    if share >= MIN_VOTE_SHARE and _fits(text, source):
        found += [(text, w) for w in windows(text.codes, source.index, n_input, budget)]
    if core is None:
        return found
    core_share = CORE_SAMPLE_FACTOR * MIN_VOTE_SHARE * len(core.text) / len(text.text)
    if (
        share >= core_share
        and _fits(core, source)
        and sample_share(core.codes, source.index) >= MIN_VOTE_SHARE
    ):
        found += [(core, w) for w in windows(core.codes, source.index, n_input, budget)]
    return found


def _items(
    corpus: TextCorpus, source: _Input, answer: str | None, budget: Budget
) -> list[_Item]:
    """A heap of every window of every text (and core) of *corpus*."""
    items: list[_Item] = []
    for entry in corpus.entries:
        for coded, window in _entry_windows(entry, source, budget):
            items.append(
                _Item(
                    negative_key=-len(coded.text),
                    scored=0,
                    rank=0 if coded.row_id == answer else 1,
                    row_id=coded.row_id,
                    start=window.start,
                    end=window.end,
                    serial=len(items),
                    coded=coded,
                    window=window,
                )
            )
    heapq.heapify(items)
    return items


class _Found(dict[int, Alignment]):
    """The last alignment of each window (by its item's serial), and every
    alignment by ``(serial, span)``: a fit reads the blocks of the very
    alignment that gave its span."""

    def __init__(self) -> None:
        super().__init__()
        self.by_span: dict[tuple[int, Span], Alignment] = {}


class _Search:
    """One search: the input, its budget, the spans kept, and every window
    by where it starts. A window is aligned and its span compared once,
    whether as a hit or as a look-alike."""

    def __init__(self, source: _Input, items: list[_Item], budget: Budget) -> None:
        self.source = source
        self.budget = budget
        self.taken = _Taken()
        self.items = sorted(items, key=lambda item: item.window.pad_start)
        self.starts = [item.window.pad_start for item in self.items]
        self.widest = max(
            (item.window.pad_end - item.window.pad_start for item in items), default=0
        )
        self._spans: dict[int, Span | None] = {}
        self._found = _Found()
        self._chars: dict[int, RunChars] = {}
        self._fits: dict[tuple[int, Span, bool], Fit | None] = {}

    def _span(self, item: _Item) -> Span | None:
        """Where *item*'s text sits in its window (input tokens), or None."""
        if item.serial not in self._spans:
            window = item.window
            self._spans[item.serial] = self._aligned(
                item, window.pad_start, window.pad_end
            )
        return self._spans[item.serial]

    def _hit_span(self, item: _Item) -> Span | None:
        """``_span``, looked for once more, the span widened by a run of
        MAX_GAP_CHARS or more that it misses at an end of the text: the
        text's end may match a later copy of the same words as well
        (Python-2.0.1's closing disclaimer, repeated by the 0BSD text after
        it), and trimming drops that far block, though the words sit right
        after the span. Only for a hit: a look-alike keeps ``_span``.

        Known limit, chosen (precision over recall): 20 to 60 foreign words
        inserted within about one run of an end of the text get that end
        block trimmed; the look then widens into the insertion and the hit
        is refused as a missing clause (``working-docs/implementation/
        whole-texts.md``, gap guard)."""
        span = self._span(item)
        widened = None if span is None else self._widened(item, span)
        if widened is not None and self._gap(item) >= MAX_GAP_CHARS:
            return self._aligned(item, *widened)
        return span

    def _aligned(self, item: _Item, start: int, end: int) -> Span | None:
        """Where *item*'s text sits in input tokens *start* to *end*, or
        None; keeps the runs of the text it misses."""
        codes = item.coded.codes
        self.budget.charge_word_cells(len(codes) * (end - start))
        found = align(codes, self.source.codes[start:end])
        if found is None:
            return None
        span = start + found.start, start + found.end
        self._found[item.serial] = found
        self._found.by_span[(item.serial, span)] = found
        return span

    def _widened(self, item: _Item, span: Span) -> Span | None:
        """*span* widened by the runs of *item*'s text it misses at the
        text's ends where trimmed blocks matched half that run or more, or
        None when there is no such run."""
        found, length = self._found[item.serial], len(item.coded.codes)
        missing, (dropped_front, dropped_back) = found.missing, found.trimmed
        if not missing:
            return None
        front = missing[0][1] if missing[0][0] == 0 else 0
        back = length - missing[-1][0] if missing[-1][1] == length else 0
        front = front if 2 * dropped_front >= front else 0
        back = back if 2 * dropped_back >= back else 0
        if not front and not back:
            return None
        return max(0, span[0] - front), min(len(self.source.codes), span[1] + back)

    def _gap(self, item: _Item) -> int:
        """The characters of the longest run of *item*'s text that its last
        alignment (``_aligned`` found one) misses."""
        missing = self._found[item.serial].missing
        if not missing:
            return 0
        return longest_gap(self._run_chars(item.coded), missing)

    def _run_chars(self, coded: CodedText) -> RunChars:
        """The token positions of *coded*'s text, worked out once."""
        if id(coded) not in self._chars:
            self._chars[id(coded)] = RunChars(coded.text)
        return self._chars[id(coded)]

    def _fit(self, item: _Item, span: Span, unbounded: bool = False) -> Fit | None:
        """How well *item*'s text fits *span*, critical words aside, or None
        under the look-alike floor: with its variable parts left out where
        the template has some (``licenseid.textmask``), for a hit and a
        look-alike alike."""
        key = (item.serial, span, unbounded)
        if key not in self._fits:
            coded, span_text = item.coded, self.source.span_text(*span)
            found = self._found.by_span.get((item.serial, span))
            if coded.regions and found is not None:
                exempt = exempt_runs(
                    coded, found.blocks, self._run_chars(coded), span_text, unbounded
                )
                fit = masked_fit(coded, exempt, self.budget)
            else:
                fit = span_fit(coded, span_text, self.budget)
            self._fits[key] = fit
        return self._fits[key]

    def _same_critical(self, item: _Item, span: Span) -> bool:
        """Whether *span* holds *item*'s critical words as often as its
        text."""
        return same_critical(item.coded, self.source.words[span[0] : span[1]])

    def scored(self, item: _Item) -> _Item | None:
        """*item* with its span, fit and exact key, or None when it is no
        hit or a kept span already claims its place.

        Dropping a span a kept one overlaps, before its characters are
        compared, is exact: a kept key is at least the bound of any item
        left. Dropping a window a kept span half covers is a measured
        shortcut."""
        if self.taken.covers_half(item.window.start, item.window.end):
            return None
        # A text that only a look-alike's fit can reach is no hit.
        if not can_reach(item.coded.least, len(self.source.text), MIN_SIMILARITY):
            return None
        span = self._hit_span(item)
        if (
            span is None
            or self.taken.overlaps(*span)
            or not self._same_critical(item, span)
            or self._gap(item) >= MAX_GAP_CHARS
        ):
            return None
        fit = self._fit(item, span)
        if fit is None or not fit.reaches(MIN_SIMILARITY):
            return None
        return item._replace(
            negative_key=-fit.key, scored=1, start=span[0], end=span[1], fit=fit
        )

    def doubted(self, hit: _Item) -> bool:
        """Whether a look-alike casts doubt on *hit*: a text of another
        group whose span meets the hit's and that keys above the hit at
        MIN_SIMILARITY or more, whatever its critical words (a hit but for
        them) or, when the hit is under SURE_SIMILARITY, keys at
        LOOKALIKE_REACH of it or more at NEAR_SIMILARITY or more with the
        same critical words. Look-alikes are scored whatever a
        kept span claims; against a masked hit, one also keys above or ties
        it with its fills unbounded (``textmask.exempt_runs``)."""
        if hit.fit is None:
            return False
        key = hit.fit.key
        # None: a sure hit, doubted only by a hit but for its critical words.
        floor = None if hit.fit.reaches(SURE_SIMILARITY) else LOOKALIKE_REACH * key
        # A key is at most the text's length; a tie reaches down to TIE_REACH
        # of the hit's (``_outkeys``).
        least = key + 1 if not hit.fit.masked else TIE_REACH * key
        if floor is not None:
            least = min(least, floor)
        first = bisect_left(self.starts, hit.start - self.widest)
        for other in self.items[first : bisect_left(self.starts, hit.end)]:
            if other.row_id == hit.row_id or len(other.coded.text) < least:
                continue
            if self._doubts(other, hit, floor):
                return True
        return False

    def _doubts(self, other: _Item, hit: _Item, floor: float | None) -> bool:
        """Whether *other* doubts *hit*: see ``doubted``."""
        span = self._span(other)
        if span is None or not _meet(span, (hit.start, hit.end)):
            return False
        if hit.fit is None:
            return False
        if hit.fit.masked:
            # The bounds that pick a name hold back no doubt: a longer text
            # whose clause no bound accepts (or whose title word is unmatched)
            # still outkeys a shorter one inside it (X11 around MIT).
            unbounded = self._fit(other, span, unbounded=True)
            if (
                unbounded is not None
                and _outkeys(unbounded, hit.fit)
                and unbounded.reaches(MIN_SIMILARITY)
            ):
                return True
        fit = self._fit(other, span)
        if fit is None:
            return False
        if _outkeys(fit, hit.fit) and fit.reaches(MIN_SIMILARITY):
            return True
        return (
            floor is not None and fit.key >= floor and self._same_critical(other, span)
        )


def _outkeys(fit: Fit, hit: Fit) -> bool:
    """Whether a look-alike's *fit* keys above the *hit*'s or, both with
    their variable parts left out, ties it: fits as closely (similarity)
    with a key at TIE_REACH of the hit's or more, unless only the hit's
    parts hold its own words. Two texts that differ only in their variable
    parts (the cores of OLDAP-1.1 and NBPL-1.0: name, version, holder) both
    fit a copy of either with its own name exactly; the length of the words
    each var holds must not pick one."""
    if fit.key > hit.key:
        return True
    return (
        fit.masked
        and hit.masked
        and not (hit.own and not fit.own)
        and fit.key >= TIE_REACH * hit.key
        and fit.distance * hit.total <= hit.distance * fit.total
    )


class Found(NamedTuple):
    """The whole texts an input holds: *rows*, the representative row IDs,
    deduped, in the order of the first kept span of each in the input, and
    *first*, that of the named span that starts first (``rows[0]``)."""

    rows: list[str]
    first: str


def _kept(heap: list[_Item], search: _Search) -> list[tuple[int, str]]:
    """``(start, row ID)`` of the hits kept, greedy by key, one per copy; a
    doubted hit claims its span and names nothing."""
    kept: list[tuple[int, str]] = []
    while heap:
        item = heapq.heappop(heap)
        if not item.scored:
            scored = search.scored(item)
            if scored is not None:
                heapq.heappush(heap, scored)
        elif not search.taken.overlaps(item.start, item.end):
            search.taken.add(item.start, item.end)
            if not search.doubted(item):
                kept.append((item.start, item.row_id))
    return kept


def found_texts(norm_input: str, corpus: TextCorpus, answer_id: str) -> Found | None:
    """The List texts the input holds whole (:class:`Found`); None when
    nothing found or past a limit.

    *norm_input* is the normalised input. A representative is the least ID
    of a same-text group (``TextCorpus.representative``); *answer_id*'s group
    wins a tie and shows by its representative too."""
    source = _read_input(norm_input, corpus)
    if source is None:
        return None
    budget = Budget()
    try:
        heap = _items(corpus, source, corpus.representative(answer_id), budget)
        kept = _kept(heap, _Search(source, heap, budget))
    except LimitReached:
        return None
    if not kept:
        return None
    rows = list(dict.fromkeys(row for _, row in sorted(kept)))
    return Found(rows, rows[0])


def found_rows(norm_input: str, corpus: TextCorpus, answer_id: str) -> list[str] | None:
    """The rows of :func:`found_texts` (representative row IDs, one per
    kept copy, deduped), sorted, or None: for tests of the search alone."""
    found = found_texts(norm_input, corpus, answer_id)
    return None if found is None else sorted(found.rows)
