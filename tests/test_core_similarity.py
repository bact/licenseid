# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Tier 2 scores a long input against a licence's core as well as its whole
text, and keeps the higher similarity (``similarity.core_similarity``).

A copy of Apache-2.0 without its appendix scored 0.94 against Apache-2.0's
whole text and 0.99 against Pixar's (an Apache-2.0 with a clause of its own and
no appendix), so it was Pixar; the LGPL-3.0 alone (the List's text holds the
whole GPL-3.0 as an optional part) scored 0.3 and had no answer. The core is
the template without its optional parts (``licenseid.coretext``)."""
# pylint: disable=missing-function-docstring,redefined-outer-name

import json
import sqlite3
from collections.abc import Generator

import pytest
from conftest import GivenWarnings
from long_text_db import LONG_TEXTS, TEMPLATES, long_text_detector
from matcher_db import Lic, seeded_db
from rapidfuzz import fuzz

from licenseid import similarity
from licenseid.coretext import core_text
from licenseid.detector import LicenseDetector
from licenseid.normalize import normalize_text
from licenseid.records import core_of
from licenseid.types import CandidateMatch, TextParts


def _fixture_text(license_id: str) -> str:
    data = json.loads((LONG_TEXTS / f"{license_id}.json").read_text(encoding="utf-8"))
    return str(data["license_text"])


def _template(license_id: str) -> str:
    return (TEMPLATES / f"{license_id}.template.txt").read_text(encoding="utf-8")


APACHE_TEXT = _fixture_text("Apache-2.0")
# Apache-2.0 without its optional parts: the title and the appendix.
APACHE_CORE = core_text(_template("Apache-2.0")) or ""
# Made up, the shape of Pixar: the Apache-2.0 terms with a trademark clause
# of their own and no appendix.
# A var (the section number) stands apart: ``coretext`` puts a space beside it.
_TRADEMARKS = APACHE_CORE[
    APACHE_CORE.index("6.  Trademarks.") : APACHE_CORE.index("7.  Disclaimer")
]
MODIFIED_TEXT = APACHE_CORE.replace(
    _TRADEMARKS,
    "6. Trademarks. The names of the Licensor may be used in publicity only"
    " with its written permission.\n\n",
)


@pytest.fixture(scope="module")
def apache_family_db() -> Generator[str, None, None]:
    """Apache-2.0 with its core (as a build keeps it) beside the made-up
    Apache-Mod-1.0 and MIT."""
    apache = normalize_text(APACHE_TEXT)
    rows = [
        Lic("Apache-2.0", "Apache License 2.0", search_text=apache),
        Lic(
            "Apache-Mod-1.0",
            "Modified Apache",
            search_text=normalize_text(MODIFIED_TEXT),
        ),
        Lic("MIT", "MIT License", search_text=normalize_text(_fixture_text("MIT"))),
    ]
    for db_path in seeded_db("test_core_similarity", rows):
        core, words = core_of(_template("Apache-2.0"), len(apache.split()))
        with sqlite3.connect(db_path, uri=True) as conn:
            conn.execute(
                "UPDATE licenses SET core_text = ?, core_word_count = ?"
                " WHERE license_id = 'Apache-2.0'",
                (core, words),
            )
        yield db_path


def _top(db_path: str, text: str) -> tuple[str, bool]:
    result = LicenseDetector(db_path).detect(text=text)[0]
    return result["expression"], result["exact"]


def test_the_apache_terms_without_the_appendix_are_apache(
    apache_family_db: str,
) -> None:
    assert _top(apache_family_db, APACHE_CORE) == ("Apache-2.0", False)


def test_the_modified_apache_stays_itself(apache_family_db: str) -> None:
    assert _top(apache_family_db, MODIFIED_TEXT) == ("Apache-Mod-1.0", True)


def test_the_whole_apache_text_stays_exact(apache_family_db: str) -> None:
    assert _top(apache_family_db, APACHE_TEXT) == ("Apache-2.0", True)


def test_the_lgpl_3_alone_is_the_lgpl_3(given: GivenWarnings) -> None:
    """The LGPL-3.0 without the copy of the GPL-3.0 its List text holds,
    among every long-text fixture (GPL-3.0 and its other neighbours). The
    text states no variant (variants.settle_text chooses one)."""
    core = core_text(_template("LGPL-3.0-only")) or ""
    results = long_text_detector().detect(text=core)
    assert given.conditions() == {"variant not stated"}
    assert results[0]["expression"] in {"LGPL-3.0-only", "LGPL-3.0-or-later"}
    assert results[0]["exact"] is False
    assert results[0]["variant_stated"] is False
    assert results[0]["score"] >= 0.85


# Made up: the OFL-1.1 body without its title, after a copyright line that
# names a Reserved Font Name.
OFL_RFN_COPY = (
    "Copyright (c) 2010, Example Foundry (https://example.com), with Reserved"
    ' Font Name "Example Sans".\n\n'
    + _fixture_text("OFL-1.1")[_fixture_text("OFL-1.1").index("PREAMBLE") :]
)


def test_twins_of_one_text_are_scored_alike() -> None:
    """OFL-1.1, -RFN and -no-RFN have one text, but only the template of
    -no-RFN has a core shorter than it (the copyright line of the others
    names a Reserved Font Name): with its core alone, it took this copy.
    Each twin scores on the text they share (``records.uneven_cores``)."""
    results = long_text_detector().detect(text=OFL_RFN_COPY)[:3]
    assert [r["expression"] for r in results] == [
        "OFL-1.1",
        "OFL-1.1-RFN",
        "OFL-1.1-no-RFN",
    ]
    assert len({r["score"] for r in results}) == 1


# -- Unit rows: similarity.calculate_base_similarity ---------------------

CORE = "alpha beta gamma delta epsilon zeta eta theta iota kappa"  # 10 words
# The core's words, each followed by three optional ones: 40 words.
WHOLE = " ".join(
    f"{word} opt{i}a opt{i}b opt{i}c" for i, word in enumerate(CORE.split())
)


def _scored(norm_input: str, cand: CandidateMatch) -> tuple[float, float, str]:
    return similarity.calculate_base_similarity(similarity.query_of(norm_input), cand)


def _with_core(search_text: str = WHOLE, core: str = CORE) -> CandidateMatch:
    return similarity.with_core(
        CandidateMatch(license_id="X-1.0", search_text=search_text),
        TextParts(core, len(core.split()), ()),
    )


def test_the_core_wins_with_its_coverage_and_window() -> None:
    assert _scored(CORE, _with_core()) == (1.0, 1.0, CORE)


@pytest.mark.parametrize(
    ("words", "scored"),
    [(8, True), (7, False)],  # 0.8 of the core's 10 words
)
def test_an_input_needs_eight_tenths_of_the_core(words: int, scored: bool) -> None:
    norm_input = " ".join(CORE.split()[:words])
    sim, coverage, window = _scored(norm_input, _with_core())
    assert (window == CORE) is scored
    assert coverage == pytest.approx(words / 10 if scored else words / 40)
    if scored:
        assert sim == pytest.approx(fuzz.token_sort_ratio(norm_input, CORE) / 100.0)


@pytest.mark.parametrize(
    ("words", "scored"),
    [(12, True), (13, False)],  # the core's 10 words are 0.8 of 12.5
)
def test_the_core_needs_eight_tenths_of_the_input(words: int, scored: bool) -> None:
    """An input much longer than the core holds more than the core: it is
    not scored against it (nor pays for it)."""
    norm_input = " ".join([*CORE.split(), *(f"extra{i}" for i in range(words - 10))])
    sim, coverage, window = _scored(norm_input, _with_core())
    assert (window == CORE) is scored
    assert coverage == pytest.approx(words / 10 if scored else words / 40)
    if scored:
        assert sim == pytest.approx(fuzz.token_sort_ratio(norm_input, CORE) / 100.0)


def test_a_core_of_eight_tenths_of_the_input_is_scored() -> None:
    """The boundary itself: a core of 8 words for an input of 10."""
    core = " ".join(CORE.split()[:8])
    norm_input = f"{core} extra0 extra1"
    _, coverage, window = _scored(norm_input, _with_core(core=core))
    assert (window, coverage) == (core, 10 / 8)


def test_a_core_that_cannot_reach_the_whole_text_is_not_compared(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The length bound: twice the shorter length over the sum of both is the
    most token_sort_ratio can give, so no comparison is made below it."""
    calls: list[str] = []
    real = fuzz.token_sort_ratio

    def counted(s1: str, s2: str, *, score_cutoff: float) -> float:
        calls.append(s2)
        return real(s1, s2, score_cutoff=score_cutoff)

    monkeypatch.setattr(fuzz, "token_sort_ratio", counted)
    ten = " ".join(["a"] * 10)  # 19 characters
    # At most 2 * 9 / (19 + 9) = 0.64 against 9 characters.
    assert similarity.core_similarity(ten, 10, "b" * 9, 10, 0.65) == 0.0
    five = " ".join(["a"] * 5)  # 9 characters
    assert similarity.core_similarity(ten, 10, five, 10, 0.6) == pytest.approx(18 / 28)
    assert calls == [five]


