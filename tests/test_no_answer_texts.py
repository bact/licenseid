# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""A record of no answer (``detect -v``, ``--json``) names the List texts the
input holds (``TEXTS``), a fact about the input, and ``REASON`` is
``several texts`` where there is no result and it holds texts of several
licences. The search is the ``found_rows`` fake; the texts are made up
(``texts_db``)."""
# pylint: disable=missing-function-docstring,redefined-outer-name

import json
from collections.abc import Generator
from typing import Any

import pytest
from click.testing import CliRunner
from conftest import FoundRows
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import
from texts_db import A, texts_database

from licenseid.cli import cli

pytestmark = pytest.mark.terse_cli

MORE = A + " extra words here"  # A-1.0 by text, not exactly
# Forty words no licence holds after one gram of A-1.0's (and B-1.0's): no
# candidate (a score of 1/42, under the none bar), but a text to search.
GIBBERISH = "permission is granted " + " ".join(f"zqx{n}vk" for n in range(40))


@pytest.fixture
def db_path() -> Generator[str, None, None]:
    yield from texts_database("test_no_answer_texts")


def _run(db_path: str, *args: str) -> Any:
    return CliRunner().invoke(cli, ["--db", db_path, "detect", *args])


def _fields(result: Any) -> dict[str, str]:
    """The fields of the first line."""
    line = result.stdout.splitlines()[0]
    return dict(field.split("=", 1) for field in line.split("\t"))


def test_below_threshold_names_the_top_candidates_texts(
    db_path: str, found_rows: FoundRows
) -> None:
    found_rows.rows = ["A-1.0"]
    answer = _fields(_run(db_path, "-v", "--text", MORE))
    assert float(answer["SCORE"]) < 1.0
    result = _run(db_path, "-v", "--threshold", "1", "--text", MORE)
    assert result.exit_code == 1
    fields = _fields(result)
    assert (fields["REASON"], fields["TEXTS"]) == ("below threshold", "A-1.0")
    assert len(found_rows.calls) == 2  # one search a call: none for the record


@pytest.mark.parametrize(
    ("rows", "reason", "texts"),
    [
        (["A-1.0"], "no match", "A-1.0"),
        (["A-1.0", "B-1.0"], "several texts", "A-1.0 B-1.0"),
        (["A-1.0", "GPL-3.0-only"], "several texts", "A-1.0 GPL-3.0-only"),
        (None, "no match", ""),
    ],
    ids=["one", "two", "group", "none"],
)
def test_no_candidate_names_what_the_input_holds(
    db_path: str, found_rows: FoundRows, rows: list[str] | None, reason: str, texts: str
) -> None:
    found_rows.rows = rows
    result = _run(db_path, "-v", "--text", GIBBERISH)
    assert result.exit_code == 1
    fields = _fields(result)
    assert (fields["EXPRESSION"], fields["REASON"], fields["TEXTS"]) == (
        "",
        reason,
        texts,
    )
    assert found_rows.calls == [(GIBBERISH, "")]  # no answer prefers no group


def test_the_or_later_variant_names_a_group_so(
    db_path: str, found_rows: FoundRows
) -> None:
    found_rows.rows = ["A-1.0", "GPL-3.0-only"]
    result = _run(db_path, "-v", "--variant", "or-later", "--text", GIBBERISH)
    assert _fields(result)["TEXTS"] == "A-1.0 GPL-3.0-or-later"


def test_a_refused_answer_is_several_texts(db_path: str, found_rows: FoundRows) -> None:
    found_rows.rows, found_rows.first = ["A-1.0", "B-1.0"], "B-1.0"
    result = _run(db_path, "-v", "--text", MORE)
    assert result.exit_code == 1
    fields = _fields(result)
    assert (fields["EXPRESSION"], fields["REASON"], fields["TEXTS"]) == (
        "",
        "several texts",
        "A-1.0 B-1.0",
    )
    record = json.loads(_run(db_path, "--json", "--text", MORE).stdout)
    assert (record["reason"], record["texts"]) == ("several texts", ["A-1.0", "B-1.0"])
    assert {k for k, v in record.items() if v is not None} == {"reason", "texts"}


def test_the_terse_output_makes_no_second_search(
    db_path: str, found_rows: FoundRows
) -> None:
    found_rows.rows, found_rows.first = ["A-1.0", "B-1.0"], "B-1.0"
    result = _run(db_path, "--text", MORE)
    assert (result.exit_code, result.stdout) == (1, "\n")
    # Tier 2's search, then the rule's (two texts found); nothing printed
    # needs more.
    assert [answer for _, answer in found_rows.calls] == ["", "A-1.0"]


def test_a_declared_id_of_no_answer_is_not_searched(
    db_path: str, found_rows: FoundRows
) -> None:
    found_rows.rows = ["A-1.0", "B-1.0"]
    fields = _fields(_run(db_path, "-v", "--id", "No-Such-1.0"))
    assert (fields["REASON"], fields["TEXTS"]) == ("no match", "")
    assert not found_rows.calls
