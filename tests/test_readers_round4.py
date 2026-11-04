# SPDX-FileContributor: Arthit Suriyawongkul
# SPDX-FileCopyrightText: 2026-present Arthit Suriyawongkul
# SPDX-FileType: SOURCE
# SPDX-License-Identifier: Apache-2.0

"""Task ``readers``, fourth round: what round 3 refused that it must not,
on the whole 3.29.0 List (every ID a row, Intel, Nokia and Ruby too).

Each test was first a pin of what the branch did (``# BUG:``); it now holds
the new answer.
"""
# pylint: disable=missing-function-docstring

from pathlib import Path

import pytest
from click.testing import CliRunner
from db_asserts import safe_home  # noqa: F401  # pylint: disable=unused-import

from licenseid import LicenseDatabase
from licenseid.classify import grant_follows, grant_head
from licenseid.cli import cli
from licenseid.detector import LicenseDetector
from licenseid.looseid import (
    _lists_another,
    declared_grant_id_text,
    disambiguate_whole,
    read_inexactly,
)
from licenseid.types import CandidateMatch, Detection

Answer = tuple[str, bool] | None


def _top(found: list[Detection]) -> Answer:
    return (found[0]["expression"], found[0]["exact"]) if found else None


def _text(corpus_db: LicenseDatabase, value: str) -> Answer:
    return _top(LicenseDetector(corpus_db.location).detect(text=value))


def _file(corpus_db: LicenseDatabase, tmp_path: Path, content: str) -> Answer:
    path = tmp_path / "notice.c"
    path.write_text(content, "utf-8")
    return _top(LicenseDetector(corpus_db.location).detect(file_path=str(path)))


# --- 1: a word that is also an ID, in prose beside a granted ID ----------------

PROSE = {
    # Round 3 gave none: Intel, Nokia, fair, doc, Ruby and curl are IDs of
    # the List, and each was read as a second licence. In prose they are
    # words; only a listed one counts (looseid._lists_another).
    "Copyright Intel Corp. GPL-2.0 or later": ("GPL-2.0-or-later", True),
    "(c) Nokia 2009, LGPL-2.1 or any later version": ("LGPL-2.1-or-later", True),
    "Distributed under GPL-3.0 or later; fair use applies": (
        "GPL-3.0-or-later",
        True,
    ),
    "GPL-2.0 only, see the doc folder": ("GPL-2.0-only", True),
    "GPL-2.0 or later, the same as Ruby": ("GPL-2.0-or-later", True),
    "LGPL-2.1 or later (see LICENSE). Uses curl.": ("LGPL-2.1-or-later", True),
}


@pytest.mark.parametrize("value", sorted(PROSE))
def test_an_id_word_in_prose(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str
) -> None:
    answer = PROSE[value]
    assert (_text(corpus_db, value), _file(corpus_db, tmp_path, value)) == (
        answer,
        answer,
    )


def test_an_id_word_in_a_header(corpus_db: LicenseDatabase, tmp_path: Path) -> None:
    header = "// Copyright 2015 Intel Corporation\n// Licensed under GPL-2.0 or later\n"
    assert _file(corpus_db, tmp_path, header) == ("GPL-2.0-or-later", True)


@pytest.mark.parametrize(
    "value",
    ["Copyright Intel Corp. GPL-2.0 or later", "GPL-2.0 or later, the same as Ruby"],
)
def test_an_id_word_in_prose_is_spdx(corpus_db: LicenseDatabase, value: str) -> None:
    result = CliRunner().invoke(
        cli, ["--db", corpus_db.location, "is-spdx", "--text", value]
    )
    assert (result.exit_code, result.stderr) == (0, "")


# A licence listed beside the granted one is still refused, as resolve() does:
# no exact answer (one with "and" goes on to the text tiers, not exact).
LISTED = [
    "GPL-3.0, LGPL-2.1 or later",
    "LGPL-2.1 or later, GPL-3.0",
    "MIT, GPL-2.0 or later",
    "GPL-2.0 or later; docs under the GFDL-1.3",
    "GPL-2.0 / LGPL-2.1 or later",
    "ISC and GPL-2.0 or later",
]


@pytest.mark.parametrize("value", LISTED)
def test_a_listed_licence_beside_a_grant(
    corpus_db: LicenseDatabase, tmp_path: Path, value: str
) -> None:
    for answer in (_text(corpus_db, value), _file(corpus_db, tmp_path, value)):
        assert answer is None or not answer[1]  # never the granted one, exact


# --- 2: a grant wrapped onto a comment line -------------------------------------

