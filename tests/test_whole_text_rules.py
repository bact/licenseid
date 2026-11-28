# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""The rules of whole text first on made-up score tables
(``licenseid.gramselect``): the texts the whole-text search reads, the
guard, the narrowing and its runner-ups; the rule that leaves out a
runner-up nothing names beside the text found (``ranking.under_found``); and
``variants`` sorting with the one ranking key. Numbers are written
literally."""
# pylint: disable=missing-function-docstring

from typing import Any

import pytest

from licenseid.gramselect import guarded, is_held, narrowed, searched
from licenseid.grantsubject import Signals, constant
from licenseid.ranking import under_found
from licenseid.textcorpus import TextCorpus, TextRow
from licenseid.textgrams import GramScore
from licenseid.variants import settle_text


def row(license_id: str, shared: int, size: int, score: float = 0.5) -> GramScore:
    return GramScore(license_id, shared, size, score)


def no_core(_license_id: str) -> int | None:
    return None


def ids(rows: Any) -> list[str]:
    return [r.license_id for r in rows]


# -- The texts the search reads ----------------------------------------------


@pytest.mark.parametrize(
    ("shared", "size", "held"),
    [(50, 100, True), (49, 100, False), (100, 100, True), (51, 101, True)],
    ids=["half", "under-half", "whole", "odd-size"],
)
def test_a_text_is_held_from_half_of_its_grams(
    shared: int, size: int, held: bool
) -> None:
    assert is_held(row("A", shared, size), no_core) is held


@pytest.mark.parametrize(
    ("core", "held"),
    [(60, True), (61, False), (None, False), (500, False)],
    ids=["core-half", "core-under-half", "no-core", "core-larger"],
)
def test_the_core_counts_where_it_is_smaller(core: int | None, held: bool) -> None:
    """30 of the text's 100 grams: under half; of a core of 60, half."""
    asked: list[str] = []

    def core_grams(license_id: str) -> int | None:
        asked.append(license_id)
        return core

    assert is_held(row("A", 30, 100), core_grams) is held
    assert asked == ["A"]


def test_the_core_is_not_asked_of_a_text_held_alone() -> None:
    def core_grams(license_id: str) -> int | None:
        raise AssertionError(license_id)

    assert is_held(row("A", 50, 100), core_grams)


def test_the_search_reads_the_top_20_and_every_text_held() -> None:
    top = [row(f"T{at:02}", 10, 100, 0.9 - at / 100) for at in range(22)]
    held = row("H", 60, 100, 0.01)  # far down the scores, held more than half
    rows = [held, *top]
    assert searched(rows, no_core) == [f"T{at:02}" for at in range(20)] + ["H"]


def test_fewer_than_20_texts_are_all_read() -> None:
    rows = [row("A", 1, 100, 0.01), row("B", 2, 100, 0.02)]
    assert searched(rows, no_core) == ["B", "A"]


def test_no_text_no_search() -> None:
    assert not searched([], no_core)


# -- Guard -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("other", "guards"),
    [(11, False), (12, True), (10, False), (100, True)],
    ids=["1.1-times", "over-1.1", "equal", "far-more"],
)
def test_the_guard_reads_another_text_sharing_more_than_1_1_times(
    other: int, guards: bool
) -> None:
    rows = [row("FOUND", 10, 40), row("LONGER", other, 400)]
    assert guarded(rows, {"FOUND"}) is guards


def test_the_guard_takes_the_best_member_of_the_group() -> None:
    rows = [row("F-only", 10, 40), row("F-or-later", 20, 40), row("X", 21, 400)]
    assert not guarded(rows, {"F-only", "F-or-later"})
    assert guarded(rows, {"F-only"})


def test_a_group_with_no_row_is_guarded_by_any_other() -> None:
    assert guarded([row("X", 1, 40)], {"FOUND"})
    assert not guarded([], {"FOUND"})


# -- Narrowing ---------------------------------------------------------------


def table(*scores: tuple[str, float]) -> list[GramScore]:
    return [row(license_id, 10, 40, score) for license_id, score in scores]


