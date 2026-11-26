# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Whether a look-alike casts doubt on a hit of the whole-text search
(``licenseid.wholetexts``): a kept span names nothing when a text of another
same-text group fits a span overlapping it about as well.

A look-alike doubts a hit when it keys above it at MIN_SIMILARITY or more,
whatever its critical words (a hit refused only by a critical word: a word
dropped from the true text must not name a look-alike); or, for a hit under
SURE_SIMILARITY, keys at LOOKALIKE_REACH of it or more at NEAR_SIMILARITY or
more with the same critical words (the input is about as close to either
text); or, both fits with their variable parts left out
(``licenseid.textmask``), ties it: keys at TIE_REACH of it or more as
closely (two texts that differ only in their variable parts). Against a hit
fitted with its variable parts left out, the look-alike's parts are left out
with no bound on their fills (``textmask.exempt_runs``) too: a clause too
long for FILL_SLACK in a longer text must not name a shorter text inside it.
A doubtful name is worse than none.

Measurements: ``working-docs/implementation/whole-texts.md``.
"""

from bisect import bisect_left
from collections.abc import Sequence
from typing import Final, Protocol, TypeVar

from licenseid.textcorpus import CodedText, Span
from licenseid.textlocate import MIN_SIMILARITY, SURE_SIMILARITY, Fit

#: A look-alike's key is at least this share of the hit's: a text of about
#: the same extent. A text the hit holds as a part (PSF-2.0 in Python-2.0.1,
#: a key of a quarter) is no look-alike. On the real licence files any share
#: from 0.80 to 0.93 gives the same answers (TEXTS measurements).
LOOKALIKE_REACH: Final = 0.90
#: Two masked fits whose keys are this close tie (``outkeys``): the cores
#: of OLDAP-1.1 and NBPL-1.0 key 4,537 and 4,591 (0.988). At 0.90 a nested
#: text that fits its shorter span more closely (SMLNJ's core in Pillow's
#: MIT-CMU, 0.954) doubts the true one.
TIE_REACH: Final = 0.98


class Candidate(Protocol):
    """A window of the search: its text, its place, and its fit once
    scored."""

    @property
    def row_id(self) -> str:
        """Its same-text group."""

    @property
    def start(self) -> int:
        """Its first input token."""

    @property
    def end(self) -> int:
        """The input token after its last."""

    @property
    def coded(self) -> CodedText:
        """Its text (or core)."""

    @property
    def fit(self) -> Fit | None:
        """Its fit, once scored."""


ItemT = TypeVar("ItemT", bound=Candidate)


class Looks(Protocol[ItemT]):
    """The search a look-alike is read from (``wholetexts._Search``): every
    window by where its padded window starts, the widest, and the span and
    fit of each, worked out once."""

    @property
    def items(self) -> Sequence[ItemT]:
        """Every window, by the start of its padded window."""

    @property
    def starts(self) -> Sequence[int]:
        """The start of each padded window of ``items``."""

    @property
    def widest(self) -> int:
        """The widest padded window."""

    def span(self, item: ItemT) -> Span | None:
        """Where *item*'s text sits in its window, or None."""

    def fit(self, item: ItemT, span: Span, unbounded: bool = False) -> Fit | None:
        """How well *item*'s text fits *span*, or None."""

    def same_critical(self, item: ItemT, span: Span) -> bool:
        """Whether *span* holds *item*'s critical words as often as its
        text."""


def meet(first: Span, second: Span) -> bool:
    """Whether two spans overlap by more than a tenth of the shorter."""
    shared = min(first[1], second[1]) - max(first[0], second[0])
    return 10 * shared > min(first[1] - first[0], second[1] - second[0])


def doubted(search: Looks[ItemT], hit: ItemT) -> bool:
    """Whether a look-alike casts doubt on *hit*: a text of another group
    whose span meets the hit's and that keys above the hit at MIN_SIMILARITY
    or more, whatever its critical words (a hit but for them) or, when the
    hit is under SURE_SIMILARITY, keys at LOOKALIKE_REACH of it or more at
    NEAR_SIMILARITY or more with the same critical words. Look-alikes are
    scored whatever a kept span claims; against a masked hit, one also keys
    above or ties it with its fills unbounded (``textmask.exempt_runs``)."""
    if hit.fit is None:
        return False
    key = hit.fit.key
    # None: a sure hit, doubted only by a hit but for its critical words.
    floor = None if hit.fit.reaches(SURE_SIMILARITY) else LOOKALIKE_REACH * key
    # A key is at most the text's length; a tie reaches down to TIE_REACH
    # of the hit's (``outkeys``).
    least = key + 1 if not hit.fit.masked else TIE_REACH * key
    if floor is not None:
        least = min(least, floor)
    first = bisect_left(search.starts, hit.start - search.widest)
    for other in search.items[first : bisect_left(search.starts, hit.end)]:
        if other.row_id == hit.row_id or len(other.coded.text) < least:
            continue
        if _doubts(search, other, hit, floor):
            return True
    return False


def _doubts(
    search: Looks[ItemT], other: ItemT, hit: ItemT, floor: float | None
) -> bool:
    """Whether *other* doubts *hit*: see ``doubted``."""
    span = search.span(other)
    if span is None or not meet(span, (hit.start, hit.end)):
        return False
    if hit.fit is None:
        return False
    if hit.fit.masked:
        # The bounds that pick a name hold back no doubt: a longer text
        # whose clause no bound accepts (or whose title word is unmatched)
        # still outkeys a shorter one inside it (X11 around MIT).
        unbounded = search.fit(other, span, unbounded=True)
        if (
            unbounded is not None
            and outkeys(unbounded, hit.fit)
            and unbounded.reaches(MIN_SIMILARITY)
        ):
            return True
    fit = search.fit(other, span)
    if fit is None:
        return False
    if outkeys(fit, hit.fit) and fit.reaches(MIN_SIMILARITY):
        return True
    return floor is not None and fit.key >= floor and search.same_critical(other, span)


def outkeys(fit: Fit, hit: Fit) -> bool:
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
