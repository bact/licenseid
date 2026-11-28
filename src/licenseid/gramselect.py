# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Which List texts Tier 2 scores: rules over a table of gram scores
(``licenseid.textgrams.GramTable``), with no database and no detector state.

Tier 1 looks the word 3-grams of the input up in the stored postings
(``licenseid.database.gram_scores``, once per ``detect()`` call); every text
that shares a gram has a score, ``shared / min(grams of the input, grams of
the text)``. Then, in this order (plan of 0.10.0, section 3.1):

1. **Filters.** ``exclude``, ``only_spdx`` and ``only_common`` take their IDs
   out of the table (:func:`filtered`), before any rule below reads it, so
   the bar and the selection see only what may answer: the best text
   excluded, the bar reads the next. ``TEXTS`` and ``texts()`` read no
   filter.
2. **None.** A best score under :data:`NONE_BAR` gives no candidate: no
   input that answers scores under 0.4, and the rows such an input would
   list are noise on prose.
3. **Selection.** Tier 2 scores the first :data:`TOP` by score and every
   text within :data:`MARGIN` of the best, at most :data:`MOST`; of equal
   scores the earlier row first (``textgrams.ranked``), never an order a
   hash gives.

The whole-text search of ``TEXTS`` reads the texts :func:`searched` gives,
of the unfiltered table (``licenseid.textcandidates``). When it finds exactly
one text, Tier 2 scores that text's same-text group and runner-ups instead
of the selection (:func:`narrowed`), unless the guard holds.

The markers and the hinted licences join after these, also when the bar left
none (``licenseid.retrieval.add_free_text``). An input of very many distinct
grams has only its first :data:`GRAM_LIMIT` looked up.
"""

from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from fractions import Fraction
from math import isclose
from typing import Final, NamedTuple

from licenseid.listlookup import fold_case
from licenseid.textgrams import GramScore, ranked

#: A best score under this gives no gram candidate. Measured on the core set
#: (868 inputs): bars of 0.3, 0.1 and 0 move no answer; 0.1 lists the low
#: rows of 99 of 125 inputs with no answer, at the cost of 0.3.
NONE_BAR: Final = 0.1
#: Texts Tier 2 scores whatever their distance from the best.
TOP: Final = 3
#: Texts within this of the best score are scored too: a margin of 0.05
#: holds the true text as often as one of 0.25.
MARGIN: Final = 0.05
#: At most this many texts are scored.
MOST: Final = 20
#: Distinct grams of an input looked up, the first ones in input order. Past
#: it the candidates come from the grams read and ``TEXTS`` is None, never a
#: partial list (the whole-text search would refuse such an input anyway:
#: over ``textlocate.MAX_INPUT_TOKENS`` tokens). No List text comes near it
#: (GPL-3.0 has about 5,000 distinct grams).
GRAM_LIMIT: Final = 50_000
#: The whole-text search reads the first texts by score, this many...
SEARCHED_TOP: Final = 20
#: ... and every text the input holds this share of the grams of, or of its
#: core's where that is smaller: a file of many texts holds each whole, far
#: down the scores (``TEXTS`` equal to a search of every text on the 868
#: inputs of the core set and the 165 of the many-text set).
HELD: Final = 0.5
#: No narrowing when another text shares more than this times the grams the
#: text found shares: a shorter text held whole inside a fragment of a longer
#: one (``SSH-short`` in an ``SSH-OpenSSH`` head). Any margin from 1.02 to
#: 1.25 gives the same result.
GUARD_MARGIN: Final = Fraction(11, 10)
#: Texts Tier 2 scores beside a text found whole, in gram order, each scoring
#: :data:`NONE_BAR` or more (decision D3 of the plan).
RUNNER_UPS: Final = 3


class ListFlags(NamedTuple):
    """What the filters read of a licence's row."""

    is_spdx: bool
    is_high_usage: bool
    is_osi_approved: bool
    is_fsf_libre: bool


class Filters(NamedTuple):
    """The filters of a ``detect()`` call."""

    #: Case-folded, a bare deprecated ID with its twins
    #: (``licenseid.idoptions.excluded_ids``).
    excluded: frozenset[str]
    only_spdx: bool
    only_common: bool