ROWS = table(
    ("R1", 0.9), ("F", 0.85), ("F-twin", 0.85), ("R2", 0.5), ("R3", 0.3), ("R4", 0.2)
)


def test_the_group_first_then_three_runner_ups_in_gram_order() -> None:
    narrow = narrowed(ROWS, ROWS, {"F", "F-twin"})
    assert narrow is not None
    assert ids(narrow.rows) == ["F", "F-twin", "R1", "R2", "R3"]
    assert narrow.group == {"F", "F-twin"}
    assert narrow.runner_ups == {"R1", "R2", "R3"}


@pytest.mark.parametrize(
    ("score", "kept"),
    [(0.1, True), (0.0999, False), (0.1001, True)],
    ids=str,
)
def test_a_runner_up_reaches_the_none_bar(score: float, kept: bool) -> None:
    rows = table(("F", 0.9), ("R", score))
    narrow = narrowed(rows, rows, {"F"})
    assert narrow is not None
    assert ("R" in narrow.runner_ups) is kept


def test_fewer_runner_ups_when_fewer_reach_the_bar() -> None:
    rows = table(("F", 0.9), ("R1", 0.2), ("R2", 0.05))
    narrow = narrowed(rows, rows, {"F"})
    assert narrow is not None and ids(narrow.rows) == ["F", "R1"]


def test_a_filtered_member_is_not_scored() -> None:
    passed = [r for r in ROWS if r.license_id != "F-twin"]
    narrow = narrowed(ROWS, passed, {"F", "F-twin"})
    assert narrow is not None
    assert ids(narrow.rows) == ["F", "R1", "R2", "R3"]


def test_a_found_text_the_filters_took_out_does_not_narrow() -> None:
    passed = [r for r in ROWS if not r.license_id.startswith("F")]
    assert narrowed(ROWS, passed, {"F", "F-twin"}) is None


def test_filtered_runner_ups_are_not_scored() -> None:
    passed = [r for r in ROWS if r.license_id not in ("R1", "R2")]
    narrow = narrowed(ROWS, passed, {"F", "F-twin"})
    assert narrow is not None and narrow.runner_ups == {"R3", "R4"}


def test_the_guard_reads_the_unfiltered_table() -> None:
    """A longer text that shares more stops the narrowing even when a
    filter takes it out: the guard reads the input, not the options."""
    rows = [row("F", 10, 40, 0.9), row("LONG", 20, 400, 0.6)]
    passed = rows[:1]
    assert narrowed(rows, passed, {"F"}) is None
    assert narrowed(rows[:1], passed, {"F"}) is not None


# -- Runner-ups nothing names are no results beside the text found -----------


def match(license_id: str, score: float) -> Any:
    return {"license_id": license_id, "score": score}


def left(
    ranked: list[Any], group: set[str], runner_ups: set[str], named: Any = ()
) -> list[str]:
    return [m["license_id"] for m in under_found(ranked, group, runner_ups, named)]


@pytest.mark.parametrize("score", [0.3, 0.94, 0.95, 0.96], ids=str)
def test_an_unnamed_runner_up_is_left_out_whatever_it_scores(score: float) -> None:
    """Under the answer (0.3; 0.94, a near tie), equal to it and above it."""
    ranked = sorted(
        [match("F", 0.95), match("R", score), match("Q", 0.5)],
        key=lambda m: -m["score"],
    )
    assert left(ranked, {"F"}, {"R", "Q"}) == ["F"]
    assert left(ranked, {"F"}, {"R", "Q"}, ["Other-1.0"]) == ["F"]


@pytest.mark.parametrize(
    ("score", "kept"),
    [(0.3, True), (0.94, True), (0.95, False), (0.96, False)],
    ids=["under", "near", "equal", "above"],
)
def test_a_named_runner_up_stays_only_under_the_answer(
    score: float, kept: bool
) -> None:
    ranked = [match("F", 0.95), match("R", score), match("Q", 0.5)]
    assert left(ranked, {"F"}, {"R", "Q"}, ["R"]) == (["F", "R"] if kept else ["F"])