WRAPPED = [
    # Round 3 gave none: the "*", "#" or "//" of the next line was judged a
    # mark the grant crossed. After a line break only the comment prefix
    # stands there (classify._kept).
    "/*\n * Licensed under GPL-2.0\n * or (at your option) any later version.\n */\n",
    "# This file is GPL-2.0\n# or any later version\n",
    "// GPL-2.0\n// or later\n",
    "/* GPL-2.0\r\n * or later */\r\n",
    "# GPL-2.0\n# - or later\n",  # a dash between words (D10); it was none
]


@pytest.mark.parametrize(
    "content", WRAPPED, ids=["block", "hash", "slash", "crlf", "dash"]
)
def test_a_grant_wrapped_onto_a_comment_line(
    corpus_db: LicenseDatabase, tmp_path: Path, content: str
) -> None:
    assert _file(corpus_db, tmp_path, content) == ("GPL-2.0-or-later", True)


@pytest.mark.parametrize(
    "content",
    [
        "// GPL-2.0;\n// ; or later\n",  # a mark on the line of the "or"
        "# GPL-2.0\n# ? or later\n",
    ],
    ids=["semicolon", "question mark"],
)
def test_a_mark_on_the_line_of_a_wrapped_grant(
    corpus_db: LicenseDatabase, tmp_path: Path, content: str
) -> None:
    assert _file(corpus_db, tmp_path, content) is None


# --- the judges, one by one ----------------------------------------------------


@pytest.mark.parametrize(
    ("text", "answer"),
    [
        ("Copyright Intel Corp. GPL-2.0 or later", "GPL-2.0-or-later"),
        ("GPL-2.0 or later, Intel", ""),  # an item of its own
        ("Intel; GPL-2.0 or later", ""),
        ("Intel & GPL-2.0 or later", ""),
        ("GPL-2.0 or later, or ISC", None),  # an operator: no reading at all
        ("ISC, MIT, GPL-2.0 or later", ""),
        ("GPL-2.0 or later, see GFDL-1.3", ""),  # a version: a licence anywhere
        ("GPL-2.0 or later, see Intel", "GPL-2.0-or-later"),
        ("GPL-2.0 or later (GPL-2.0-or-later)", "GPL-2.0-or-later"),  # its own
        ("GPL-2.0 or later, 2009", "GPL-2.0-or-later"),  # a number, no ID
    ],
)
def test_lists_another(
    corpus_db: LicenseDatabase, text: str, answer: str | None
) -> None:
    assert disambiguate_whole(text, corpus_db) == answer


@pytest.mark.parametrize(
    ("text", "listed"),
    [
        ("Intel and GPL-2.0", True),  # an operator joins two items
        ("Intel or GPL-2.0", True),
        ("Intel GPL-2.0", False),  # a prose word
    ],
)
def test_an_operator_ends_a_list_item(
    corpus_db: LicenseDatabase, text: str, listed: bool
) -> None:
    # disambiguate_whole declines an operator before it asks; the judge
    # still holds to the rule on its own.
    assert _lists_another(text, {"gpl-2.0"}, corpus_db) is listed


@pytest.mark.parametrize(
    ("before", "head"),
    [
        ("MIT ", "MIT"),
        ("MIT (", "MIT"),
        ("MIT, [", "MIT,"),
        ("MIT,", None),  # no word "or" after a mark
        ("", None),
    ],
)
def test_grant_head_is_one_rule(before: str, head: str | None) -> None:
    assert grant_head(before) == head
    assert declared_grant_id_text(f"{before}or later") == head


@pytest.mark.parametrize(
    ("rest", "granted"),
    [
        ("\n * or later", True),
        ("\n// or later", True),
        ("\n# (or later)", True),
        ("\r\n * or later", True),
        ("\r * or later", True),  # a carriage return alone breaks a line too
        (";\n * or later", True),  # only the last line is judged
        ("\n * ; or later", None),
        ("\n# - or later", True),  # a dash between words (D10)
        ("\n# ? or later", None),
        ("\n *or later", None),  # no word "or"
    ],
)
def test_a_wrapped_grant_is_judged_on_its_line(rest: str, granted: bool | None) -> None:
    assert grant_follows("GPL-2.0", rest) is granted


def test_a_plus_on_the_exception_of_a_with_is_not_read(
    corpus_db: LicenseDatabase,
) -> None:
    """Only a licence's "+" counts: one after an exception is no operator
    (plusoperator.PLUS_OPERATOR), so it makes no reading ambiguous."""
    found: list[CandidateMatch] = [{"license_id": "MIT", "search_text": ""}]
    assert read_inexactly(corpus_db, "GPL-2.0-with-GCC-exception+", found) == (
        "ambiguous"
    )
    with_it = "MIT WITH GPL-2.0-with-GCC-exception+"
    assert read_inexactly(corpus_db, with_it, found) is None
