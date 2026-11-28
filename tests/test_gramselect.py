# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The rules of ``licenseid.gramselect`` on made-up score tables: the
filters, the none bar, the Tier 2 selection. Numbers are written literally."""
# pylint: disable=missing-function-docstring

import pytest

from licenseid.gramselect import (
    Filters,
    ListFlags,
    filtered,
    passes,
    selected,
)
from licenseid.textgrams import GramScore

SPDX = ListFlags(True, False, False, False)
COMMON = ListFlags(True, True, False, False)
OSI = ListFlags(True, False, True, False)
FSF = ListFlags(True, False, False, True)
OFF_LIST = ListFlags(False, True, True, True)
NONE = Filters(frozenset(), only_spdx=False, only_common=False)


def table(*scores: float) -> list[GramScore]:
    """Rows L0, L1, ... in row order, with *scores*."""
    return [GramScore(f"L{at}", 10, 10, score) for at, score in enumerate(scores)]


def ids(rows: list[GramScore]) -> list[str]:
    return [row.license_id for row in rows]


# -- None bar ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("best", "kept"),
    [(0.0999, False), (0.1, True), (0.1001, True), (0.0, False)],
    ids=str,
)
def test_the_bar_reads_the_best_score(best: float, kept: bool) -> None:
    assert bool(selected(table(0.05, best, 0.01))) is kept


def test_an_empty_table_selects_none() -> None:
    assert not selected([])


def test_one_row_over_the_bar_is_selected() -> None:
    assert ids(selected(table(0.4))) == ["L0"]


# -- Selection ---------------------------------------------------------------


def test_the_top_three_are_scored_however_far_from_the_best() -> None:
    assert ids(selected(table(0.9, 0.2, 0.15, 0.12, 0.11))) == ["L0", "L1", "L2"]


@pytest.mark.parametrize(
    ("rival", "kept"),
    [(0.7, True), (0.7001, True), (0.6999, False)],
    ids=str,
)
def test_a_fourth_text_within_005_of_the_best_is_scored(
    rival: float, kept: bool
) -> None:
    # Best 0.75: 0.7 is 0.05 under it, on the edge (in, float rounding aside).
    rows = table(0.75, 0.74, 0.73, rival)
    assert ("L3" in ids(selected(rows))) is kept


@pytest.mark.parametrize(
    ("best", "rival", "kept"),
    [
        (0.9, 0.85, True),
        (0.6, 0.55, True),
        (1.0, 0.95, True),
        # 0.4 - 0.05 is 0.35000000000000003 in floats: in all the same.
        (0.4, 0.35, True),
        (0.2, 0.15, True),
        (0.9, 0.8499, False),
    ],
    ids=str,
)
def test_the_margin_edge_holds_under_float_rounding(
    best: float, rival: float, kept: bool
) -> None:
    assert ("L3" in ids(selected(table(best, best, best, rival)))) is kept


def test_the_margin_is_0_05_not_more() -> None:
    assert "L3" not in ids(selected(table(0.75, 0.75, 0.75, 0.6999)))
    assert "L3" not in ids(selected(table(0.8, 0.8, 0.8, 0.7499)))


@pytest.mark.parametrize(("rows", "count"), [(20, 20), (21, 20), (25, 20), (19, 19)])
def test_at_most_twenty_are_scored(rows: int, count: int) -> None:
    chosen = selected(table(*[0.9] * rows))
    assert len(chosen) == count
    assert ids(chosen) == [f"L{at}" for at in range(count)]


def test_equal_scores_keep_row_order() -> None:
    rows = table(0.3, 0.8, 0.3, 0.8, 0.8, 0.3)
    assert ids(selected(rows)) == ["L1", "L3", "L4"]
    assert ids(selected(list(reversed(rows)))) == ["L4", "L3", "L1"]


def test_selected_rows_are_best_first() -> None:
    assert ids(selected(table(0.5, 0.9, 0.7, 0.88))) == ["L1", "L3", "L2"]


# -- Filters -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("flags", "filters", "kept"),
    [
        (SPDX, NONE, True),
        (OFF_LIST, Filters(frozenset(), True, False), False),
        (SPDX, Filters(frozenset(), True, False), True),
        (SPDX, Filters(frozenset(), False, True), False),
        (COMMON, Filters(frozenset(), False, True), True),
        (OSI, Filters(frozenset(), False, True), True),
        (FSF, Filters(frozenset(), False, True), True),
        (OFF_LIST, Filters(frozenset(), True, True), False),
        (COMMON, Filters(frozenset({"x-1.0"}), True, True), False),
        (COMMON, Filters(frozenset({"y-1.0"}), True, True), True),
        (None, NONE, False),
    ],
    ids=[
        "no-filter",
        "spdx-only-off-list",
        "spdx-only-on-list",
        "common-only-rare",
        "common-only-high-usage",
        "common-only-osi",
        "common-only-fsf",
        "both-off-list",
        "excluded",
        "other-excluded",
        "no-row",
    ],
)
def test_passes(flags: ListFlags | None, filters: Filters, kept: bool) -> None:
    assert passes("X-1.0", flags, filters) is kept


def test_an_empty_id_never_passes() -> None:
    assert not passes("", SPDX, NONE)


def test_the_filters_act_before_the_bar() -> None:
    """The best text excluded: the bar reads the next, under it here."""
    rows = table(0.5, 0.09)
    excluded = Filters(frozenset({"l0"}), True, False)
    assert ids(selected(rows)) == ["L0", "L1"]
    assert not selected(filtered(rows, {"L0": SPDX, "L1": SPDX}, excluded))


def test_the_filters_act_before_the_selection() -> None:
    """Three filtered out above: the top three and the margin are of the rest."""
    rows = table(0.9, 0.9, 0.9, 0.5, 0.2, 0.19, 0.1)
    flags = {f"L{at}": (OFF_LIST if at < 3 else SPDX) for at in range(7)}
    kept = filtered(rows, flags, Filters(frozenset(), True, False))
    assert ids(selected(kept)) == ["L3", "L4", "L5"]


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        (NONE, ["L0", "L1", "L2", "L3"]),
        (Filters(frozenset({"l0"}), False, False), ["L1", "L2", "L3"]),
        (Filters(frozenset(), True, False), ["L0", "L2", "L3"]),
        (Filters(frozenset(), False, True), ["L1", "L2"]),
        (Filters(frozenset({"l2"}), True, True), []),
    ],
    ids=["none", "exclude", "only-spdx", "only-common", "all-three"],
)
def test_each_filter_alone_and_together(filters: Filters, expected: list[str]) -> None:
    rows = table(0.4, 0.3, 0.2, 0.1)
    flags = {"L0": SPDX, "L1": OFF_LIST, "L2": COMMON, "L3": SPDX}
    assert ids(filtered(rows, flags, filters)) == expected


def test_filtered_keeps_row_order_and_drops_rows_with_no_flags() -> None:
    rows = table(0.1, 0.9, 0.5)
    assert ids(filtered(rows, {"L0": SPDX, "L2": SPDX}, NONE)) == ["L0", "L2"]
