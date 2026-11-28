# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``firsttext``: in a file of several licence texts, a text answer stands
only when its text is the first whole text found. The search is the
``found_rows`` fake here (its ``rows`` and ``first``); the real one runs in
``test_several_texts.py``."""
# pylint: disable=missing-function-docstring,redefined-outer-name,protected-access

from collections.abc import Generator
from typing import Any

import pytest
from conftest import FoundRows, GivenWarnings
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from long_text_db import long_text_detector
from several_texts import several_text
from test_wholetexts import FILLER, NOTICE, corpus_of, fake
from texts_db import A, texts_database

from licenseid import firsttext
from licenseid.detector import LicenseDetector
from licenseid.normalize import normalize_text
from licenseid.retrieval import text_candidates
from licenseid.textnames import named_texts
from licenseid.wholetexts import Found, found_rows, found_texts

GPL = ("GPL-3.0-only", "GPL-3.0-or-later")
GROUPS = {"GPL-3.0-only": GPL}
# Made-up texts (``test_wholetexts``), whose IDs sort unlike their places.
TA, TB, TC = fake(1), fake(2, 70), fake(3, 50)
CORPUS = corpus_of({"A": TA, "B": TB, "C": TC})


@pytest.mark.parametrize(
    ("found", "answer", "stands"),
    [
        (None, "A-1.0", True),  # nothing found: positive evidence only
        (Found(["A-1.0"], "A-1.0"), "B-1.0", True),  # one text: no file of several
        (Found(["A-1.0", "B-1.0"], "A-1.0"), "A-1.0", True),
        (Found(["A-1.0", "B-1.0"], "B-1.0"), "A-1.0", False),
        (Found(["A-1.0", "B-1.0"], "A-1.0"), "a-1.0", True),  # case folded
        (Found(["GPL-3.0-only", "MIT"], "GPL-3.0-only"), "GPL-3.0-or-later", True),
        (Found(["GPL-3.0-only", "MIT"], "GPL-3.0-only"), "GPL-3.0", True),
        (Found(["GPL-3.0-only", "MIT"], "GPL-3.0-only"), "GPL-3.0+", True),
        (
            Found(["GPL-3.0-only", "MIT"], "GPL-3.0-only"),
            "GPL-3.0-only WITH GCC-exception-3.1",
            True,
        ),
        (Found(["GPL-3.0-only", "MIT"], "MIT"), "GPL-3.0-or-later", False),
        (Found(["GPL-3.0-only", "MIT"], "MIT"), "GPL-3.0", False),
        (
            Found(["GPL-3.0-only", "MIT"], "MIT"),
            "GPL-3.0-only WITH GCC-exception-3.1",
            False,
        ),
    ],
    ids=[
        "none-found",
        "one-text",
        "first",
        "not-first",
        "case",
        "twin",
        "deprecated",
        "deprecated-plus",
        "exception",
        "twin-not-first",
        "deprecated-not-first",
        "exception-not-first",
    ],
)
def test_the_answer_stands_when_its_text_is_first(
    found: Found | None, answer: str, stands: bool
) -> None:
    assert firsttext.first_stands(found, answer, GROUPS) is stands


@pytest.fixture
def db_path() -> Generator[str, None, None]:
    yield from texts_database("test_firsttext")


def _result(license_id: str = "A-1.0", **changes: Any) -> Any:
    return {"license_id": license_id, "method": "text", "exact": False, **changes}


# A-1.0's text and more words (``texts_db``): the search reads the texts that
# share a gram with the input (``textcandidates``), so it shares some.
WORDS_40 = normalize_text(A) + " and more words"


def _settle(db_path: str, results: list[Any], norm_input: str = WORDS_40) -> Any:
    db = LicenseDetector(db_path).db
    with db.reading():
        texts = text_candidates(db, norm_input, norm_input)
        return firsttext.settle_texts(results, texts, db)


def test_a_refused_top_leaves_no_result_and_the_search(
    db_path: str, found_rows: FoundRows
) -> None:
    found_rows.rows, found_rows.first = ["A-1.0", "B-1.0"], "B-1.0"
    results = [_result(), _result("B-1.0")]
    assert _settle(db_path, results) == ([], Found(["A-1.0", "B-1.0"], "B-1.0"))
    found_rows.first = "A-1.0"
    settled, found = _settle(db_path, results)
    assert settled is results and found == Found(["A-1.0", "B-1.0"], "A-1.0")


@pytest.mark.parametrize(
    ("top", "norm_input"),
    [
        (_result(method="name"), WORDS_40),
        (_result(method="tag"), WORDS_40),
        (_result(exact=True), WORDS_40),
        (_result(), " ".join(WORDS_40.split()[:39])),
    ],
    ids=["name", "tag", "exact", "39-tokens"],
)
def test_only_an_inexact_text_top_of_40_tokens_is_searched(
    db_path: str, found_rows: FoundRows, top: Any, norm_input: str
) -> None:
    found_rows.rows, found_rows.first = ["A-1.0", "B-1.0"], "B-1.0"
    assert _settle(db_path, [top], norm_input) == ([top], None)
    assert not found_rows.calls


def test_no_result_is_not_searched(db_path: str, found_rows: FoundRows) -> None:
    assert _settle(db_path, []) == ([], None)
    assert not found_rows.calls


def test_nothing_found_keeps_the_results(db_path: str, found_rows: FoundRows) -> None:
    results = [_result()]
    assert _settle(db_path, results) == (results, None)
    assert found_rows.calls == [(WORDS_40, "A-1.0")]


@pytest.mark.parametrize(
    ("answer", "row"),
    [
        ("GPL-3.0", "GPL-3.0-only"),
        ("GPL-3.0+", "GPL-3.0-or-later"),
        ("GPL-3.0-only WITH GCC-exception-3.1", "GPL-3.0-only"),
        ("A-1.0", "A-1.0"),
    ],
)
def test_the_answers_row_wins_a_tie(
    db_path: str, found_rows: FoundRows, answer: str, row: str
) -> None:
    found_rows.rows = ["A-1.0"]
    _settle(db_path, [_result(answer)])
    assert found_rows.calls == [(WORDS_40, row)]


def test_a_short_text_before_a_long_one_is_refused(
    monkeypatch: pytest.MonkeyPatch, given: GivenWarnings
) -> None:
    """MIT, then the GPL-3.0: the top, GPL-3.0-only, covers about 1.03 of
    the input, under markerfloor's 1.05. A coverage gate would let it
    stand; the rule has none. The raw match has that value: the public one
    is capped at 1."""
    detector = long_text_detector()
    text = several_text("mit-then-gpl3")
    assert not detector.detect(text=text)
    assert not detector._match_raw(text=text)
    monkeypatch.setattr(firsttext, "first_stands", lambda *_: True)
    top = detector._match_raw(text=text)[0]
    assert top["license_id"] == "GPL-3.0-only"
    coverage = top["coverage"]
    assert coverage is not None and 1.0 < coverage <= 1.05
    assert top.get("texts") == ["MIT", "GPL-3.0-only"]
    assert detector.detect(text=text)[0]["coverage"] == 1.0
    assert given.conditions() <= {"variant not stated"}


@pytest.mark.parametrize(
    ("text", "rows"),
    [
        (f"{TB} {FILLER} {TA} {NOTICE} {TC}", ["B", "A", "C"]),
        (f"{TC} {TA}", ["C", "A"]),
        (f"{TA} {TB} {TA}", ["A", "B"]),  # a group at its first copy
        (f"{NOTICE} {TB} {TA} {TB}", ["B", "A"]),
    ],
    ids=["three", "two", "copies", "copies-later"],
)
def test_the_texts_are_in_file_order(text: str, rows: list[str]) -> None:
    """``Found.rows`` follows the input, not the IDs; ``first`` is its head
    (``found_rows`` stays sorted)."""
    found = found_texts(text, CORPUS, "A")
    assert found == Found(rows, rows[0])
    assert found_rows(text, CORPUS, "A") == sorted(rows)


def test_the_names_keep_the_file_order() -> None:
    """MIT, then the Apache-2.0: ``TEXTS`` is ``MIT Apache-2.0``, not by ID."""
    groups = {"GPL-3.0-only": GPL}
    assert named_texts(["MIT", "Apache-2.0"], "", "auto", groups) == [
        "MIT",
        "Apache-2.0",
    ]
    assert named_texts(["MIT", "GPL-3.0-only"], "GPL-3.0-or-later", "auto", groups) == [
        "MIT",
        "GPL-3.0-or-later",
    ]
