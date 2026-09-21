# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""How candidates are ordered: the ranking key, the -only / -or-later
tie-breaker (its window, its nudge, its phrase detector) and the short-text
sort. Roadmap item 8."""
# pylint: disable=redefined-outer-name,missing-function-docstring
# pylint: disable=protected-access,too-many-arguments,too-many-positional-arguments

from collections.abc import Generator
from pathlib import Path

import pytest
from conftest import MIT_SEARCH_TEXT
from matcher_db import Lic, seeded_db
from ordering_helpers import HEADER_OR_LATER, ids, im

from licenseid import matcher as matcher_module
from licenseid.classify import has_or_later_language
from licenseid.identifiers import disambiguate_deprecated_id
from licenseid.matcher import AggregatedLicenseMatcher
from licenseid.ranking import DEP_PENALTY, apply_version_suffix_tiebreaker
from licenseid.types import CandidateMatch, InternalMatch, MatchRequest


def rank(
    ordering_matcher: AggregatedLicenseMatcher,
    monkeypatch: pytest.MonkeyPatch,
    scores: dict[str, float],
    *,
    deprecated: frozenset[str] = frozenset(),
    pop: dict[str, int] | None = None,
    enable_popularity: bool | None = None,
) -> list[InternalMatch]:
    """Run _rank_candidates with each candidate's final score fixed, so that
    only the ordering rule is under test."""
    pops = pop or {}
    monkeypatch.setattr(
        matcher_module,
        "calculate_base_similarity",
        lambda *_args: (0.0, 0.0, ""),
    )
    monkeypatch.setattr(
        matcher_module,
        "calculate_final_score",
        lambda match, *_args: scores[match["license_id"]],
    )
    monkeypatch.setattr(ordering_matcher.db, "find_fingerprint_hits", lambda _text: {})
    candidates = [
        CandidateMatch(
            license_id=lid,
            search_text="",
            is_deprecated=lid in deprecated,
            pop_score=pops.get(lid, 0),
        )
        for lid in scores
    ]
    request = MatchRequest()
    if enable_popularity is not None:
        request["enable_popularity"] = enable_popularity
    return ordering_matcher._rank_candidates(candidates, "x", request)


# -- The ranking key (_rank_candidates) -----------------------------------


@pytest.mark.parametrize(
    ("dep_score", "expected"),
    [
        (0.90, ["Canon-1.0", "Old-1.0"]),
        (0.91, ["Canon-1.0", "Old-1.0"]),
        (0.92, ["Canon-1.0", "Old-1.0"]),
        (0.94, ["Old-1.0", "Canon-1.0"]),
    ],
)
def test_a_deprecated_id_loses_the_penalty_in_the_ranking(
    ordering_matcher: AggregatedLicenseMatcher,
    monkeypatch: pytest.MonkeyPatch,
    dep_score: float,
    expected: list[str],
) -> None:
    ranked = rank(
        ordering_matcher,
        monkeypatch,
        {"Canon-1.0": 0.90, "Old-1.0": dep_score},
        deprecated=frozenset({"Old-1.0"}),
    )
    assert ids(ranked) == expected
    assert ranked[-1]["score"] in (0.90, dep_score), "the stored score is untouched"


def test_ties_are_broken_by_deprecation_then_popularity_then_id(
    ordering_matcher: AggregatedLicenseMatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    scores = {"B-1.0": 0.8, "A-1.0": 0.8, "C-1.0": 0.8}
    off = rank(ordering_matcher, monkeypatch, scores, pop={"B-1.0": 9, "C-1.0": 1})
    assert ids(off) == ["A-1.0", "B-1.0", "C-1.0"], "popularity is off: id order"
    on = rank(
        ordering_matcher,
        monkeypatch,
        scores,
        pop={"B-1.0": 9, "C-1.0": 1},
        enable_popularity=True,
    )
    assert ids(on) == ["B-1.0", "C-1.0", "A-1.0"], "popularity is on: higher first"


def test_popularity_is_off_unless_the_matcher_or_the_request_turns_it_on(
    ordering_matcher: AggregatedLicenseMatcher, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A request that says nothing uses the matcher's own setting (off by
    default); a request that says something overrides it."""
    scores = {"A-1.0": 0.8, "B-1.0": 0.8}
    pop = {"B-1.0": 9}

    def order(request_flag: bool | None = None) -> list[str]:
        return ids(
            rank(
                ordering_matcher,
                monkeypatch,
                scores,
                pop=pop,
                enable_popularity=request_flag,
            )
        )

    assert order() == ["A-1.0", "B-1.0"], "off by default"
    ordering_matcher.enable_popularity = True
    assert order() == ["B-1.0", "A-1.0"], "the matcher's setting applies"
    assert order(False) == ["A-1.0", "B-1.0"], "the request overrides it"