def passes(license_id: str, flags: ListFlags | None, filters: Filters) -> bool:
    """Whether the licence *license_id*, of row *flags* (None: no row), may
    answer under *filters*: not excluded, on the List if ``only_spdx``, and
    if ``only_common`` widely used or OSI-approved or FSF-libre."""
    if flags is None or not license_id or fold_case(license_id) in filters.excluded:
        return False
    if filters.only_spdx and not flags.is_spdx:
        return False
    return not filters.only_common or (
        flags.is_high_usage or flags.is_osi_approved or flags.is_fsf_libre
    )


def filtered(
    rows: Iterable[GramScore], flags: Mapping[str, ListFlags], filters: Filters
) -> list[GramScore]:
    """The *rows* that pass *filters* (*flags* by licence ID), in their
    order."""
    return [
        row
        for row in rows
        if passes(row.license_id, flags.get(row.license_id), filters)
    ]


def selected(rows: Sequence[GramScore]) -> list[GramScore]:
    """The texts of *rows* (filtered) that Tier 2 scores, best first: none
    when the best scores under :data:`NONE_BAR`, else the first :data:`TOP`
    and those within :data:`MARGIN` of the best, at most :data:`MOST`. A
    score on the edge of the margin, up to float rounding, is in."""
    order = ranked(rows)
    if not order or order[0].score < NONE_BAR:
        return []
    edge = order[0].score - MARGIN
    return [
        row
        for at, row in enumerate(order[:MOST])
        if at < TOP or row.score >= edge or isclose(row.score, edge)
    ]


def is_held(row: GramScore, core_grams: Callable[[str], int | None]) -> bool:
    """Whether the input holds :data:`HELD` of the grams of *row*'s text, or
    of its core's where that is smaller (*core_grams* by licence ID; None:
    no core). The core is asked only when the text alone falls short."""
    if row.shared >= HELD * row.size:
        return True
    core = core_grams(row.license_id)
    return core is not None and row.shared >= HELD * min(core, row.size)


def searched(
    rows: Sequence[GramScore], core_grams: Callable[[str], int | None]
) -> list[str]:
    """The licence IDs whose texts the whole-text search reads: of *rows*
    (unfiltered), the first :data:`SEARCHED_TOP` by score and every other
    one :func:`is_held`, best first."""
    order = ranked(rows)
    return [
        row.license_id
        for at, row in enumerate(order)
        if at < SEARCHED_TOP or is_held(row, core_grams)
    ]


def guarded(rows: Iterable[GramScore], group: Collection[str]) -> bool:
    """Whether a text of *rows* shares more than :data:`GUARD_MARGIN` times
    the grams that *group*, the same-text group of the one text found,
    shares with the input at best (so no member of it does): then the found
    text explains less of the input than that one, and Tier 2 is not
    narrowed to it."""
    rows = list(rows)
    own = max((row.shared for row in rows if row.license_id in group), default=0)
    # In whole numbers: a Fraction a row costs a millisecond on a long input.
    limit = own * GUARD_MARGIN.numerator
    return any(row.shared * GUARD_MARGIN.denominator > limit for row in rows)


class Narrowed(NamedTuple):
    """What Tier 2 scores beside a text found whole."""

    #: The texts to score: the group's first, then the runner-ups.
    rows: tuple[GramScore, ...]
    #: The IDs of the found text's same-text group.
    group: frozenset[str]
    #: The IDs of the runner-ups: each is left out where it scores as high as
    #: the group or higher (decision Q1 of the plan).
    runner_ups: frozenset[str]


def narrowed(
    rows: Sequence[GramScore], passed: Sequence[GramScore], group: Collection[str]
) -> Narrowed | None:
    """The texts Tier 2 scores when the search found one text, *group* its
    same-text group: the members of *group* the filters left (*passed*, the
    filtered *rows*), then the first :data:`RUNNER_UPS` others of *passed*
    by score that reach :data:`NONE_BAR`. None, the selection then, when the
    filters took every member out or :func:`guarded` holds."""
    if guarded(rows, group):
        return None
    order = ranked(passed)
    own = [row for row in order if row.license_id in group]
    if not own:
        return None
    rivals = [
        row for row in order if row.license_id not in group and row.score >= NONE_BAR
    ][:RUNNER_UPS]
    return Narrowed(
        tuple(own + rivals),
        frozenset(group),
        frozenset(row.license_id for row in rivals),
    )