@pytest.mark.parametrize(
    "named",
    ["GPL-2.0", "gpl-2.0", "GPL-2.0-only", "GPL-2.0-or-later", "GPL-2.0+"],
)
def test_a_name_stands_for_both_twins(named: str) -> None:
    """A bare deprecated ID, either twin, any case: the pair stays, so the
    tie-breaker and ``variants`` read both rows."""
    ranked = [
        match("F", 0.95),
        match("GPL-2.0-only", 0.6),
        match("GPL-2.0-or-later", 0.59),
        match("LGPL-2.0-only", 0.5),
    ]
    runner_ups = {"GPL-2.0-only", "GPL-2.0-or-later", "LGPL-2.0-only"}
    assert left(ranked, {"F"}, runner_ups, [named]) == [
        "F",
        "GPL-2.0-only",
        "GPL-2.0-or-later",
    ]


def test_every_member_of_the_group_stays() -> None:
    ranked = [match("F-twin", 0.97), match("R", 0.96), match("F", 0.9)]
    assert left(ranked, {"F", "F-twin"}, {"R"}) == ["F-twin", "F"]


def test_the_best_member_of_the_group_is_the_bar() -> None:
    ranked = [match("F-twin", 0.97), match("R", 0.96), match("F", 0.9)]
    assert left(ranked, {"F", "F-twin"}, {"R"}, ["R"]) == ["F-twin", "R", "F"]


def test_a_candidate_that_is_no_runner_up_stays() -> None:
    """A marker's candidate merged after the grams is no runner-up, above
    the text found or under it."""
    ranked = [match("MARKER", 0.99), match("F", 0.9), match("R", 0.8), match("H", 0.2)]
    assert left(ranked, {"F"}, {"R"}) == ["MARKER", "F", "H"]


def test_no_member_of_the_group_ranked_leaves_all() -> None:
    ranked = [match("R", 0.99), match("Q", 0.5)]
    assert under_found(ranked, {"F"}, {"R", "Q"}) == ranked


# -- The size of a core --------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "grams"),
    [
        ("a b c d e", 3),
        ("a b a b a b", 2),  # "a b a", "b a b": repeats counted once
        ("a b", 0),
        ("a b c", 1),
    ],
    ids=["five-words", "repeats", "two-words", "three-words"],
)
def test_a_texts_distinct_grams(text: str, grams: int) -> None:
    corpus = TextCorpus.build([TextRow("X-1.0", text, None, ("X-1.0",))])
    assert corpus.entries[0].text.gram_count == grams


# -- variants sorts with the one ranking key ------------------------------------


def text_hit(license_id: str, score: float, **more: Any) -> Any:
    return {
        "license_id": license_id,
        "method": "text",
        "exact": False,
        "score": score,
        "similarity": score,
        "coverage": 1.0,
        "pop_score": 0,
        **more,
    }


def test_settled_results_sort_by_the_ranking_key() -> None:
    """Equal scores by ID, and a deprecated row 0.03 under its score, as the
    detector sorts them (``ranking.ranking_key``), not in arrival order."""
    hits = [
        text_hit("Z-1.0", 0.9),
        text_hit("A-1.0", 0.9),
        text_hit("D-1.0", 0.91, is_deprecated=True),
    ]
    out = settle_text(hits, Signals(constant(False)), "auto")
    assert [r["license_id"] for r in out] == ["A-1.0", "Z-1.0", "D-1.0"]


def test_popularity_breaks_a_tie_when_asked() -> None:
    hits = [text_hit("A-1.0", 0.9), text_hit("B-1.0", 0.9, pop_score=5)]
    signals = Signals(constant(False))
    assert [r["license_id"] for r in settle_text(hits, signals, "auto")] == [
        "A-1.0",
        "B-1.0",
    ]
    out = settle_text(hits, signals, "auto", popular=True)
    assert [r["license_id"] for r in out] == ["B-1.0", "A-1.0"]


def test_as_written_sorts_by_the_ranking_key_too() -> None:
    hits = [text_hit("Z-1.0", 0.9), text_hit("A-1.0", 0.9)]
    out = settle_text(hits, Signals(constant(False)), "as-written")
    assert [r["license_id"] for r in out] == ["A-1.0", "Z-1.0"]