def test_match_hands_the_tiebreaker_the_text_and_the_popularity_setting(
    ordering_matcher: AggregatedLicenseMatcher,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """match() passes the tie-breaker the raw text, whether it is pure
    license text (a LICENSE file name says so), and the popularity flag with
    the same precedence as the ranking (request over matcher over off)."""
    calls: list[tuple[str, bool, bool]] = []

    def spy(
        ranked: list[InternalMatch], raw_text: str, is_pure: bool, enable_pop: bool
    ) -> list[InternalMatch]:
        calls.append((raw_text, is_pure, enable_pop))
        return ranked

    monkeypatch.setattr(matcher_module, "apply_version_suffix_tiebreaker", spy)
    text = (MIT_SEARCH_TEXT + " " + MIT_SEARCH_TEXT).upper()  # not already normal

    ordering_matcher.match(text=text)
    ordering_matcher.enable_popularity = True
    ordering_matcher.match(text=text)
    ordering_matcher.match(text=text, enable_popularity=False)
    license_file = tmp_path / "LICENSE"
    license_file.write_text(text, encoding="utf-8")
    ordering_matcher.match(file_path=str(license_file), enable_popularity=False)

    assert calls == [
        (text, False, False),
        (text, False, True),
        (text, False, False),
        (text, True, False),
    ]


# -- The tie-breaker: order (roadmap item 8) ------------------------------


def only_and_or_later(only: float, or_later: float) -> list[InternalMatch]:
    return [im("GPL-2.0-only", only), im("GPL-2.0-or-later", or_later)]


def test_the_tiebreaker_re_sort_does_not_promote_a_deprecated_id() -> None:
    """Old-1.0 ranks below Canon-1.0 (0.91 - 0.03 < 0.90). A tied
    -only/-or-later pair makes the tie-breaker re-sort the whole list, and
    that re-sort must apply the same penalty."""
    ranked = [
        im("Canon-1.0", 0.90),
        im("Old-1.0", 0.91, deprecated=True),
        *only_and_or_later(0.50, 0.50),
    ]
    result = apply_version_suffix_tiebreaker(ranked, HEADER_OR_LATER, is_pure=False)
    assert ids(result)[:2] == ["Canon-1.0", "Old-1.0"]


def test_the_popularity_flag_reaches_the_tiebreaker_re_sort() -> None:
    """Equal scores are ordered by popularity only when it is enabled; the
    re-sort the tie-breaker makes must follow the same flag."""

    def ranked() -> list[InternalMatch]:
        return [
            im("A-1.0", 0.80, pop=1),
            im("B-1.0", 0.80, pop=9),
            *only_and_or_later(0.50, 0.50),
        ]

    off = apply_version_suffix_tiebreaker(ranked(), HEADER_OR_LATER, is_pure=False)
    on = apply_version_suffix_tiebreaker(
        ranked(), HEADER_OR_LATER, is_pure=False, enable_pop=True
    )
    assert ids(off)[:2] == ["A-1.0", "B-1.0"]
    assert ids(on)[:2] == ["B-1.0", "A-1.0"]


# -- The tie-breaker: nudge (pinned on purpose) ---------------------------


def test_the_nudge_is_half_the_window_each_way() -> None:
    """The result stays sorted by score, so the granting language decides by
    moving the two scores 0.005 apart. It changes the reported scores."""
    signal = apply_version_suffix_tiebreaker(
        only_and_or_later(0.90, 0.90), HEADER_OR_LATER, is_pure=False
    )
    assert ids(signal) == ["GPL-2.0-or-later", "GPL-2.0-only"]
    assert [r["score"] for r in signal] == pytest.approx([0.905, 0.895])
    default = apply_version_suffix_tiebreaker(
        only_and_or_later(0.90, 0.90), "no grant here", is_pure=False
    )
    assert ids(default) == ["GPL-2.0-only", "GPL-2.0-or-later"]
    assert [r["score"] for r in default] == pytest.approx([0.905, 0.895])


def test_the_nudge_can_pass_an_unrelated_license_within_the_window() -> None:
    """Accepted: keeping the list sorted by score means a pair member can
    move past a third license scoring within 0.005 of it."""
    ranked = [im("Other-1.0", 0.903), *only_and_or_later(0.90, 0.90)]
    result = apply_version_suffix_tiebreaker(ranked, HEADER_OR_LATER, is_pure=False)
    assert ids(result) == ["GPL-2.0-or-later", "Other-1.0", "GPL-2.0-only"]
    assert result[1]["score"] == 0.903, "a license outside the pair keeps its score"


# -- The tie-breaker: window ----------------------------------------------


def adjusted(only: float, or_later: float) -> bool:
    ranked = only_and_or_later(only, or_later)
    result = apply_version_suffix_tiebreaker(ranked, HEADER_OR_LATER, is_pure=False)
    return any(r["score"] != s for r, s in zip(result, (only, or_later)))


@pytest.mark.parametrize("gap", [0.0, 0.004, 0.009])
def test_a_gap_under_the_window_is_a_tie(gap: float) -> None:
    assert adjusted(0.90 + gap, 0.90)


@pytest.mark.parametrize("gap", [0.011, 0.02, 0.2])
def test_a_gap_over_the_window_is_not_a_tie(gap: float) -> None:
    assert not adjusted(0.90 + gap, 0.90)


def test_a_gap_of_exactly_the_window_is_not_a_tie_at_any_score() -> None:
    """0.91 - 0.90 and 0.35 - 0.34 are both 0.01, but not the same float."""
    lows = [round(0.30 + step * 0.01, 2) for step in range(76)]
    ties = [low for low in lows if adjusted(round(low + 0.01, 3), low)]
    assert not ties, f"a gap of 0.01 was a tie at {ties}"


def test_applying_the_tiebreaker_twice_changes_nothing_more() -> None:
    once = apply_version_suffix_tiebreaker(
        only_and_or_later(0.90, 0.90), HEADER_OR_LATER, is_pure=False
    )
    snapshot = [(r["license_id"], r["score"]) for r in once]
    twice = apply_version_suffix_tiebreaker(once, HEADER_OR_LATER, is_pure=False)
    assert [(r["license_id"], r["score"]) for r in twice] == snapshot


# -- The tie-breaker: the phrase detector ---------------------------------

# Each phrase: does the tie-breaker read it as "or later" (classify), and does
# the ID path (identifiers) resolve "GPL-2.0 <phrase>" to -or-later?
PHRASES: dict[str, tuple[bool, bool]] = {
    "or (at your option) any later version": (True, True),
    "or later": (True, True),
    "or any later version": (True, True),
    "or a later version": (True, True),
    "or newer": (True, True),
    "or, at your option, any later version": (True, True),
    "or\n * (at your option) any later version": (True, True),
    "or\n// (at your option)\n// any later version": (True, True),
    "or\n# any later version": (True, True),
    "or\n * a later version": (True, True),
    "(or later)": (True, True),
    "[or later]": (True, True),
    "+ or later": (True, True),
    "\n// or later": (True, True),
    "\n * or (at your option) any\n * later version": (True, True),
    "or,\n// a later version": (True, True),
    "or a laterally": (False, False),
    "not any later version": (False, False),
    "no any later version": (False, False),
    "not or a later version": (False, False),
    "not or newer": (False, False),
}


def tiebreaker_reads(phrase: str) -> bool:
    return has_or_later_language(f"GPL-2.0 {phrase}")


def id_path_reads(phrase: str) -> bool:
    return disambiguate_deprecated_id(f"GPL-2.0 {phrase}") == "GPL-2.0-or-later"


@pytest.mark.parametrize("phrase", sorted(PHRASES))
def test_the_tiebreaker_and_the_id_path_read_a_phrase_the_same_way(
    phrase: str,
) -> None:
    tiebreaker, id_path = PHRASES[phrase]
    assert tiebreaker_reads(phrase) == tiebreaker, "tie-breaker"
    assert id_path_reads(phrase) == id_path, "ID path"


@pytest.mark.parametrize(
    "text",
    ["sooner or later", "this or later chapters", "version or later", "or later"],
)
def test_a_bare_or_later_without_a_number_is_not_a_grant(text: str) -> None:
    """Only "N or later" is a grant; "or a later", "or any later" and "or
    newer" need no number."""
    assert not has_or_later_language(text)


def test_the_shorthand_is_read_by_the_tiebreaker_only() -> None:
    """GPLv2+ is a notice in source files; the ID path handles '+' itself."""
    assert tiebreaker_reads("GPLv2+")
    assert not id_path_reads("GPLv2+")


# -- The short-text sort ---------------------------------------------------


@pytest.fixture
def twin_names_db() -> Generator[str, None, None]:
    yield from seeded_db(
        "test_ordering_short",
        [Lic("B-1.0", "Twin Name License"), Lic("A-1.0", "Twin Name License")],
    )


def test_short_text_ties_are_broken_by_license_id(twin_names_db: str) -> None:
    results = AggregatedLicenseMatcher(twin_names_db).match("Twin Name License")
    assert [r["license_id"] for r in results] == ["A-1.0", "B-1.0"]
    assert results[0]["score"] == results[1]["score"]


def test_the_penalty_constant_is_what_the_tests_assume() -> None:
    assert DEP_PENALTY == 0.03