def test_a_core_that_scores_lower_leaves_the_whole_text() -> None:
    norm_input = f"{WHOLE} extra"
    sim, coverage, window = _scored(norm_input, _with_core())
    assert window == WHOLE
    assert coverage == pytest.approx(41 / 40)
    assert sim == pytest.approx(fuzz.token_sort_ratio(norm_input, WHOLE) / 100.0)


def test_the_core_is_safeguarded_against_its_own_words() -> None:
    """A copy of the core with a "not" it lacks loses 5 %, even where the
    whole text has a "not" in an optional part: the words compared are the
    core's."""
    core = " ".join([*CORE.split(), *(f"term{i}" for i in range(30))])
    norm_input = f"{core} not"
    whole = " ".join(f"{word} opt{i}a opt{i}b" for i, word in enumerate(core.split()))
    whole = f"{whole} not"
    sim, _, window = _scored(norm_input, _with_core(whole, core))
    raw = fuzz.token_sort_ratio(norm_input, core) / 100.0
    assert window == core
    assert raw > 0.9
    assert sim == pytest.approx(raw * 0.95)


def test_the_diff_shows_the_core_it_was_compared_with(
    apache_family_db: str,
) -> None:
    """``--diff`` makes Tier 2's comparison again: against the core."""
    detector = LicenseDetector(apache_family_db)
    norm_input, window = detector._diff_pair(  # pylint: disable=protected-access
        APACHE_CORE, "Apache-2.0"
    )
    assert norm_input == normalize_text(APACHE_CORE)
    assert (
        window
        == core_of(_template("Apache-2.0"), len(normalize_text(APACHE_TEXT).split()))[0]
    )


def test_matching_the_core_is_not_exact() -> None:
    query = similarity.query_of(CORE)
    ranked = similarity.score_candidates([_with_core()], query, {}, True, False)
    assert (ranked[0]["similarity"], ranked[0]["exact"]) == (1.0, False)


@pytest.mark.parametrize(
    "parts",
    [None, TextParts(None, None, ("X-1.0", "Y-1.0"))],
    ids=["no-parts", "twins-only"],
)
def test_a_licence_without_a_core_is_left_alone(parts: TextParts | None) -> None:
    cand = CandidateMatch(license_id="X-1.0", search_text=WHOLE)
    assert similarity.with_core(cand, parts) is cand


def test_a_candidate_without_its_text_gets_no_core() -> None:
    """A hinted candidate past the first 50 has no text: it is scored against
    nothing, not against its core."""
    cand = CandidateMatch(license_id="X-1.0", search_text="")
    assert similarity.with_core(cand, TextParts(CORE, 10, ())) is cand
