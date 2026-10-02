# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Direct tests of licenseid.shorttext.match_short_text (Tier 0).

Written from a mutation audit of the matcher.py split: coverage was 100%,
but the thresholds, the definitive-hit triple and the one-word partial
match could be changed without a test noticing.
"""
# pylint: disable=redefined-outer-name,missing-function-docstring

from collections.abc import Callable, Generator
from typing import Any
from unittest import mock

import pytest
from matcher_db import Lic, seeded_db
from rapidfuzz import fuzz

from licenseid import shorttext
from licenseid.database import LicenseDatabase
from licenseid.shorttext import match_short_text


@pytest.fixture
def db() -> Generator[LicenseDatabase, None, None]:
    rows = [
        Lic("Acme-1.0", "Acme Public License"),
        Lic("Gpl-Like-3.0-only", "Copyleft Thing"),
        Lic("Zebra-1.0", "Zebra Quokka"),
        Lic("Ferret-1.0", "Ferret Lynx Ocelot"),
        Lic("Two-1.0", "sreltpus ctapirhgwp"),
        Lic("Three-1.0", "qmx a vycfysb"),
    ]
    for path in seeded_db("test_shorttext", rows):
        yield LicenseDatabase(path)


def summary(db: LicenseDatabase, text: str) -> list[tuple[str, float, float | None]]:
    return [
        (
            m["license_id"],
            round(m["score"], 6),
            None if m["similarity"] is None else round(m["similarity"], 6),
        )
        for m in match_short_text(db, text)
    ]


def test_an_id_ignoring_case_is_a_definitive_hit(db: LicenseDatabase) -> None:
    """The caller treats a score above 1.0 as final. An ID is not compared,
    so nothing is measured."""
    results = match_short_text(db, "acme 1 0")

    assert len(results) == 1
    assert results[0]["license_id"] == "Acme-1.0"
    assert (results[0]["method"], results[0]["score"]) == ("id", 1.02)
    assert (results[0]["similarity"], results[0]["coverage"]) == (None, None)


def test_an_exact_name_scores_1_02_without_an_id_match(db: LicenseDatabase) -> None:
    assert summary(db, "acme public license") == [("Acme-1.0", 1.02, 1.0)]


def test_a_name_subset_gets_the_smaller_flex_bonus(db: LicenseDatabase) -> None:
    """Token-set ratio 100 without an exact name: +0.01, not +0.02."""
    assert summary(db, "acme license") == [("Acme-1.0", 1.01, 1.0)]


def test_a_one_word_input_matches_inside_an_id(db: LicenseDatabase) -> None:
    """Only a single word gets the partial ID ratio: `gpl` sits inside
    `gpl like 3 0 only`."""
    assert summary(db, "gpl") == [("Gpl-Like-3.0-only", 1.0, 1.0)]


def test_a_two_word_input_gets_no_partial_id_ratio(db: LicenseDatabase) -> None:
    assert not match_short_text(db, "gpl like")


def test_two_words_need_90_and_three_words_need_85(db: LicenseDatabase) -> None:
    """`zebra kokka` scores 86.96 against `zebra quokka`; `ferret lynx
    ocelxx` scores 88.89 against `ferret lynx ocelot`."""
    assert not match_short_text(db, "zebra kokka")
    assert summary(db, "ferret lynx ocelxx") == [("Ferret-1.0", 0.888889, 0.888889)]


def test_equal_scores_sort_by_license_id() -> None:
    rows = [Lic("B-1.0", "Twin Name"), Lic("A-1.0", "Twin Name")]
    for path in seeded_db("test_shorttext_twins", rows):
        twin_db = LicenseDatabase(path)
        assert [m["license_id"] for m in match_short_text(twin_db, "twin name")] == [
            "A-1.0",
            "B-1.0",
        ]


def test_the_thresholds_are_exactly_90_and_85(db: LicenseDatabase) -> None:
    """Two words score 89.47 against `sreltpus ctapirhgwp` (no match: needs
    90); three score 84.62 against `qmx a vycfysb` (no match: needs 85)."""
    assert not match_short_text(db, "sreltpus ctaperhvwp")
    assert not match_short_text(db, "pmx a tycfysb")


# The cutoff stops RapidFuzz early (roadmap item 27) and changes no result.
CUTOFF_INPUTS = [
    "acme-1.0",
    "acme public license",
    "acme public licence",
    "acme",
    "copyleft thing",
    "copyleft thing for everyone who wants it",
    "zebra quokka",
    "quokka",
    "ferret lynx",
    "ferret lynx ocelot and more words",
    "gpl like 3",
    "the",
    "本ライセンスは",
    "a" * 2_000,
]


def _no_cutoff(scorer: Callable[..., float]) -> Callable[..., float]:
    def score(a: str, b: str, **_: Any) -> float:
        return scorer(a, b)

    return score


def test_the_cutoff_changes_no_result(db: LicenseDatabase) -> None:
    reference = mock.Mock(
        spec=fuzz,
        ratio=_no_cutoff(fuzz.ratio),
        partial_ratio=_no_cutoff(fuzz.partial_ratio),
        token_set_ratio=_no_cutoff(fuzz.token_set_ratio),
    )
    with mock.patch.object(shorttext, "fuzz", reference):
        expected = [match_short_text(db, t) for t in CUTOFF_INPUTS]
    assert [match_short_text(db, t) for t in CUTOFF_INPUTS] == expected
    # Most inputs reach a fuzzy match, or the comparison proves little.
    assert sum(map(bool, expected)) >= 6


@pytest.mark.parametrize(("text", "threshold"), [("acme", 90.0), ("a b c", 85.0)])
def test_every_scorer_stops_at_the_threshold(
    db: LicenseDatabase, text: str, threshold: float
) -> None:
    """A long word against every row took seconds without the cutoff."""
    spy = mock.Mock(spec=fuzz, wraps=fuzz)
    with mock.patch.object(shorttext, "fuzz", spy):
        match_short_text(db, text)
    calls = [
        *spy.ratio.call_args_list,
        *spy.partial_ratio.call_args_list,
        *spy.token_set_ratio.call_args_list,
    ]
    assert calls
    assert {c.kwargs.get("score_cutoff") for c in calls} == {threshold}
