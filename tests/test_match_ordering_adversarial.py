# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Adversarial cover for the ranking key, the -only / -or-later tie-breaker
and its phrase detector: a differential reference for the sort order, a
sweep of the tie window, property checks over seeded random lists, the
phrase matrix with its negations and known limits, and a backtracking
guard. Attacks the contract, not the implementation."""
# pylint: disable=redefined-outer-name,missing-function-docstring
# pylint: disable=protected-access

import random
import time
from collections.abc import Callable, Generator
from functools import cmp_to_key, partial
from typing import cast

import pytest
from matcher_db import Lic, seeded_db
from ordering_helpers import HEADER_OR_LATER, ids, im

from licenseid.classify import OR_LATER_PHRASE, has_or_later_language
from licenseid.identifiers import disambiguate_deprecated_id
from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.normalize import normalize_text
from licenseid.ranking import (
    DEP_PENALTY,
    TIE_WINDOW,
    apply_version_suffix_tiebreaker,
    ranking_key,
)
from licenseid.types import InternalMatch

ONLY = "GPL-2.0-only"
OR_LATER = "GPL-2.0-or-later"
NO_GRANT = "version 2 of the license"


def scores_of(ranked: list[InternalMatch]) -> dict[str, float]:
    return {r["license_id"]: r["score"] for r in ranked}


def fresh(ranked: list[InternalMatch]) -> list[InternalMatch]:
    """A copy the tie-breaker cannot write through: it nudges the scores of
    the entries it is given, in place."""
    return [cast(InternalMatch, dict(r)) for r in ranked]


# -- An independent reference for clause A --------------------------------


def _reference_cmp(
    left: InternalMatch, right: InternalMatch, *, enable_popularity: bool
) -> int:
    """Clause A written out directly, with no shared code."""
    left_score = left["score"] - (DEP_PENALTY if left.get("is_deprecated") else 0.0)
    right_score = right["score"] - (DEP_PENALTY if right.get("is_deprecated") else 0.0)
    if left_score != right_score:
        return -1 if left_score > right_score else 1
    left_dep = bool(left.get("is_deprecated"))
    right_dep = bool(right.get("is_deprecated"))
    if left_dep != right_dep:
        return 1 if left_dep else -1
    if enable_popularity:
        left_pop = left.get("pop_score", 0)
        right_pop = right.get("pop_score", 0)
        if left_pop != right_pop:
            return -1 if left_pop > right_pop else 1
    if left["license_id"] != right["license_id"]:
        return -1 if left["license_id"] < right["license_id"] else 1
    return 0


def reference_sort(
    items: list[InternalMatch], *, enable_popularity: bool
) -> list[InternalMatch]:
    return sorted(
        items,
        key=cmp_to_key(partial(_reference_cmp, enable_popularity=enable_popularity)),
    )


_PAIR_IDS = frozenset({ONLY, OR_LATER, "LGPL-2.1-only", "LGPL-2.1-or-later"})
_ID_POOL = sorted(_PAIR_IDS) + ["MIT", "Apache-2.0", "Zlib", "Old-1.0"]


def random_list(rng: random.Random, *, size: int | None = None) -> list[InternalMatch]:
    """Scores on a 0.001 grid over 0.300..1.050, so ties and near-ties are
    common; deprecation and popularity mixed in."""
    chosen = rng.sample(_ID_POOL, size or rng.randint(1, len(_ID_POOL)))
    return [
        im(
            license_id,
            rng.randrange(300, 1051) / 1000,
            deprecated=rng.random() < 0.4,
            pop=rng.choice([0, 0, 1, 7, 1000]),
        )
        for license_id in chosen
    ]


def describe(items: list[InternalMatch]) -> str:
    """The exact input of a failing property run, for the repro."""
    return " ".join(
        f"{r['license_id']}={r['score']}"
        f"/dep={bool(r.get('is_deprecated'))}/pop={r.get('pop_score', 0)}"
        for r in items
    )


# -- Clause A: the ranking key --------------------------------------------


@pytest.mark.parametrize("enable_popularity", [False, True])
def test_theranking_key_agrees_with_an_independent_reference(
    enable_popularity: bool,
) -> None:
    rng = random.Random(20260920 + int(enable_popularity))
    key = ranking_key(enable_popularity)
    for _ in range(500):
        items = random_list(rng)
        got = sorted(items, key=key)
        want = reference_sort(items, enable_popularity=enable_popularity)
        assert ids(got) == ids(want), describe(items)


@pytest.mark.parametrize("enable_popularity", [False, True])
def test_the_order_does_not_depend_on_the_input_order(
    enable_popularity: bool,
) -> None:
    """A tie-heavy list sorts to one order from every permutation."""
    base = [
        im("MIT", 0.90),
        im("Apache-2.0", 0.90, pop=7),
        im("Zlib", 0.90, deprecated=True),
        im("Old-1.0", 0.93, deprecated=True),
        im("Canon-1.0", 0.90, pop=7),
    ]
    key = ranking_key(enable_popularity)
    expected = ids(sorted(base, key=key))
    rng = random.Random(11)
    for _ in range(200):
        shuffled = list(base)
        rng.shuffle(shuffled)
        assert ids(sorted(shuffled, key=key)) == expected


def bare(license_id: str, score: float) -> InternalMatch:
    """An InternalMatch without is_deprecated and without pop_score."""
    scored = {k: score for k in ("score", "similarity", "coverage", "base_score")}
    return cast(
        InternalMatch,
        {"license_id": license_id, "best_window": "", **scored},
    )


@pytest.mark.parametrize(
    ("enable_popularity", "expected"),
    [
        (False, ["A-1.0", "B-1.0", "C-1.0"]),
        (True, ["B-1.0", "A-1.0", "C-1.0"]),
    ],
)
def test_missing_keys_mean_not_deprecated_and_zero_popularity(
    enable_popularity: bool, expected: list[str]
) -> None:
    """A-1.0 carries neither key: it sorts ahead of the deprecated C-1.0,
    and behind B-1.0 only when popularity counts."""
    items = [
        bare("A-1.0", 0.9),
        im("B-1.0", 0.9, pop=1),
        im("C-1.0", 0.9, deprecated=True),
    ]
    assert ids(sorted(items, key=ranking_key(enable_popularity))) == expected


@pytest.mark.parametrize(
    ("enable_popularity", "expected"),
    [
        (False, ["A-1.0", "B-1.0", "C-1.0"]),
        (True, ["C-1.0", "A-1.0", "B-1.0"]),
    ],
)
def test_extreme_popularity_values_only_count_when_enabled(
    enable_popularity: bool, expected: list[str]
) -> None:
    items = [
        im("A-1.0", 0.5, pop=0),
        im("B-1.0", 0.5, pop=-5),
        im("C-1.0", 0.5, pop=10**18),
    ]
    assert ids(sorted(items, key=ranking_key(enable_popularity))) == expected


def test_boundary_scores_still_order_by_score_then_id() -> None:
    items = [
        im("B-1.0", 0.0),
        im("A-1.0", 0.0),
        im("D-1.0", 1.05),
        im("C-1.0", 1.05, deprecated=True),
    ]
    order = ["D-1.0", "C-1.0", "A-1.0", "B-1.0"]
    assert ids(sorted(items, key=ranking_key(False))) == order


# -- Clause B: the tie window ---------------------------------------------


def pair_sorted(only: float, or_later: float) -> list[InternalMatch]:
    return sorted([im(ONLY, only), im(OR_LATER, or_later)], key=ranking_key(False))


@pytest.mark.parametrize("raw_text", [HEADER_OR_LATER, NO_GRANT])
def test_the_tie_window_depends_on_the_gap_and_the_signal_only(raw_text: str) -> None:
    """Scores 0.30..1.05, gaps -0.012..+0.012 (both orderings of the pair):
    a tie iff the gap is under 0.01, and then the preferred ID wins."""
    preferred = OR_LATER if raw_text == HEADER_OR_LATER else ONLY
    failures: list[str] = []
    for step in range(76):
        low = round(0.30 + step * 0.01, 3)
        for gap_step in range(-12, 13):
            gap = round(gap_step * 0.001, 3)
            given = pair_sorted(low, round(low + gap, 3))
            before = scores_of(given)
            result = apply_version_suffix_tiebreaker(
                fresh(given), raw_text, is_pure=False
            )
            tie = round(abs(before[ONLY] - before[OR_LATER]), 9) < TIE_WINDOW
            changed = scores_of(result) != before
            first = ids(result)[0]
            want_first = preferred if tie else ids(given)[0]
            if changed != tie or first != want_first:
                failures.append(
                    f"low={low} gap={gap} tie={tie} changed={changed}"
                    f" first={first} want={want_first}"
                )
    assert not failures, failures[:5]


def test_pure_license_text_prefers_only_even_with_granting_language() -> None:
    result = apply_version_suffix_tiebreaker(
        pair_sorted(0.90, 0.90), HEADER_OR_LATER, is_pure=True
    )
    assert ids(result)[0] == ONLY


@pytest.mark.parametrize(
    ("peer", "reason"),
    [("MIT", "no -or-later peer"), ("gpl-2.0-or-later", "IDs are case-sensitive")],
)
def test_a_pair_that_is_not_a_pair_is_left_alone(peer: str, reason: str) -> None:
    given = [im(ONLY, 0.90), im(peer, 0.899)]
    result = apply_version_suffix_tiebreaker(
        fresh(given), HEADER_OR_LATER, is_pure=False
    )
    assert ids(result) == [ONLY, peer], reason
    assert scores_of(result) == scores_of(given), reason


def test_several_pairs_are_nudged_independently() -> None:
    given = [
        im(ONLY, 0.90),
        im(OR_LATER, 0.90),
        im("LGPL-2.1-only", 0.70),
        im("LGPL-2.1-or-later", 0.70),
        im("MIT", 0.60),
    ]
    result = apply_version_suffix_tiebreaker(
        fresh(given), HEADER_OR_LATER, is_pure=False
    )
    assert ids(result) == [OR_LATER, ONLY, "LGPL-2.1-or-later", "LGPL-2.1-only", "MIT"]
    assert scores_of(result)["MIT"] == 0.60


# -- Clause B: properties over random lists -------------------------------


def tiebreaker_input(
    rng: random.Random, *, enable_pop: bool = False
) -> list[InternalMatch]:
    items = random_list(rng, size=rng.randint(2, len(_ID_POOL)))
    return sorted(items, key=ranking_key(enable_pop))


@pytest.mark.parametrize("enable_pop", [False, True])
def test_the_result_is_always_sorted_and_keeps_outside_scores(enable_pop: bool) -> None:
    rng = random.Random(4242 + int(enable_pop))
    key = ranking_key(enable_pop)
    for _ in range(300):
        given = tiebreaker_input(rng, enable_pop=enable_pop)
        before = scores_of(given)
        result = apply_version_suffix_tiebreaker(
            fresh(given), HEADER_OR_LATER, is_pure=False, enable_pop=enable_pop
        )
        assert set(ids(result)) == set(ids(given)), describe(given)
        assert ids(result) == ids(sorted(result, key=key)), describe(given)
        outside = {k: v for k, v in scores_of(result).items() if k not in _PAIR_IDS}
        assert outside == {k: v for k, v in before.items() if k not in _PAIR_IDS}, (
            describe(given)
        )


@pytest.mark.parametrize(
    ("only", "or_later"),
    [(0.900, 0.896), (0.700, 0.699), (0.500, 0.492)],
)
def test_a_second_pass_nudges_a_pair_again_and_only_one_pass_is_ever_made(
    only: float, or_later: float
) -> None:
    """Pinned, not fixed: the tie-breaker is not idempotent. When the
    preferred side starts below its peer, the 0.01 swing leaves the pair
    inside the window, so a second pass nudges it again. match() applies it
    exactly once, so nothing observable depends on this; the nudge stays as it
    is on purpose (roadmap item 8)."""
    once = apply_version_suffix_tiebreaker(
        fresh(pair_sorted(only, or_later)), HEADER_OR_LATER, is_pure=False
    )
    twice = apply_version_suffix_tiebreaker(fresh(once), HEADER_OR_LATER, is_pure=False)
    assert scores_of(twice) != scores_of(once)
    assert ids(twice) == ids(once), "the order is settled by the first pass"


# -- Clause C: the phrase detector ----------------------------------------

# Phrases not already pinned by tests/test_match_ordering.py.
PHRASES: dict[str, bool] = {
    "Or Any Later Version": True,
    "OR NEWER": True,
    "or\tany\tlater\tversion": True,
    "or   any    later     version": True,
    "or any later\r\nversion": True,
    "// or any later\n// version": True,
    "# or any later\n# version": True,
    " * or any later\n * version": True,
    "; or any later\n; version": True,
    "-- or any later\n-- version": True,
    "any later version": True,
    "2 or later": True,
    "2 or newer": True,
    "no later version": False,
    "sooner or later on": False,
    "granted under the terms above": False,
}


@pytest.mark.parametrize("phrase", sorted(PHRASES))
def test_both_paths_read_each_phrase_the_specified_way(phrase: str) -> None:
    """The detector and the bare-ID path must agree, and must agree with
    the spec."""
    text = f"GPL-2.0 {phrase}"
    detected = has_or_later_language(text)
    resolved = disambiguate_deprecated_id(text)
    assert detected is PHRASES[phrase], "detector"
    assert detected is (resolved == OR_LATER), f"ID path resolved to {resolved!r}"


def test_the_id_text_itself_is_not_granting_language() -> None:
    assert OR_LATER_PHRASE.search(OR_LATER) is None


@pytest.mark.parametrize(
    "text",
    ["Python 3.10 or newer", "never any later version"],
)
def test_known_accepted_limits_of_the_phrase_regex(text: str) -> None:
    """Pinned, not a defect: a number-prefixed 'or newer' reads as a
    version grant, and negations other than 'not'/'no' are not guarded."""
    assert has_or_later_language(text) is True


# -- Clause D: no catastrophic backtracking -------------------------------


_PAYLOADS: dict[str, Callable[[], str]] = {
    "open-parens": lambda: "or (" * 10000,
    "or-run": lambda: "or " * 300000,
    "long-space": lambda: "or" + " " * 200000 + "x",
    "paren-tail": lambda: "or (" + "a" * 100000,
    "any-later-1mb": lambda: "any later " * 100000,
    "a-then-spaces": lambda: "or a" + " " * 40000,
    "any-then-newlines": lambda: "or any" + "\n" * 40000,
    "option-then-spaces": lambda: "or at your option" + " " * 40000 + "a" + " " * 40000,
    "number-then-spaces": lambda: "1" + " " * 200000 + "x",
    "numbers": lambda: "1 " * 200000,
}


@pytest.mark.parametrize("name", sorted(_PAYLOADS))
def test_the_phrase_regex_does_not_backtrack(name: str) -> None:
    payload = _PAYLOADS[name]()
    start = time.monotonic()
    OR_LATER_PHRASE.search(payload)
    elapsed = time.monotonic() - start
    assert elapsed < 1.0, f"{name} took {elapsed:.3f}s"


# -- Clause E: end to end through match() ---------------------------------

GPL_BODY = (
    "This program is free software; you can redistribute it and/or modify "
    "it under the terms of the GNU General Public License as published by "
    "the Free Software Foundation, version 2 of the License"
)
GPL_NAME = "GNU General Public License v2.0"


@pytest.fixture
def twin_gpl_db() -> Generator[str, None, None]:
    """-only and -or-later with the same name and the same indexed text, so
    nothing but the wording of the input can separate them."""
    yield from seeded_db(
        "test_ordering_adv_gpl",
        [
            Lic(lid, GPL_NAME, True, True, False, False, None, GPL_BODY)
            for lid in (ONLY, OR_LATER)
        ],
    )


def top_id(db_path: str, text: str, file_path: str | None = None) -> str:
    results = AggregatedLicenseMatcher(db_path).match(text=text, file_path=file_path)
    assert results, "no match at all"
    return results[0]["license_id"]


@pytest.mark.parametrize(
    "grant",
    [
        "either version 2 of the License, or (at your option) any later version",
        "either version 2 of the License, or any later version",
        "version 2 of the License, or any later version",
        "version 2 of the License or newer",
    ],
)
def test_a_source_header_with_granting_language_resolves_to_or_later(
    twin_gpl_db: str, grant: str
) -> None:
    header = (
        "This program is free software; you can redistribute it and/or "
        "modify it under the terms of the GNU General Public License as "
        f"published by the Free Software Foundation, {grant}."
    )
    assert top_id(twin_gpl_db, header) == OR_LATER


@pytest.mark.parametrize(
    ("text", "file_path"),
    [(f"{GPL_BODY}, version 2 only.", None), (f"{GPL_BODY}.", "LICENSE")],
    ids=["version-2-only", "pure-license-text"],
)
def test_text_without_a_grant_resolves_to_only(
    twin_gpl_db: str, text: str, file_path: str | None
) -> None:
    assert top_id(twin_gpl_db, text, file_path) == ONLY


def tier_text(padding: int) -> str:
    """The same header at two lengths: Tier 0 (short text) runs below 30
    normalised words, Tier 1 above it."""
    return (
        "Copyright 2026 Example. This program is free software you can "
        "redistribute it under the terms of the GNU General Public License "
        f"{' '.join(['published'] * padding)} version 2 or any later version"
    )


def test_the_same_header_resolves_the_same_way_either_side_of_tier_0(
    twin_gpl_db: str,
) -> None:
    """One header, two lengths: 29 normalised words takes the short-text
    path, 31 takes the full one. The granting language is identical."""
    short, long = tier_text(2), tier_text(4)
    assert len(normalize_text(short).split()) == 29
    assert len(normalize_text(long).split()) == 31
    assert top_id(twin_gpl_db, short) == top_id(twin_gpl_db, long) == OR_LATER
