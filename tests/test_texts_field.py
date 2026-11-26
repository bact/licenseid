# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""``TEXTS`` (JSON ``texts``): the List texts an input holds whole, named once
each, sorted; the same on every result of a call; empty for an answer that is
not a text match and for an input under 40 tokens.

The search is ``wholetexts.found_rows``; here a fake gives its rows (the
``found_rows`` fixture), so these tests pin what the detector, the database
and the printing do with them. The texts are made up: 72 words of A-1.0, B-1.0
being A-1.0 with two words changed."""
# pylint: disable=missing-function-docstring,redefined-outer-name

import json
import sqlite3
from collections.abc import Generator
from typing import Any

import pytest
from click.testing import CliRunner
from conftest import NO_DETECTION, FoundRows
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from texts_db import GPL, A, texts_database

from licenseid import firsttext, textnames
from licenseid.cli import cli
from licenseid.database import text_corpus
from licenseid.detector import LicenseDetector
from licenseid.normalize import normalize_text
from licenseid.result import json_line, no_detection_line, text_line
from licenseid.types import Variant

MORE = A + " extra words here"  # A-1.0 by text, not exactly


@pytest.fixture
def db_path() -> Generator[str, None, None]:
    yield from texts_database("test_texts_field")


def test_every_result_has_the_texts_and_a_list_of_its_own(
    db_path: str, found_rows: FoundRows
) -> None:
    found_rows.rows = ["A-1.0", "B-1.0"]
    results = LicenseDetector(db_path).detect(text=MORE)
    assert [r["expression"] for r in results] == ["A-1.0", "B-1.0"]
    assert [r["texts"] for r in results] == [["A-1.0", "B-1.0"]] * 2
    results[0]["texts"].append("changed")  # type: ignore[union-attr]
    assert results[1]["texts"] == ["A-1.0", "B-1.0"]
    assert len(found_rows.calls) == 1  # one search for the call, not per result


def test_the_search_gets_the_normalised_input_and_the_answers_row(
    db_path: str, found_rows: FoundRows
) -> None:
    found_rows.rows = ["A-1.0"]
    LicenseDetector(db_path).detect(text=MORE)
    assert found_rows.calls == [(normalize_text(MORE), "A-1.0")]


def test_nothing_found_is_none_on_every_result(
    db_path: str, found_rows: FoundRows
) -> None:
    results = LicenseDetector(db_path).detect(text=MORE)
    assert len(found_rows.calls) == 1
    assert [r["texts"] for r in results] == [None, None]


def test_an_exact_answer_holds_its_own_text_and_is_not_searched(
    db_path: str, found_rows: FoundRows
) -> None:
    found_rows.rows = ["B-1.0"]
    results = LicenseDetector(db_path).detect(text=A)
    assert (results[0]["expression"], results[0]["exact"]) == ("A-1.0", True)
    assert [r["texts"] for r in results] == [["A-1.0"]] * len(results)
    assert not found_rows.calls


@pytest.mark.parametrize(
    "value",
    ["SPDX-License-Identifier: A-1.0", "A-1.0", "A licence", "A-1.0 OR B-1.0"],
    ids=["tag", "id", "name", "expression"],
)
def test_a_declared_value_or_a_name_has_none(
    db_path: str, found_rows: FoundRows, value: str
) -> None:
    found_rows.rows = ["A-1.0"]
    results = LicenseDetector(db_path).detect(text=value)
    assert results
    assert results[0]["method"] != "text"
    assert [r["texts"] for r in results] == [None] * len(results)
    assert not found_rows.calls and not found_rows.built


def test_a_declared_license_id_has_none(db_path: str, found_rows: FoundRows) -> None:
    results = LicenseDetector(db_path).detect(license_id="A-1.0")
    assert results[0]["texts"] is None
    assert not found_rows.calls


def test_a_text_that_declares_its_licence_in_a_tag_has_none(
    db_path: str, found_rows: FoundRows
) -> None:
    text = f"SPDX-License-Identifier: B-1.0\n{A}"
    results = LicenseDetector(db_path).detect(text=text)
    assert (results[0]["expression"], results[0]["method"]) == ("B-1.0", "tag")
    assert results[0]["texts"] is None
    assert not found_rows.calls


def test_forty_tokens_are_searched_and_thirty_nine_are_not(
    db_path: str, found_rows: FoundRows
) -> None:
    found_rows.rows = ["A-1.0"]
    words = normalize_text(A).split()
    detector = LicenseDetector(db_path)
    short = detector.detect(text=" ".join(words[:39]))
    assert not found_rows.calls
    assert short[0]["method"] == "text" and short[0]["texts"] is None
    longer = detector.detect(text=" ".join(words[:40]))
    assert longer[0]["method"] == "text" and len(found_rows.calls) == 1
    assert longer[0]["texts"] == ["A-1.0"]


@pytest.mark.parametrize(
    ("text", "tokens"),
    [
        ("a " * 39, False),
        ("a " * 40, True),
        ("  a\t" * 40, True),
        ("字" * 39, False),
        ("字" * 40, True),
        ("かな " * 20, True),  # a character each, as the corpus reads them
        ("字 a " * 19, False),
        ("字 a " * 20, True),
        ("", False),
    ],
    ids=[
        "ascii39",
        "ascii40",
        "ascii-white-space",
        "han39",
        "han40",
        "kana-words",
        "mixed38",
        "mixed40",
        "empty",
    ],
)
def test_the_gate_counts_a_han_or_kana_character_as_a_token(
    text: str, tokens: bool
) -> None:
    assert textnames.has_tokens(text) is tokens


def test_an_option_that_filters_candidates_does_not_touch_the_search(
    db_path: str, found_rows: FoundRows
) -> None:
    found_rows.rows = ["A-1.0", "B-1.0"]
    detector = LicenseDetector(db_path)
    plain = detector.detect(text=MORE)[0]["texts"]
    for options in (
        {"exclude": ["B-1.0"]},
        {"exclude": ["B-1.0", "A-1.0"]},
        {"hint": ["GPL-3.0-only"]},
        {"only_spdx": False},
        {"only_common": True},
    ):
        results = detector.detect(text=MORE, **options)
        assert [r["texts"] for r in results] == [plain] * len(results), options
    assert len(found_rows.built) == 1  # every row, once, whatever the option
    assert {row.license_id for row in found_rows.built[0]} == {
        "A-1.0",
        "B-1.0",
        "GPL-3.0-only",
        "GPL-3.0-or-later",
    }


def test_the_corpus_holds_each_text_with_its_core_and_its_group(
    db_path: str, found_rows: FoundRows
) -> None:
    found_rows.rows = ["A-1.0"]
    LicenseDetector(db_path).detect(text=MORE)
    (rows,) = found_rows.built
    by_id = {r.license_id: r for r in rows}
    assert by_id["A-1.0"].text == normalize_text(A)
    assert (by_id["A-1.0"].core, by_id["A-1.0"].group) == (None, ("A-1.0",))
    assert by_id["GPL-3.0-or-later"].group == ("GPL-3.0-only", "GPL-3.0-or-later")
    assert "GPL-3.0" not in by_id  # no text: no row


def test_a_call_makes_one_connection_with_the_corpus_built(
    db_path: str, found_rows: FoundRows, opened: list[sqlite3.Connection]
) -> None:
    found_rows.rows = ["A-1.0"]
    detector = LicenseDetector(db_path)
    opened.clear()
    assert detector.detect(text=MORE)[0]["texts"] == ["A-1.0"]
    assert len(opened) == 1 and len(found_rows.built) == 1
    opened.clear()
    detector.detect(text=MORE)
    assert len(opened) == 1 and len(found_rows.built) == 1


def test_the_corpus_is_built_again_after_the_tables_are_rewritten(
    db_path: str, found_rows: FoundRows
) -> None:
    found_rows.rows = ["A-1.0"]
    detector = LicenseDetector(db_path)
    detector.detect(text=MORE)
    detector.detect(text=MORE)
    assert len(found_rows.built) == 1
    with sqlite3.connect(db_path, uri=True) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO db_metadata VALUES ('last_update_datetime', 'x')"
        )
        conn.execute("DELETE FROM license_index WHERE license_id = 'B-1.0'")
    detector.detect(text=MORE)
    assert len(found_rows.built) == 2
    assert "B-1.0" not in {row.license_id for row in found_rows.built[1]}


def _invoke(db_path: str, *args: str) -> Any:
    return CliRunner().invoke(cli, ["--db", db_path, "detect", *args])


def test_the_text_line_ends_with_the_texts_after_the_reason(
    db_path: str, found_rows: FoundRows
) -> None:
    found_rows.rows, found_rows.first = ["B-1.0", "A-1.0"], "A-1.0"
    result = _invoke(db_path, "-v", "--top", "2", "--text", MORE)
    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert len(lines) == 2
    # In the order of the rows the search gives (the file's), not by ID.
    assert all(x.endswith("\tREASON=\tTEXTS=B-1.0 A-1.0") for x in lines)


def test_the_json_has_a_list_and_null_for_none(
    db_path: str, found_rows: FoundRows
) -> None:
    found_rows.rows = ["A-1.0", "B-1.0"]
    result = _invoke(db_path, "--json", "--text", MORE)
    assert json.loads(result.stdout.splitlines()[0])["texts"] == ["A-1.0", "B-1.0"]
    result = _invoke(db_path, "--json", "--id", "A-1.0")
    assert json.loads(result.stdout.splitlines()[0])["texts"] is None
    result = _invoke(db_path, "-v", "--id", "A-1.0")
    assert result.stdout.endswith("\tREASON=\tTEXTS=\n")


def test_a_record_of_no_answer_has_texts_only_when_found(db_path: str) -> None:
    assert no_detection_line("no match").endswith("\tREASON=no match\tTEXTS=")
    assert no_detection_line("several texts", ["A-1.0", "MIT"]).endswith(
        "\tREASON=several texts\tTEXTS=A-1.0 MIT"
    )
    assert NO_DETECTION.endswith("\tREASON=no match\tTEXTS=\n")
    result = _invoke(db_path, "--json", "--id", "No-Such-1.0")
    assert json.loads(result.stdout)["texts"] is None


def test_the_line_and_the_json_of_a_result_agree() -> None:
    from conftest import public_match

    result = public_match("A-1.0", method="text", texts=["A-1.0", "GPL-3.0-only"])
    assert text_line(result).endswith("\tREASON=\tTEXTS=A-1.0 GPL-3.0-only")
    assert json.loads(json_line(result))["texts"] == ["A-1.0", "GPL-3.0-only"]
    assert text_line(public_match()).endswith("\tREASON=\tTEXTS=")
    assert json.loads(json_line(public_match()))["texts"] is None
    assert text_line(public_match(texts=[])).endswith("\tTEXTS=")


@pytest.mark.parametrize(
    ("variant", "named"),
    [
        ("auto", "GPL-3.0-only"),
        ("only", "GPL-3.0-only"),
        ("or-later", "GPL-3.0-or-later"),
        ("as-written", "GPL-3.0-only"),
    ],
)
def test_the_real_search_finds_two_texts_in_one_input(
    db_path: str, variant: Variant, named: str
) -> None:
    """No fake: ``wholetexts`` on the made-up List, each text named as the
    variant names an unstated one (the answer's own is A-1.0)."""
    results = LicenseDetector(db_path).detect(
        text=f"{A} {GPL} and some words after them", variant=variant
    )
    assert results[0]["method"] == "text"
    assert results[0]["texts"] == sorted({results[0]["expression"], named})
    assert results[0]["texts"] == results[-1]["texts"]


def _text_result(license_id: str, *, exact: bool = False, method: str = "text") -> Any:
    return {
        "license_id": license_id,
        "method": method,
        "exact": exact,
        "score": 1.0,
        "similarity": 1.0,
        "coverage": 1.0,
    }


def _held(db_path: str, result: Any, variant: Variant = "auto") -> list[str] | None:
    """``TEXTS`` of *result* as ``detect()`` makes it: the search of
    ``firsttext``, then the names of ``textnames``."""
    db = LicenseDetector(db_path).db
    with db.reading():
        settled, found = firsttext.settle_texts([result], normalize_text(MORE), db)
        return textnames.held_texts(db, settled, variant, found)


def test_only_a_text_match_is_searched(db_path: str, found_rows: FoundRows) -> None:
    """The tiers that reach the search give text matches: the gate is for the
    ones that might not."""
    found_rows.rows = ["A-1.0"]
    assert _held(db_path, _text_result("A-1.0", method="name")) is None
    assert not found_rows.calls
    assert _held(db_path, _text_result("A-1.0")) == ["A-1.0"]


def test_no_result_is_no_texts(db_path: str, found_rows: FoundRows) -> None:
    db = LicenseDetector(db_path).db
    assert firsttext.settle_texts([], normalize_text(MORE), db) == ([], None)
    assert textnames.held_texts(db, [], "auto", None) is None
    assert not found_rows.calls


def test_nothing_found_is_none_whether_the_search_says_none_or_an_empty_list(
    db_path: str, found_rows: FoundRows
) -> None:
    nothing: list[list[str] | None] = [None, []]
    for rows in nothing:
        found_rows.rows = rows
        assert _held(db_path, _text_result("A-1.0")) is None
    assert len(found_rows.calls) == 2


@pytest.mark.parametrize(
    ("answer", "row"),
    [
        ("GPL-3.0", "GPL-3.0-only"),  # the bare ID is read from its row
        ("GPL-3.0+", "GPL-3.0-or-later"),
        ("GPL-3.0-or-later", "GPL-3.0-or-later"),
        ("A-1.0", "A-1.0"),
    ],
)
def test_the_search_gets_the_row_of_a_deprecated_answer(
    db_path: str, found_rows: FoundRows, answer: str, row: str
) -> None:
    found_rows.rows = ["A-1.0"]
    _held(db_path, _text_result(answer), "as-written")
    assert found_rows.calls[0][1] == row


def test_an_answer_with_an_exception_names_its_licence(
    db_path: str, found_rows: FoundRows
) -> None:
    found_rows.rows = ["GPL-3.0-only"]
    answer = "GPL-3.0-only WITH Classpath-exception-2.0"
    assert _held(db_path, _text_result(answer)) == ["GPL-3.0-only"]
    assert _held(db_path, _text_result(answer, exact=True)) == ["GPL-3.0-only"]
    assert found_rows.calls[0][1] == "GPL-3.0-only"


def test_the_corpus_is_kept_between_calls_outside_a_reading_block_and_rebuilt(
    db_path: str, found_rows: FoundRows
) -> None:
    """The stamp is read at each lookup outside a block, as for every read."""
    db = LicenseDetector(db_path).db
    first = text_corpus(db)
    assert text_corpus(db) is first and len(found_rows.built) == 1
    with sqlite3.connect(db_path, uri=True) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO db_metadata VALUES ('last_update_datetime', 'y')"
        )
    assert text_corpus(db) is not first and len(found_rows.built) == 2


def test_the_corpus_rows_carry_the_core_a_licence_keeps(
    db_path: str, found_rows: FoundRows
) -> None:
    core = " ".join(normalize_text(A).split()[:30])
    with sqlite3.connect(db_path, uri=True) as conn:
        conn.execute(
            "UPDATE licenses SET core_text = ?, core_word_count = 30"
            " WHERE license_id = 'A-1.0'",
            (core,),
        )
    text_corpus(LicenseDetector(db_path).db)
    by_id = {r.license_id: r for r in found_rows.built[0]}
    assert (by_id["A-1.0"].core, by_id["B-1.0"].core) == (core, None)
